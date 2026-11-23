from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts.verify_release_data import DEFAULT_MANIFEST, verify

ROOT = Path(__file__).resolve().parents[1]


def test_release_manifest_and_cross_file_invariants() -> None:
    result = verify()
    assert result["ok"], result["errors"]
    assert result["files_checked"] == 12
    assert result["rows_checked"] == 5428


def test_manifest_covers_settings_schemas_and_branches() -> None:
    manifest = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
    protocol = manifest["annotation_protocol"]
    assert protocol["primary"]["display_name"] == "Mistral Large 3 2512"
    assert protocol["secondary"]["display_name"] == "MiniMax M3"
    assert protocol["temperature"] == 0.0
    assert protocol["seed"] == 20260729
    assert protocol["labels_are_human_annotations"] is False

    entries = {entry["path"]: entry for entry in manifest["files"]}
    representative = entries["data/confirmatory_v1/human_validation/representative_arm_audit.csv"]
    assert representative["rows"] == 288
    assert set(representative["branch_counts"].values()) == {48}
    factorial = entries["data/confirmatory_v1/human_validation/factorial_paired_audit_expanded.csv"]
    assert factorial["rows"] == 1200
    assert set(factorial["branch_counts"].values()) == {300}
    assert not {
        "messages",
        "judge_rationale",
        "cache_hit",
        "created_at",
    }.intersection(factorial["schema"])


def test_released_h3_is_current_primary_rater_freeze() -> None:
    frame = pd.read_csv(
        ROOT / "data" / "confirmatory_v1" / "human_validation" / "paired_h3_audit.csv"
    )
    assert set(frame["annotator_id"].astype(str)) == {"A1"}
    assert set(frame["annotator_model"].astype(str)) == {"mistralai/mistral-large-2512"}
    assert frame["record_id"].is_unique
    assert frame["branch"].value_counts().to_dict() == {
        "existence_assertion": 100,
        "authority_pressure": 100,
    }
