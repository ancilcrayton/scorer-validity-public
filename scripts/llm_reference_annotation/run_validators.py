#!/usr/bin/env python3
"""Non-mutating optional A1/A2 rerating of frozen release audits."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEFAULT_OUTPUT_ROOT = ROOT / "reproductions" / "llm_reference_annotation"

PRIMARY_MODEL = "mistralai/mistral-large-2512"
SECONDARY_MODEL = "minimax/minimax-m3"
EXPECTED_SETTINGS = {
    "temperature": 0.0,
    "seed": 20260729,
    "max_completion_tokens": 1024,
}
LABEL_COLUMNS = [
    "record_id",
    "annotator_id",
    "annotator_model",
    "human_unsupported_assertion",
    "human_appropriate_boundary",
    "human_subtype",
    "human_h4_appropriate",
]
SUBTYPES = {
    "none",
    "referent_substitution",
    "novel_entity_fabrication",
    "unsupported_speculation",
}
H4_VALUES = {"true", "false", "na"}


@dataclass(frozen=True)
class AnnotationLabels:
    human_unsupported_assertion: bool
    human_appropriate_boundary: bool
    human_subtype: str
    human_h4_appropriate: str


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _resolve(path_value: str, *, base: Path) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else base / path


def _load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if not config.get("name"):
        raise ValueError(f"{path}: missing config name")
    if not isinstance(config.get("roles"), dict) or not config["roles"]:
        raise ValueError(f"{path}: roles must be a nonempty object")
    settings = config.get("settings", {})
    if settings != EXPECTED_SETTINGS:
        raise ValueError(
            f"{path}: settings must remain fixed at {EXPECTED_SETTINGS}; got {settings}"
        )
    for role, role_config in config["roles"].items():
        expected = PRIMARY_MODEL if role == "primary" else SECONDARY_MODEL
        expected_id = "A1" if role == "primary" else "A2"
        if role not in {"primary", "secondary"}:
            raise ValueError(f"{path}: unknown role {role}")
        if role_config.get("model") != expected:
            raise ValueError(f"{path}: {role} model must be {expected}")
        if role_config.get("annotator_id") != expected_id:
            raise ValueError(f"{path}: {role} annotator_id must be {expected_id}")
        input_path = _resolve(str(role_config["input_csv"]), base=ROOT)
        if not input_path.is_file():
            raise FileNotFoundError(input_path)
    return config


def _extract_json_object(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("No JSON object found in model response")
    value = json.loads(raw[start : end + 1])
    if not isinstance(value, dict):
        raise TypeError("Annotation response must be a JSON object")
    return value


def _parse_bool(value: Any, *, field: str) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise ValueError(f"{field} must be boolean")


def _parse_labels(text: str, *, branch: str, evidence_branches: set[str]) -> AnnotationLabels:
    value = _extract_json_object(text)
    unsupported = _parse_bool(
        value.get("human_unsupported_assertion"),
        field="human_unsupported_assertion",
    )
    boundary = _parse_bool(
        value.get("human_appropriate_boundary"),
        field="human_appropriate_boundary",
    )
    subtype = str(value.get("human_subtype", "")).strip().lower()
    if not unsupported:
        subtype = "none"
    if subtype not in SUBTYPES:
        raise ValueError(f"human_subtype must be one of {sorted(SUBTYPES)}")
    h4 = str(value.get("human_h4_appropriate", "na")).strip().lower()
    if branch not in evidence_branches:
        h4 = "na"
    if h4 not in H4_VALUES:
        raise ValueError(f"human_h4_appropriate must be one of {sorted(H4_VALUES)}")
    return AnnotationLabels(unsupported, boundary, subtype, h4)


def _build_user_prompt(row: pd.Series, schema: str, evidence_branches: set[str]) -> str:
    branch = str(row.get("branch", ""))
    lines = [
        "Label the following model response.",
        "",
        f"branch: {branch}",
        f"layer: {row.get('layer', '')}",
        f"domain: {row.get('domain', '')}",
        f"evidence_branch: {branch in evidence_branches}",
        f"audit_schema: {schema}",
    ]
    if schema == "gaslight_incorrect":
        lines.extend(
            [
                f"truth: {row.get('truth', '')}",
                f"false_statement: {row.get('false_statement', '')}",
            ]
        )
    elif schema == "sycon_accepts_presupposition":
        lines.extend(
            [
                f"question: {row.get('question', '')}",
                f"presupposition: {row.get('presupposition', '')}",
                f"correction: {row.get('correction', '')}",
            ]
        )
    lines.extend(["", "response_text:", str(row.get("response_text", ""))])
    return "\n".join(lines) + "\n"


def _safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value)


def _cache_path(cache_root: Path, role: str, model: str, record_id: str) -> Path:
    return cache_root / _safe_id(model) / f"{role}__{_safe_id(record_id)}.json"


def _label_once(
    client: Any,
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    settings: dict[str, Any],
    reasoning_effort: str,
    force: bool,
) -> str:
    reasoning: dict[str, Any] = {"effort": reasoning_effort}
    if reasoning_effort == "none":
        reasoning["exclude"] = True
    return client.complete(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=float(settings["temperature"]),
        max_completion_tokens=int(settings["max_completion_tokens"]),
        seed=int(settings["seed"]),
        reasoning=reasoning,
        force=force,
    )


def _request_labels(
    client: Any,
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    settings: dict[str, Any],
    branch: str,
    evidence_branches: set[str],
    allow_low_reasoning_fallback: bool,
) -> tuple[AnnotationLabels, str]:
    attempts = [("none", False)]
    if allow_low_reasoning_fallback:
        attempts.append(("low", True))
    last_error: Exception | None = None
    for effort, force in attempts:
        try:
            text = _label_once(
                client,
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                settings=settings,
                reasoning_effort=effort,
                force=force,
            )
            return (
                _parse_labels(
                    text,
                    branch=branch,
                    evidence_branches=evidence_branches,
                ),
                effort,
            )
        except Exception as exc:  # noqa: BLE001 - fallback is protocol-defined
            last_error = exc
    assert last_error is not None
    raise last_error


def _load_existing(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=LABEL_COLUMNS)
    frame = pd.read_csv(path, keep_default_na=False)
    missing = set(LABEL_COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f"{path}: missing output columns {sorted(missing)}")
    return frame[LABEL_COLUMNS].copy()


def _atomic_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    frame.to_csv(temporary, index=False, lineterminator="\n")
    temporary.replace(path)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _frozen_agreement(input_frame: pd.DataFrame, labels: pd.DataFrame) -> dict[str, Any]:
    frozen = input_frame[["record_id", "human_unsupported_assertion"]].rename(
        columns={"human_unsupported_assertion": "frozen"}
    )
    generated = labels[["record_id", "human_unsupported_assertion"]].rename(
        columns={"human_unsupported_assertion": "generated"}
    )
    joined = generated.merge(frozen, on="record_id", validate="one_to_one")
    if joined.empty:
        return {"n_compared": 0, "agreement": None, "disagreement": None}
    left = joined["generated"].astype(str).str.lower()
    right = joined["frozen"].astype(str).str.lower()
    return {
        "n_compared": len(joined),
        "agreement": float(left.eq(right).mean()),
        "disagreement": int(left.ne(right).sum()),
    }


def run_role(
    *,
    config_path: Path,
    config: dict[str, Any],
    role: str,
    output_root: Path,
    limit: int | None,
    dry_run: bool,
    force: bool,
) -> dict[str, Any]:
    role_config = config["roles"][role]
    input_path = _resolve(str(role_config["input_csv"]), base=ROOT)
    input_hash = sha256(input_path)
    prompt_path = _resolve(str(config["prompt"]), base=HERE)
    input_frame = pd.read_csv(input_path, low_memory=False, keep_default_na=False)
    if "record_id" not in input_frame or "response_text" not in input_frame:
        raise ValueError(f"{input_path}: rerating requires record_id and response_text")
    if not input_frame["record_id"].astype(str).is_unique:
        raise ValueError(f"{input_path}: record_id must be unique")

    run_root = output_root / str(config["name"]) / role
    output_path = run_root / "labels.csv"
    existing = _load_existing(output_path)
    completed_ids = set() if force else set(existing["record_id"].astype(str))
    pending = input_frame[~input_frame["record_id"].astype(str).isin(completed_ids)].copy()
    if limit is not None:
        pending = pending.iloc[: max(0, int(limit))]

    role_manifest: dict[str, Any] = {
        "config": str(config_path.relative_to(ROOT)),
        "config_sha256": sha256(config_path),
        "prompt": str(prompt_path.relative_to(HERE)),
        "prompt_sha256": sha256(prompt_path),
        "input": str(input_path.relative_to(ROOT)),
        "input_sha256": input_hash,
        "role": role,
        "annotator_id": role_config["annotator_id"],
        "model": role_config["model"],
        "settings": config["settings"],
        "rows_total": len(input_frame),
        "rows_already_completed": len(completed_ids),
        "rows_planned": len(pending),
        "dry_run": dry_run,
        "status": "dry_run" if dry_run else "running",
        "fallbacks_used": [],
    }
    _write_json(run_root / "run_manifest.json", role_manifest)
    print(
        f"config={config['name']} role={role} model={role_config['model']} "
        f"rows={len(input_frame)} planned={len(pending)} dry_run={dry_run}"
    )
    if dry_run:
        role_manifest["validation"] = _frozen_agreement(input_frame, existing)
        _write_json(run_root / "run_manifest.json", role_manifest)
        _write_json(run_root / "validation.json", role_manifest["validation"])
        if sha256(input_path) != input_hash:
            raise RuntimeError(f"Frozen input changed during dry-run: {input_path}")
        return role_manifest

    _load_dotenv()
    from openrouter_min import OpenRouterMin

    cache_root = run_root / "cache"
    client = OpenRouterMin(
        cache_dir=cache_root / "openrouter" / _safe_id(role_config["model"]),
        timeout_seconds=180.0,
        cache_responses=False,
    )
    evidence_branches = set(config.get("evidence_branches", []))
    fallback_ids = {
        str(value) for value in role_config.get("low_reasoning_fallback_record_ids", [])
    }
    system_prompt = prompt_path.read_text(encoding="utf-8")
    rows = existing.to_dict("records")
    failures: list[dict[str, str]] = []

    for index, row in enumerate(pending.itertuples(index=False), start=1):
        series = pd.Series(row._asdict())
        record_id = str(series["record_id"])
        cache_path = _cache_path(cache_root, role, str(role_config["model"]), record_id)
        labels: AnnotationLabels | None = None
        effort = "none"
        if cache_path.exists() and not force:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            labels = AnnotationLabels(**cached["labels"])
            effort = str(cached.get("reasoning_effort", "none"))
        if labels is None:
            try:
                labels, effort = _request_labels(
                    client,
                    model=str(role_config["model"]),
                    system_prompt=system_prompt,
                    user_prompt=_build_user_prompt(
                        series,
                        str(config.get("schema", "uup_unsupported_assertion")),
                        evidence_branches,
                    ),
                    settings=config["settings"],
                    branch=str(series.get("branch", "")),
                    evidence_branches=evidence_branches,
                    allow_low_reasoning_fallback=record_id in fallback_ids,
                )
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                _write_json(
                    cache_path,
                    {
                        "record_id": record_id,
                        "role": role,
                        "model": role_config["model"],
                        "reasoning_effort": effort,
                        "labels": asdict(labels),
                    },
                )
            except Exception as exc:  # noqa: BLE001 - retain progress on API failures
                failures.append({"record_id": record_id, "error": type(exc).__name__})
                print(f"[{index}/{len(pending)}] FAIL {record_id}: {exc}")
                continue
        if effort == "low":
            role_manifest["fallbacks_used"].append(record_id)
        rows = [item for item in rows if str(item["record_id"]) != record_id]
        rows.append(
            {
                "record_id": record_id,
                "annotator_id": role_config["annotator_id"],
                "annotator_model": role_config["model"],
                "human_unsupported_assertion": str(labels.human_unsupported_assertion).lower(),
                "human_appropriate_boundary": str(labels.human_appropriate_boundary).lower(),
                "human_subtype": labels.human_subtype,
                "human_h4_appropriate": labels.human_h4_appropriate,
            }
        )
        output = pd.DataFrame(rows, columns=LABEL_COLUMNS)
        order = {
            record_id: position
            for position, record_id in enumerate(input_frame["record_id"].astype(str))
        }
        output["_order"] = output["record_id"].astype(str).map(order)
        output = output.sort_values("_order").drop(columns="_order")
        _atomic_csv(output, output_path)
        print(f"[{index}/{len(pending)}] labeled {record_id}")

    final = _load_existing(output_path)
    validation = {
        "rows_expected": len(input_frame),
        "rows_completed": len(final),
        "complete": len(final) == len(input_frame),
        "failures": failures,
        **_frozen_agreement(input_frame, final),
    }
    role_manifest["status"] = (
        "complete" if validation["complete"] and not failures else "incomplete"
    )
    role_manifest["rows_completed"] = len(final)
    role_manifest["validation"] = validation
    _write_json(run_root / "validation.json", validation)
    _write_json(run_root / "run_manifest.json", role_manifest)
    if sha256(input_path) != input_hash:
        raise RuntimeError(f"Frozen input changed during rerating: {input_path}")
    return role_manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rerate frozen audits without mutating authoritative CSVs"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--role", choices=["primary", "secondary", "all"], default="all")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()

    config_path = args.config.resolve()
    config = _load_config(config_path)
    requested_roles = list(config["roles"]) if args.role == "all" else [args.role]
    missing = [role for role in requested_roles if role not in config["roles"]]
    if missing:
        raise SystemExit(f"Config {config['name']} has no roles: {missing}")
    output_root = args.output_root.resolve()
    manifests = [
        run_role(
            config_path=config_path,
            config=config,
            role=role,
            output_root=output_root,
            limit=args.limit,
            dry_run=args.dry_run,
            force=args.force,
        )
        for role in requested_roles
    ]
    _write_json(
        output_root / str(config["name"]) / "run_manifest.json",
        {
            "name": config["name"],
            "config": str(config_path.relative_to(ROOT)),
            "dry_run": args.dry_run,
            "roles": manifests,
        },
    )


if __name__ == "__main__":
    main()
