from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ANNOTATION_DIR = ROOT / "scripts" / "llm_reference_annotation"
RUNNER = ANNOTATION_DIR / "run_validators.py"
CONFIGS = [
    "config_representative_arm.json",
    "config_factorial_expanded.json",
    "config_hard_audit.json",
    "config_paired_h3.json",
    "config_gaslight.json",
    "config_sycon.json",
]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("config_name", CONFIGS)
def test_annotation_dry_run_is_offline_and_non_mutating(config_name: str, tmp_path: Path) -> None:
    config_path = ANNOTATION_DIR / config_name
    config = json.loads(config_path.read_text(encoding="utf-8"))
    input_paths = [ROOT / role["input_csv"] for role in config["roles"].values()]
    before = {path: digest(path) for path in input_paths}
    environment = os.environ.copy()
    environment.pop("OPENROUTER_API_KEY", None)
    subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--config",
            str(config_path),
            "--role",
            "all",
            "--dry-run",
            "--output-root",
            str(tmp_path),
        ],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    assert {path: digest(path) for path in input_paths} == before

    run_manifest = json.loads(
        (tmp_path / config["name"] / "run_manifest.json").read_text(encoding="utf-8")
    )
    assert run_manifest["dry_run"] is True
    assert {role["role"] for role in run_manifest["roles"]} == set(config["roles"])
    for role in run_manifest["roles"]:
        assert role["status"] == "dry_run"
        assert role["rows_planned"] == role["rows_total"]
        assert role["settings"] == {
            "temperature": 0.0,
            "seed": 20260729,
            "max_completion_tokens": 1024,
        }
        assert not (tmp_path / config["name"] / role["role"] / "labels.csv").exists()
