from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def release_paths() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [ROOT / line for line in result.stdout.splitlines() if line and (ROOT / line).exists()]


def test_release_tree_excludes_manuscripts_raw_inputs_and_private_artifacts() -> None:
    paths = release_paths()
    relative = [path.relative_to(ROOT).as_posix() for path in paths]
    forbidden_suffixes = {
        ".tex",
        ".bib",
        ".sty",
        ".bst",
        ".cls",
        ".aux",
        ".log",
        ".blg",
    }
    assert not [path for path in relative if Path(path).suffix.lower() in forbidden_suffixes]
    assert not [path for path in relative if path.startswith("paper/neurips2026/")]
    assert not [path for path in relative if path.endswith("/main.pdf") or path == "paper/main.pdf"]
    forbidden_fragments = (
        ".PROTECTED",
        "private_archive",
        "/cache/",
        "data/external/",
        "results/confirmatory_v1/annotations/",
        "results/confirmatory_v1/robustness/",
        "sync_variant_tables.py",
        "build_factorial_human_audit_expanded.py",
    )
    assert not [
        path for path in relative if any(fragment in path for fragment in forbidden_fragments)
    ]
    assert ".env" not in relative


def test_release_docs_and_annotation_configs_use_current_rater_framing() -> None:
    candidates = [
        path
        for path in release_paths()
        if path.suffix.lower() == ".md"
        or path.name == ".env.example"
        or (
            path.parent == ROOT / "scripts" / "llm_reference_annotation"
            and path.name.startswith("config_")
            and path.suffix == ".json"
        )
    ]
    stale = re.compile(r"deepseek|gpt-5\.6-luna|\bluna\b", re.IGNORECASE)
    violations = {
        str(path.relative_to(ROOT)): stale.findall(
            path.read_text(encoding="utf-8", errors="ignore")
        )
        for path in candidates
        if stale.search(path.read_text(encoding="utf-8", errors="ignore"))
    }
    assert not violations


def test_release_contains_no_openrouter_secret() -> None:
    violations = []
    for path in release_paths():
        if not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if ("sk-or-" + "v1-") in text:
            violations.append(str(path.relative_to(ROOT)))
    assert not violations
