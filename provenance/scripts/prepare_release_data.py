#!/usr/bin/env python3
"""Build the scorer paper's release-safe frozen data package.

This is a maintainer-only packaging utility. Offline reproduction uses the
already-released CSVs and never requires the upstream repository.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / "data" / "confirmatory_v1"
AUDIT_ROOT = DATA_ROOT / "human_validation"
ALT_ROOT = DATA_ROOT / "alternative_judge"

PRIMARY_MODEL = "mistralai/mistral-large-2512"
SECONDARY_MODEL = "minimax/minimax-m3"
ANNOTATION_RUN_ID = "unused_families_20260819"
ANNOTATION_SEED = 20260729
ANNOTATION_TEMPERATURE = 0.0

REFERENCE_FIELDS = [
    "human_unsupported_assertion",
    "human_appropriate_boundary",
    "human_subtype",
    "human_h4_appropriate",
    "annotator_id",
    "dual_annotation",
]

UUP_COLUMNS = [
    "record_id",
    "model_slug",
    "item_id",
    "branch",
    "domain",
    "layer",
    "unsupported_assertion",
    "unsupported_answer_subtype",
    "baseline_appropriate",
    "response_text",
    *REFERENCE_FIELDS,
    "epistemic_behavior",
    "transition",
    "scoring_source",
    "audit_role",
    "annotator_model",
    "annotation_run_id",
    "annotation_prompt",
]

H3_COLUMNS = [*UUP_COLUMNS, "paired_contrast"]

GASLIGHT_COLUMNS = [
    "record_id",
    "model_slug",
    "item_id",
    "statement_id",
    "modifier_id",
    "modifier_category",
    "statement_category",
    "branch",
    "domain",
    "layer",
    "response_text",
    "truth",
    "false_statement",
    "auto_incorrect",
    *REFERENCE_FIELDS,
    "audit_role",
    "audit_schema",
    "annotator_model",
    "annotation_run_id",
    "annotation_prompt",
]

SYCON_COLUMNS = [
    "record_id",
    "model_slug",
    "item_id",
    "topic_id",
    "trajectory",
    "turn",
    "branch",
    "domain",
    "layer",
    "response_text",
    "question",
    "presupposition",
    "correction",
    "auto_accepts",
    *REFERENCE_FIELDS,
    "audit_role",
    "audit_schema",
    "annotator_model",
    "annotation_run_id",
    "annotation_prompt",
]

ALT_SOURCE_COLUMNS = [
    "record_id",
    "model_slug",
    "item_id",
    "branch",
    "primary_unsupported",
    "judge_model_alt",
    "judge_unsupported_alt",
    "judge_boundary_alt",
]

ALT_RENAMES = {
    "primary_unsupported": "pipeline_unsupported_assertion",
    "judge_model_alt": "alternative_judge_model",
    "judge_unsupported_alt": "alternative_unsupported_assertion",
    "judge_boundary_alt": "alternative_appropriate_boundary",
}

FORBIDDEN_COLUMNS = {
    "messages",
    "judge_rationale",
    "provider",
    "provider_name",
    "cache_hit",
    "created_at",
    "timestamp",
    "timestamp_utc",
    "raw_reasoning",
    "reasoning",
    "raw_response",
    "raw_response_text",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def upstream_revision(root: Path) -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def counts(frame: pd.DataFrame, column: str) -> dict[str, int]:
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


def select_h3(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[frame["paired_contrast"].astype(str).eq("H3")].copy()


def identity(frame: pd.DataFrame) -> pd.DataFrame:
    return frame


@dataclass(frozen=True)
class ReleaseSpec:
    output: Path
    source: Path
    columns: list[str]
    description: str
    sampling_seed: int | None
    sampling_design: str
    rater_role: str | None
    rater_model: str | None
    transform: Callable[[pd.DataFrame], pd.DataFrame] = identity
    set_values: dict[str, str] | None = None
    rename: dict[str, str] | None = None


def build_specs(upstream: Path) -> list[ReleaseSpec]:
    human = upstream / "data" / "confirmatory_v1" / "human_validation"
    return [
        ReleaseSpec(
            AUDIT_ROOT / "representative_arm_audit.csv",
            human / "representative_arm_audit.csv",
            UUP_COLUMNS,
            "Balanced representative arm-by-model audit (A1)",
            20260805,
            "48 clean responses per arm, balanced at eight per evaluated model",
            "primary",
            PRIMARY_MODEL,
        ),
        ReleaseSpec(
            AUDIT_ROOT / "representative_arm_audit_dual.csv",
            human / "representative_arm_audit_dual.csv",
            UUP_COLUMNS,
            "Representative audit dual-rater subset (A2)",
            20260805,
            "Prespecified 96-row subset across four arms",
            "secondary",
            SECONDARY_MODEL,
        ),
        ReleaseSpec(
            AUDIT_ROOT / "factorial_paired_audit_expanded.csv",
            human / "factorial_paired_audit_expanded.csv",
            UUP_COLUMNS,
            "Four-arm, 300-key factorial paired audit (A1)",
            20260804,
            "300 complete item-model keys, 50 per evaluated model",
            "primary",
            PRIMARY_MODEL,
        ),
        ReleaseSpec(
            AUDIT_ROOT / "factorial_paired_audit_expanded_secondary_full.csv",
            human / "factorial_paired_audit_expanded_secondary_full.csv",
            UUP_COLUMNS,
            "Four-arm, 300-key factorial paired audit (A2)",
            20260804,
            "Same 1,200 responses independently rated by A2",
            "secondary",
            SECONDARY_MODEL,
        ),
        ReleaseSpec(
            AUDIT_ROOT / "hard_audit_primary.csv",
            human / "review_sample.csv",
            UUP_COLUMNS,
            "Primary 550-row hard-case audit",
            None,
            "Tiered stress sample enriched for pressure and routed cases; not a probability sample",
            "primary",
            PRIMARY_MODEL,
            set_values={"audit_role": "hard_audit"},
        ),
        ReleaseSpec(
            AUDIT_ROOT / "paired_h3_audit.csv",
            human / "paired_audit_sample.csv",
            H3_COLUMNS,
            "Primary paired H3 audit (Authority minus Existence)",
            20260803,
            "100 complete item-model keys; H3 subset of the separate paired audit",
            "primary",
            PRIMARY_MODEL,
            transform=select_h3,
            set_values={"audit_role": "paired_h3"},
        ),
        ReleaseSpec(
            AUDIT_ROOT / "gaslight_scorer_audit.csv",
            human / "gaslight_scorer_audit.csv",
            GASLIGHT_COLUMNS,
            "Gaslight non-original incorrectness-heuristic audit (A1)",
            20260804,
            "60 keys with five audited arms",
            "primary",
            PRIMARY_MODEL,
        ),
        ReleaseSpec(
            AUDIT_ROOT / "gaslight_scorer_audit_dual.csv",
            human / "gaslight_scorer_audit_dual.csv",
            GASLIGHT_COLUMNS,
            "Gaslight dual-rater subset (A2)",
            20260804,
            "100-row balanced subset, 20 rows per arm",
            "secondary",
            SECONDARY_MODEL,
        ),
        ReleaseSpec(
            AUDIT_ROOT / "sycon_judge_audit.csv",
            human / "sycon_judge_audit.csv",
            SYCON_COLUMNS,
            "SYCON non-original acceptance-judge audit (A1)",
            20260804,
            "60 topic-model trajectories per condition and five turns per trajectory",
            "primary",
            PRIMARY_MODEL,
        ),
        ReleaseSpec(
            AUDIT_ROOT / "sycon_judge_audit_dual.csv",
            human / "sycon_judge_audit_dual.csv",
            SYCON_COLUMNS,
            "SYCON dual-rater subset (A2)",
            20260804,
            "20 topic-model trajectories per condition and five turns per trajectory",
            "secondary",
            SECONDARY_MODEL,
        ),
        ReleaseSpec(
            ALT_ROOT / "representative_predictions.csv",
            upstream
            / "results"
            / "confirmatory_v1"
            / "statistics"
            / "alt_judge_representative.csv",
            ALT_SOURCE_COLUMNS,
            "Frozen Claude Sonnet 5 alternative automatic-judge predictions",
            None,
            "The same 288 rows as the representative audit",
            None,
            None,
            rename=ALT_RENAMES,
        ),
    ]


def build_one(spec: ReleaseSpec, upstream: Path) -> tuple[pd.DataFrame, dict]:
    if not spec.source.is_file():
        raise FileNotFoundError(spec.source)
    raw_sha = sha256(spec.source)
    frame = pd.read_csv(spec.source, low_memory=False, keep_default_na=False)
    frame = spec.transform(frame)
    if spec.set_values:
        for column, value in spec.set_values.items():
            frame[column] = value
    missing = sorted(set(spec.columns) - set(frame.columns))
    if missing:
        raise ValueError(f"{spec.source}: missing required release columns {missing}")
    frame = frame.loc[:, spec.columns].copy()
    if spec.rename:
        frame = frame.rename(columns=spec.rename)
    leaked = sorted(FORBIDDEN_COLUMNS.intersection(frame.columns))
    if leaked:
        raise ValueError(f"{spec.output}: forbidden release columns {leaked}")
    if not frame["record_id"].astype(str).is_unique:
        raise ValueError(f"{spec.output}: record_id must be unique")
    spec.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(spec.output, index=False, lineterminator="\n")
    empty_response_ids = (
        sorted(
            frame.loc[frame["response_text"].astype(str).str.strip().eq(""), "record_id"].astype(
                str
            )
        )
        if "response_text" in frame
        else []
    )
    entry = {
        "path": str(spec.output.relative_to(REPO_ROOT)),
        "description": spec.description,
        "source": {
            "repository": "unknown-under-pressure",
            "path": str(spec.source.relative_to(upstream)),
            "sha256": raw_sha,
        },
        "released_sha256": sha256(spec.output),
        "rows": len(frame),
        "schema": list(frame.columns),
        "empty_response_record_ids": empty_response_ids,
        "branch_counts": counts(frame, "branch"),
        "trajectory_counts": counts(frame, "trajectory"),
        "sampling": {
            "seed": spec.sampling_seed,
            "design": spec.sampling_design,
        },
        "annotation": (
            {
                "role": spec.rater_role,
                "annotator_id": "A1" if spec.rater_role == "primary" else "A2",
                "model": spec.rater_model,
                "temperature": ANNOTATION_TEMPERATURE,
                "seed": ANNOTATION_SEED,
                "run_id": ANNOTATION_RUN_ID,
            }
            if spec.rater_role
            else None
        ),
    }
    return frame, entry


def bool_series(series: pd.Series) -> pd.Series:
    values = series.astype(str).str.strip().str.lower()
    if not values.isin({"true", "false"}).all():
        raise ValueError(f"Expected complete boolean values; got {sorted(values.unique())}")
    return values.eq("true")


def write_taxonomy(representative: pd.DataFrame, alternative: pd.DataFrame) -> dict:
    joined = representative.merge(
        alternative[["record_id", "alternative_unsupported_assertion"]],
        on="record_id",
        validate="one_to_one",
    )
    joined = joined[joined["branch"].eq("existence_assertion")].copy()
    reference = bool_series(joined["human_unsupported_assertion"])
    pipeline = bool_series(joined["unsupported_assertion"])
    alt = bool_series(joined["alternative_unsupported_assertion"])
    rows: list[dict[str, str]] = []
    for record_id in joined.loc[pipeline & ~reference, "record_id"].astype(str):
        rows.append(
            {
                "record_id": record_id,
                "scorer": "automatic_pipeline",
                "category": "hypothetical_abstention_or_needs_context",
            }
        )
    for record_id in joined.loc[alt & ~reference, "record_id"].astype(str):
        rows.append(
            {
                "record_id": record_id,
                "scorer": "alternative_automatic_judge",
                "category": "hypothetical_or_speculative_completion",
            }
        )
    taxonomy = pd.DataFrame(rows).sort_values(["scorer", "record_id"])
    expected = {"automatic_pipeline": 3, "alternative_automatic_judge": 3}
    if counts(taxonomy, "scorer") != expected:
        raise ValueError(
            "Existence false-positive coding no longer matches the frozen six-row taxonomy"
        )
    output = DATA_ROOT / "derived" / "existence_fp_taxonomy.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    taxonomy.to_csv(output, index=False, lineterminator="\n")
    return {
        "path": str(output.relative_to(REPO_ROOT)),
        "description": "Frozen author-coded surface taxonomy for Existence false positives",
        "source": {
            "released_inputs": [
                "data/confirmatory_v1/human_validation/representative_arm_audit.csv",
                "data/confirmatory_v1/alternative_judge/representative_predictions.csv",
            ]
        },
        "released_sha256": sha256(output),
        "rows": len(taxonomy),
        "schema": list(taxonomy.columns),
        "empty_response_record_ids": [],
        "branch_counts": {},
        "trajectory_counts": {},
        "sampling": {
            "seed": None,
            "design": "Post hoc single-coder surface classification of six false positives",
        },
        "annotation": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--upstream-root",
        type=Path,
        required=True,
        help="Path to the unknown-under-pressure checkout used for packaging",
    )
    parser.add_argument(
        "--upstream-revision",
        default=None,
        help="Optional source revision; defaults to git rev-parse HEAD",
    )
    args = parser.parse_args()
    upstream = args.upstream_root.resolve()
    if not (upstream / "data" / "confirmatory_v1").is_dir():
        raise SystemExit(f"Not an unknown-under-pressure checkout: {upstream}")

    entries: list[dict] = []
    frames: dict[str, pd.DataFrame] = {}
    for spec in build_specs(upstream):
        frame, entry = build_one(spec, upstream)
        entries.append(entry)
        frames[entry["path"]] = frame
        print(f"Wrote {entry['path']} ({entry['rows']} rows)")

    entries.append(
        write_taxonomy(
            frames["data/confirmatory_v1/human_validation/representative_arm_audit.csv"],
            frames["data/confirmatory_v1/alternative_judge/representative_predictions.csv"],
        )
    )

    manifest = {
        "manifest_version": 1,
        "package": "scorer-validity",
        "freeze": "confirmatory_v1",
        "upstream": {
            "repository": "unknown-under-pressure",
            "revision": args.upstream_revision or upstream_revision(upstream),
            "note": (
                "Per-file source hashes are authoritative because the frozen ratings "
                "included uncommitted release preparation at packaging time."
            ),
        },
        "annotation_protocol": {
            "historical_field_prefix": "human_",
            "labels_are_human_annotations": False,
            "primary": {
                "annotator_id": "A1",
                "display_name": "Mistral Large 3 2512",
                "model": PRIMARY_MODEL,
            },
            "secondary": {
                "annotator_id": "A2",
                "display_name": "MiniMax M3",
                "model": SECONDARY_MODEL,
            },
            "temperature": ANNOTATION_TEMPERATURE,
            "seed": ANNOTATION_SEED,
            "run_id": ANNOTATION_RUN_ID,
            "protocol_exceptions": [
                {
                    "record_id": ("qwen/qwen3-32b::clean_9e050df0a6::neutral_repetition::t1"),
                    "role": "secondary",
                    "fallback": (
                        "MiniMax M3 with low reasoning effort after repeated null "
                        "completions; all other settings unchanged"
                    ),
                }
            ],
        },
        "forbidden_columns": sorted(FORBIDDEN_COLUMNS),
        "files": entries,
    }
    manifest_path = DATA_ROOT / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {manifest_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
