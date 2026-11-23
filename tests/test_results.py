from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from paper.analyze_existing_data import correction_analysis

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "paper" / "data" / "scorer_results.json"


def load_results() -> dict:
    return json.loads(RESULTS.read_text(encoding="utf-8"))


def test_current_headline_metrics() -> None:
    payload = load_results()
    representative = payload["representative"]["overall"]
    assert (
        representative["tp"],
        representative["fp"],
        representative["fn"],
        representative["tn"],
    ) == (120, 18, 4, 146)
    assert representative["f1"] == pytest.approx(0.9160305343511451)
    assert payload["representative_dual"]["kappa"] == pytest.approx(0.958315240990013)
    diagnostics = payload["representative"]["unpaired_diagnostics"]
    assert diagnostics["Authority - Existence"]["automatic_rd"] == pytest.approx(11 / 48)
    assert diagnostics["Authority - Existence"]["primary_rater_rd"] == pytest.approx(12 / 48)
    assert payload["representative"]["authority_existence_fpr_fisher_two_sided_p"] == 1.0

    hard = payload["hard_audit"]
    assert hard["routes"]["routed_llm_judge"]["n"] == 264
    assert hard["routes"]["heuristic_only"]["n"] == 286
    assert hard["six_arm_rows"] == 478

    contrasts = payload["factorial"]["contrasts"]
    assert contrasts["Certainty-only - Neutral"]["primary_rater"][
        "risk_difference"
    ] == pytest.approx(0.023333333333333334)
    assert contrasts["Confidence - Neutral"]["primary_rater"]["risk_difference"] == pytest.approx(
        0.07
    )
    assert contrasts["Confidence - Existence x Directness"]["secondary_rater"][
        "risk_difference"
    ] == pytest.approx(-0.19)
    assert payload["factorial"]["dual_rater"]["disagreement"] == pytest.approx(57 / 1200)

    assert payload["paired_h3"]["primary_rater"]["risk_difference"] == pytest.approx(0.15)
    assert payload["alternative_judge"]["overall_vs_primary_rater"]["f1"] == pytest.approx(
        0.9407114624505929
    )
    assert payload["external"]["gaslight"]["overall"]["f1"] == pytest.approx(0.5116279069767442)
    assert payload["external"]["sycon"]["overall"]["f1"] == pytest.approx(0.6606965174129353)
    assert payload["external"]["sycon"]["primary_rater_ever_accept"]["neutral"]["positive"] == 49


def test_release_analysis_outputs_are_byte_deterministic() -> None:
    paths = [
        RESULTS,
        ROOT / "results" / "confirmatory_v1" / "statistics" / "representative_arm_audit.json",
        *sorted((ROOT / "paper" / "tables").glob("*.csv")),
        *sorted((ROOT / "paper" / "tables").glob("*.md")),
    ]
    before = {path: path.read_bytes() for path in paths}
    subprocess.run(
        [sys.executable, str(ROOT / "paper" / "analyze_release_data.py")],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    after = {path: path.read_bytes() for path in paths}
    assert after == before


def test_correction_draws_are_seed_deterministic() -> None:
    audit_root = ROOT / "data" / "confirmatory_v1" / "human_validation"
    representative = pd.read_csv(audit_root / "representative_arm_audit.csv")
    factorial = pd.read_csv(audit_root / "factorial_paired_audit_expanded.csv")
    first = correction_analysis(representative, factorial, draws=2000, seed=17)
    second = correction_analysis(representative, factorial, draws=2000, seed=17)
    assert first == second


def test_figures_use_current_local_statistics() -> None:
    representative_path = (
        ROOT / "results" / "confirmatory_v1" / "statistics" / "representative_arm_audit.json"
    )
    representative = json.loads(representative_path.read_text(encoding="utf-8"))
    assert representative["overall"]["tp"] == 120
    assert representative["by_arm"]["neutral_repetition"]["precision"] == pytest.approx(23 / 24)
    for stem in ("arm_precision_sampling", "problem_contrast"):
        for suffix in (".pdf", ".png"):
            path = ROOT / "paper" / "figures" / f"{stem}{suffix}"
            assert path.is_file()
            assert path.stat().st_size > 1000
