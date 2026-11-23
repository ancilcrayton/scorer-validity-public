#!/usr/bin/env python3
"""Validate release data checksums, schemas, rows, and cross-file coverage."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO_ROOT / "data" / "confirmatory_v1" / "manifest.json"

PRIMARY_MODEL = "mistralai/mistral-large-2512"
SECONDARY_MODEL = "minimax/minimax-m3"
FORBIDDEN_COLUMN_FRAGMENTS = (
    "message",
    "rationale",
    "provider",
    "cache",
    "timestamp",
    "created_at",
    "raw_reason",
    "raw_response",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def value_counts(frame: pd.DataFrame, column: str) -> dict[str, int]:
    if column not in frame:
        return {}
    return {
        str(key): int(value)
        for key, value in frame[column]
        .fillna("<NA>")
        .astype(str)
        .value_counts()
        .sort_index()
        .items()
    }


def strict_bool(series: pd.Series, *, name: str) -> pd.Series:
    values = series.astype(str).str.strip().str.lower()
    if not values.isin({"true", "false"}).all():
        bad = sorted(values[~values.isin({"true", "false"})].unique())
        raise ValueError(f"{name} contains non-boolean values: {bad[:5]}")
    return values.eq("true")


def _load_frames(manifest: dict[str, Any], root: Path) -> tuple[dict[str, pd.DataFrame], list[str]]:
    frames: dict[str, pd.DataFrame] = {}
    errors: list[str] = []
    listed_paths: set[str] = set()

    for entry in manifest.get("files", []):
        relative = str(entry["path"])
        if relative in listed_paths:
            errors.append(f"duplicate manifest path: {relative}")
            continue
        listed_paths.add(relative)
        path = root / relative
        if not path.is_file():
            errors.append(f"missing data file: {relative}")
            continue
        if sha256(path) != entry.get("released_sha256"):
            errors.append(f"checksum mismatch: {relative}")
        frame = pd.read_csv(path, low_memory=False, keep_default_na=False)
        frames[relative] = frame
        if len(frame) != int(entry.get("rows", -1)):
            errors.append(
                f"row mismatch: {relative}: expected {entry.get('rows')}, found {len(frame)}"
            )
        expected_schema = list(entry.get("schema", []))
        if list(frame.columns) != expected_schema:
            errors.append(
                f"schema mismatch: {relative}: expected {expected_schema}, "
                f"found {list(frame.columns)}"
            )
        leaked = [
            column
            for column in frame.columns
            if any(fragment in column.lower() for fragment in FORBIDDEN_COLUMN_FRAGMENTS)
        ]
        if leaked:
            errors.append(f"forbidden release columns in {relative}: {sorted(leaked)}")
        if "record_id" not in frame:
            errors.append(f"missing record_id: {relative}")
        elif not frame["record_id"].astype(str).is_unique:
            errors.append(f"duplicate record_id: {relative}")
        empty_response_ids = (
            sorted(
                frame.loc[
                    frame["response_text"].astype(str).str.strip().eq(""), "record_id"
                ].astype(str)
            )
            if "response_text" in frame
            else []
        )
        if empty_response_ids != entry.get("empty_response_record_ids", []):
            errors.append(f"empty response_text coverage mismatch: {relative}")
        if value_counts(frame, "branch") != entry.get("branch_counts", {}):
            errors.append(f"branch coverage mismatch: {relative}")
        if value_counts(frame, "trajectory") != entry.get("trajectory_counts", {}):
            errors.append(f"trajectory coverage mismatch: {relative}")

        annotation = entry.get("annotation")
        if annotation:
            try:
                strict_bool(
                    frame["human_unsupported_assertion"],
                    name=f"{relative}:human_unsupported_assertion",
                )
            except (KeyError, ValueError) as exc:
                errors.append(str(exc))
            expected_id = annotation["annotator_id"]
            if set(frame["annotator_id"].astype(str)) != {expected_id}:
                errors.append(f"annotator_id mismatch: {relative}")
            expected_model = annotation["model"]
            if set(frame["annotator_model"].astype(str)) != {expected_model}:
                errors.append(f"annotator_model mismatch: {relative}")
            if annotation.get("temperature") != 0.0 or annotation.get("seed") != 20260729:
                errors.append(f"annotation settings mismatch: {relative}")

    return frames, errors


def _check_cross_file(frames: dict[str, pd.DataFrame]) -> list[str]:
    errors: list[str] = []
    base = "data/confirmatory_v1"

    def ids(path: str) -> set[str]:
        return set(frames[path]["record_id"].astype(str))

    representative = f"{base}/human_validation/representative_arm_audit.csv"
    representative_dual = f"{base}/human_validation/representative_arm_audit_dual.csv"
    factorial = f"{base}/human_validation/factorial_paired_audit_expanded.csv"
    factorial_dual = f"{base}/human_validation/factorial_paired_audit_expanded_secondary_full.csv"
    hard = f"{base}/human_validation/hard_audit_primary.csv"
    h3 = f"{base}/human_validation/paired_h3_audit.csv"
    gaslight = f"{base}/human_validation/gaslight_scorer_audit.csv"
    gaslight_dual = f"{base}/human_validation/gaslight_scorer_audit_dual.csv"
    sycon = f"{base}/human_validation/sycon_judge_audit.csv"
    sycon_dual = f"{base}/human_validation/sycon_judge_audit_dual.csv"
    alternative = f"{base}/alternative_judge/representative_predictions.csv"
    taxonomy = f"{base}/derived/existence_fp_taxonomy.csv"

    required = {
        representative,
        representative_dual,
        factorial,
        factorial_dual,
        hard,
        h3,
        gaslight,
        gaslight_dual,
        sycon,
        sycon_dual,
        alternative,
        taxonomy,
    }
    missing = required - set(frames)
    if missing:
        return [f"manifest omits required release files: {sorted(missing)}"]

    if not ids(representative_dual) < ids(representative):
        errors.append("representative A2 rows must be a proper subset of A1 rows")
    if ids(factorial_dual) != ids(factorial):
        errors.append("factorial A1/A2 record coverage differs")
    if not ids(gaslight_dual) < ids(gaslight):
        errors.append("Gaslight A2 rows must be a proper subset of A1 rows")
    if not ids(sycon_dual) < ids(sycon):
        errors.append("SYCON A2 rows must be a proper subset of A1 rows")
    if ids(alternative) != ids(representative):
        errors.append("alternative-judge predictions must cover all representative rows")

    expected_h3 = {"authority_pressure": 100, "existence_assertion": 100}
    if value_counts(frames[h3], "branch") != expected_h3:
        errors.append("paired H3 branch coverage must be 100 rows per arm")
    expected_hard = {
        "authority_pressure": 111,
        "confidence_pressure": 125,
        "cue_baseline": 74,
        "evidence_false": 24,
        "evidence_reassurance": 24,
        "evidence_valid": 24,
        "existence_assertion": 63,
        "neutral_repetition": 81,
        "spontaneous_baseline": 24,
    }
    if value_counts(frames[hard], "branch") != expected_hard:
        errors.append("hard-audit branch coverage changed")

    rep = frames[representative]
    alt = frames[alternative]
    tax = frames[taxonomy]
    joined = rep.merge(
        alt, on=["record_id", "model_slug", "item_id", "branch"], validate="one_to_one"
    )
    existence = joined[joined["branch"].eq("existence_assertion")]
    reference = strict_bool(
        existence["human_unsupported_assertion"], name="representative reference labels"
    )
    pipeline = strict_bool(
        existence["unsupported_assertion"], name="representative automatic labels"
    )
    alternative_label = strict_bool(
        existence["alternative_unsupported_assertion"], name="alternative predictions"
    )
    expected_taxonomy_ids = set(
        existence.loc[pipeline & ~reference, "record_id"].astype(str)
    ) | set(existence.loc[alternative_label & ~reference, "record_id"].astype(str))
    if set(tax["record_id"].astype(str)) != expected_taxonomy_ids:
        errors.append("existence false-positive taxonomy IDs do not match scorer false positives")
    if value_counts(tax, "scorer") != {
        "alternative_automatic_judge": 3,
        "automatic_pipeline": 3,
    }:
        errors.append("existence false-positive taxonomy must contain three rows per scorer")
    return errors


def verify(manifest_path: Path = DEFAULT_MANIFEST, root: Path = REPO_ROOT) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    if manifest.get("manifest_version") != 1:
        errors.append("unsupported manifest version")
    protocol = manifest.get("annotation_protocol", {})
    if protocol.get("labels_are_human_annotations") is not False:
        errors.append("manifest must state that historical human_* fields are LLM labels")
    if protocol.get("primary", {}).get("model") != PRIMARY_MODEL:
        errors.append("primary rater must be Mistral Large 3 2512")
    if protocol.get("secondary", {}).get("model") != SECONDARY_MODEL:
        errors.append("secondary rater must be MiniMax M3")
    if protocol.get("temperature") != 0.0 or protocol.get("seed") != 20260729:
        errors.append("global annotation settings changed")

    frames, frame_errors = _load_frames(manifest, root)
    errors.extend(frame_errors)
    errors.extend(_check_cross_file(frames))
    return {
        "ok": not errors,
        "manifest": str(manifest_path.relative_to(root)),
        "files_checked": len(frames),
        "rows_checked": sum(len(frame) for frame in frames.values()),
        "errors": errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    result = verify(args.manifest.resolve())
    print(json.dumps(result, indent=2))
    if not result["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
