#!/usr/bin/env python3
"""Existing-data correction, reference-sensitivity, and heterogeneity diagnostics."""

from __future__ import annotations

import itertools
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import chi2, norm

PAPER_DIR = Path(__file__).resolve().parent
REPO_ROOT = PAPER_DIR.parent
HUMAN_DIR = REPO_ROOT / "data" / "confirmatory_v1" / "human_validation"
REPRESENTATIVE = HUMAN_DIR / "representative_arm_audit.csv"
REPRESENTATIVE_DUAL = HUMAN_DIR / "representative_arm_audit_dual.csv"
FACTORIAL = HUMAN_DIR / "factorial_paired_audit_expanded.csv"
FACTORIAL_SECONDARY = HUMAN_DIR / "factorial_paired_audit_expanded_secondary_full.csv"
OUTPUT_JSON = PAPER_DIR / "data" / "existing_data_analysis.json"
TABLES_DIR = PAPER_DIR / "tables"
CORRECTION_TABLE = TABLES_DIR / "arm_correction"
REFERENCE_TABLE = TABLES_DIR / "reference_sensitivity"
RATER_TABLE = TABLES_DIR / "rater_sensitivity"
HETEROGENEITY_TABLE = TABLES_DIR / "heterogeneity_power"

ARM_LABELS = {
    "authority_pressure": "Authority",
    "cue_baseline": "Soft cue",
    "neutral_repetition": "Neutral",
    "certainty_only": "Certainty-only",
    "confidence_pressure": "Confidence",
    "existence_assertion": "Existence",
    "existence_directness": "Existence$\\times$Directness",
    "spontaneous_baseline": "Spontaneous",
}
CONTRASTS = [
    ("certainty_only", "neutral_repetition", "Certainty-only $-$ Neutral"),
    (
        "confidence_pressure",
        "existence_directness",
        "Confidence $-$ Existence$\\times$Directness",
    ),
    ("confidence_pressure", "neutral_repetition", "Confidence $-$ Neutral"),
]


def as_bool(series: pd.Series) -> pd.Series:
    """Parse repository boolean columns without treating nonempty strings as true."""
    values = series.astype(str).str.strip().str.lower()
    if not values.isin({"true", "false"}).all():
        bad = sorted(values[~values.isin({"true", "false"})].unique())
        raise ValueError(f"Expected complete boolean column; found {bad[:5]}")
    return values.eq("true")


def confusion(frame: pd.DataFrame) -> dict[str, int | float]:
    auto = as_bool(frame["unsupported_assertion"])
    human = as_bool(frame["human_unsupported_assertion"])
    tp = int((auto & human).sum())
    fp = int((auto & ~human).sum())
    fn = int((~auto & human).sum())
    tn = int((~auto & ~human).sum())
    return {
        "n": len(frame),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "sensitivity": tp / (tp + fn),
        "specificity": tn / (tn + fp),
    }


def rogan_gladen(q: float, sensitivity: float, specificity: float) -> float:
    denominator = sensitivity + specificity - 1
    if denominator <= 0:
        return float("nan")
    return float(np.clip((q + specificity - 1) / denominator, 0, 1))


def correction_analysis(
    representative: pd.DataFrame,
    factorial: pd.DataFrame,
    *,
    draws: int = 200_000,
    seed: int = 20260805,
) -> dict:
    """Arm-specific Rogan--Gladen diagnostic with Jeffreys uncertainty."""
    rng = np.random.default_rng(seed)
    result: dict[str, dict] = {"arms": {}}
    draw_cache: dict[str, np.ndarray] = {}

    for arm in ("neutral_repetition", "confidence_pressure"):
        calibration = representative[representative["branch"].eq(arm)]
        target = factorial[factorial["branch"].eq(arm)]
        c = confusion(calibration)
        target_auto = as_bool(target["unsupported_assertion"])
        target_human = as_bool(target["human_unsupported_assertion"])
        q = float(target_auto.mean())
        point = rogan_gladen(q, float(c["sensitivity"]), float(c["specificity"]))

        q_draw = rng.beta(
            int(target_auto.sum()) + 0.5, len(target_auto) - int(target_auto.sum()) + 0.5, draws
        )
        se_draw = rng.beta(int(c["tp"]) + 0.5, int(c["fn"]) + 0.5, draws)
        sp_draw = rng.beta(int(c["tn"]) + 0.5, int(c["fp"]) + 0.5, draws)
        denominator = se_draw + sp_draw - 1
        corrected = np.full(draws, np.nan)
        valid = denominator > 0
        corrected[valid] = np.clip((q_draw[valid] + sp_draw[valid] - 1) / denominator[valid], 0, 1)
        corrected = corrected[np.isfinite(corrected)]
        draw_cache[arm] = corrected
        result["arms"][arm] = {
            "target_n": len(target),
            "target_auto_positive": int(target_auto.sum()),
            "target_auto_rate": q,
            "target_human_positive": int(target_human.sum()),
            "target_human_rate": float(target_human.mean()),
            "calibration": c,
            "corrected_point": point,
            "corrected_median": float(np.median(corrected)),
            "corrected_interval": [
                float(np.quantile(corrected, 0.025)),
                float(np.quantile(corrected, 0.975)),
            ],
            "valid_draw_share": len(corrected) / draws,
        }

    n_common = min(len(draw_cache["confidence_pressure"]), len(draw_cache["neutral_repetition"]))
    delta_draw = (
        draw_cache["confidence_pressure"][:n_common] - draw_cache["neutral_repetition"][:n_common]
    )
    confidence = result["arms"]["confidence_pressure"]
    neutral = result["arms"]["neutral_repetition"]
    result["contrast"] = {
        "name": "Confidence - Neutral",
        "automatic_rd": confidence["target_auto_rate"] - neutral["target_auto_rate"],
        "human_rd": confidence["target_human_rate"] - neutral["target_human_rate"],
        "corrected_point": confidence["corrected_point"] - neutral["corrected_point"],
        "corrected_median": float(np.median(delta_draw)),
        "corrected_interval": [
            float(np.quantile(delta_draw, 0.025)),
            float(np.quantile(delta_draw, 0.975)),
        ],
        "probability_positive": float((delta_draw > 0).mean()),
    }
    result["method"] = {
        "estimator": "arm-specific Rogan-Gladen",
        "uncertainty": "independent Jeffreys-beta draws for target rate, sensitivity, and specificity",
        "draws": draws,
        "seed": seed,
        "caveat": (
            "Post-freeze transport diagnostic; calibration rows are sparse and may overlap the "
            "factorial target sample, so the interval is not a confirmatory confidence interval."
        ),
    }
    return result


def reference_sensitivity(factorial: pd.DataFrame, *, observed_rater_disagreement: float) -> dict:
    """Bound factorial RDs under arm-correlated reference-label error."""
    rates: dict[str, dict[str, int | float]] = {}
    for arm, group in factorial.groupby("branch"):
        if arm not in ARM_LABELS:
            continue
        human = as_bool(group["human_unsupported_assertion"])
        rates[arm] = {
            "n": len(group),
            "positive": int(human.sum()),
            "rate": float(human.mean()),
        }

    epsilon_grid = [0.05, 0.10]
    if not any(math.isclose(observed_rater_disagreement, epsilon) for epsilon in epsilon_grid):
        epsilon_grid.append(observed_rater_disagreement)
    rows = []
    for treatment, comparator, label in CONTRASTS:
        left = rates[treatment]
        right = rates[comparator]
        if left["n"] != right["n"]:
            raise ValueError(f"Unbalanced factorial contrast: {label}")
        n = int(left["n"])
        net = int(left["positive"]) - int(right["positive"])
        rd = net / n
        bounds = {}
        for epsilon in epsilon_grid:
            lower = max(0.0, float(left["rate"]) - epsilon) - min(
                1.0, float(right["rate"]) + epsilon
            )
            upper = min(1.0, float(left["rate"]) + epsilon) - max(
                0.0, float(right["rate"]) - epsilon
            )
            bounds[f"{epsilon:.6f}"] = [lower, upper]
        rows.append(
            {
                "contrast": label,
                "n_pairs": n,
                "rd": rd,
                "minimum_single_label_flips_to_zero": abs(net),
                "share_of_pairs": abs(net) / n,
                "share_of_arm_labels": abs(net) / (2 * n),
                "bounds": bounds,
            }
        )
    return {
        "contrasts": rows,
        "epsilon_grid": epsilon_grid,
        "interpretation": (
            "Each epsilon bounds the fraction of labels that may be wrong separately in each "
            "arm. The additional empirical value is raw primary-secondary disagreement on the "
            "same factorial rows, not an estimated error rate against ground truth."
        ),
    }


def dual_reference_diagnostic(representative: pd.DataFrame, dual: pd.DataFrame) -> dict:
    """Describe primary-secondary disagreement on the representative subset."""
    primary = representative[["record_id", "branch", "human_unsupported_assertion"]].rename(
        columns={"human_unsupported_assertion": "primary"}
    )
    secondary = dual[["record_id", "branch", "human_unsupported_assertion"]].rename(
        columns={"human_unsupported_assertion": "secondary"}
    )
    joined = secondary.merge(primary, on=["record_id", "branch"], validate="one_to_one")
    joined["primary"] = as_bool(joined["primary"])
    joined["secondary"] = as_bool(joined["secondary"])
    by_arm = {}
    for arm, group in joined.groupby("branch"):
        by_arm[arm] = {
            "n": len(group),
            "primary_rate": float(group["primary"].mean()),
            "secondary_rate": float(group["secondary"].mean()),
            "disagreement": float(group["primary"].ne(group["secondary"]).mean()),
        }
    return {
        "n": len(joined),
        "overall_disagreement": float(joined["primary"].ne(joined["secondary"]).mean()),
        "by_arm": by_arm,
    }


def factorial_rater_diagnostic(primary: pd.DataFrame, secondary: pd.DataFrame) -> dict:
    """Compare both unused-family raters on all factorial rows and contrasts."""
    left = primary[["record_id", "branch", "human_unsupported_assertion"]].rename(
        columns={"human_unsupported_assertion": "primary"}
    )
    right = secondary[["record_id", "branch", "human_unsupported_assertion"]].rename(
        columns={"human_unsupported_assertion": "secondary"}
    )
    joined = left.merge(right, on=["record_id", "branch"], validate="one_to_one")
    joined["primary"] = as_bool(joined["primary"])
    joined["secondary"] = as_bool(joined["secondary"])

    by_arm = {}
    for arm, group in joined.groupby("branch"):
        by_arm[arm] = {
            "n": len(group),
            "primary_rate": float(group["primary"].mean()),
            "secondary_rate": float(group["secondary"].mean()),
            "disagreement": float(group["primary"].ne(group["secondary"]).mean()),
        }

    contrasts = []
    for treatment, comparator, label in CONTRASTS:
        treatment_row = by_arm[treatment]
        comparator_row = by_arm[comparator]
        primary_rd = treatment_row["primary_rate"] - comparator_row["primary_rate"]
        secondary_rd = treatment_row["secondary_rate"] - comparator_row["secondary_rate"]
        contrasts.append(
            {
                "contrast": label,
                "n_pairs": treatment_row["n"],
                "primary_rd": primary_rd,
                "secondary_rd": secondary_rd,
                "secondary_minus_primary": secondary_rd - primary_rd,
            }
        )
    return {
        "n": len(joined),
        "overall_disagreement": float(joined["primary"].ne(joined["secondary"]).mean()),
        "by_arm": by_arm,
        "contrasts": contrasts,
    }


def clustered_lpm_heterogeneity(representative: pd.DataFrame) -> dict:
    """Model-fixed-effects LPM with an item-clustered sandwich covariance."""
    frame = representative.copy()
    frame["human"] = as_bool(frame["human_unsupported_assertion"])
    frame["error"] = as_bool(frame["unsupported_assertion"]).astype(int)
    frame = frame[~frame["human"]].copy()
    arms = sorted(frame["branch"].unique())
    models = sorted(frame["model_slug"].unique())
    reference_arm = arms[0]

    columns = ["intercept"]
    parts = [np.ones(len(frame))]
    for arm in arms[1:]:
        columns.append(f"arm::{arm}")
        parts.append(frame["branch"].eq(arm).astype(float).to_numpy())
    for model in models[1:]:
        columns.append(f"model::{model}")
        parts.append(frame["model_slug"].eq(model).astype(float).to_numpy())
    x = np.column_stack(parts)
    y = frame["error"].to_numpy(dtype=float)
    xtx_inv = np.linalg.pinv(x.T @ x)
    beta = xtx_inv @ x.T @ y
    residual = y - x @ beta

    meat = np.zeros((x.shape[1], x.shape[1]))
    for indices in frame.groupby("item_id", sort=False).groups.values():
        positions = frame.index.get_indexer(indices)
        score = x[positions].T @ residual[positions]
        meat += np.outer(score, score)
    n, k = x.shape
    n_clusters = frame["item_id"].nunique()
    correction = (n_clusters / (n_clusters - 1)) * ((n - 1) / (n - k))
    covariance = correction * xtx_inv @ meat @ xtx_inv

    arm_indices = [columns.index(f"arm::{arm}") for arm in arms[1:]]
    arm_beta = beta[arm_indices]
    arm_cov = covariance[np.ix_(arm_indices, arm_indices)]
    statistic = float(arm_beta @ np.linalg.pinv(arm_cov) @ arm_beta)
    global_p = float(chi2.sf(statistic, len(arm_indices)))

    def arm_vector(arm: str) -> np.ndarray:
        vector = np.zeros(len(columns))
        if arm != reference_arm:
            vector[columns.index(f"arm::{arm}")] = 1
        return vector

    pairwise = []
    for left, right in itertools.combinations(arms, 2):
        contrast = arm_vector(left) - arm_vector(right)
        estimate = float(contrast @ beta)
        se = float(np.sqrt(max(contrast @ covariance @ contrast, 0)))
        z = estimate / se if se else math.copysign(float("inf"), estimate)
        p = float(2 * norm.sf(abs(z)))
        pairwise.append(
            {
                "left": left,
                "right": right,
                "adjusted_fpr_difference": estimate,
                "se": se,
                "ci": [estimate - 1.96 * se, estimate + 1.96 * se],
                "p": p,
            }
        )

    order = np.argsort([row["p"] for row in pairwise])
    adjusted = np.empty(len(pairwise))
    running = 0.0
    total = len(pairwise)
    for rank, index in enumerate(order):
        candidate = min(1.0, (total - rank) * pairwise[index]["p"])
        running = max(running, candidate)
        adjusted[index] = running
    for row, value in zip(pairwise, adjusted, strict=True):
        row["holm_p"] = float(value)

    observed_fprs = {}
    for arm, group in frame.groupby("branch"):
        observed_fprs[arm] = {
            "human_negative_n": len(group),
            "false_positive": int(group["error"].sum()),
            "fpr": float(group["error"].mean()),
        }

    return {
        "n_human_negative": len(frame),
        "n_item_clusters": n_clusters,
        "n_models_fixed": len(models),
        "reference_arm": reference_arm,
        "global_wald_chi2": statistic,
        "global_df": len(arm_indices),
        "global_p": global_p,
        "observed_fprs": observed_fprs,
        "pairwise": pairwise,
        "model": (
            "Linear probability model among reference-negative rows, arm and model fixed effects, "
            "item-clustered CR1 sandwich covariance; exploratory post-freeze test."
        ),
    }


def independent_power(heterogeneity: dict) -> dict:
    """Normal-approximation sample sizes, with transparent design-effect scenarios."""

    def n_per_arm(p1: float, p2: float) -> int:
        effect = abs(2 * math.asin(math.sqrt(p1)) - 2 * math.asin(math.sqrt(p2)))
        raw = 2 * (norm.ppf(0.975) + norm.ppf(0.80)) ** 2 / effect**2
        return math.ceil(raw)

    observed = sorted(arm["fpr"] for arm in heterogeneity["observed_fprs"].values())
    scenarios = [
        ("Observed extreme", observed[0], observed[-1]),
        ("10-point difference", 0.20, 0.30),
        ("15-point difference", 0.20, 0.35),
        ("20-point difference", 0.20, 0.40),
    ]
    rows = []
    for label, p1, p2 in scenarios:
        independent_n = n_per_arm(p1, p2)
        rows.append(
            {
                "scenario": label,
                "p1": p1,
                "p2": p2,
                "independent_n_per_arm": independent_n,
                "n_with_model_cluster_design_effect": {
                    f"rho={rho:.2f}": math.ceil(independent_n * (1 + 7 * rho))
                    for rho in (0.05, 0.10, 0.20)
                },
            }
        )
    return {
        "alpha": 0.05,
        "power": 0.80,
        "model_cluster_size": 8,
        "scenarios": rows,
        "caveat": (
            "Planning approximations assume two equal independent proportions; design-effect "
            "rows are sensitivity calculations, not an estimated ICC or retrospective power proof."
        ),
    }


def tex_number(value: float, digits: int = 3, signed: bool = False) -> str:
    sign = "+" if signed and value >= 0 else ""
    return f"{sign}{value:.{digits}f}"


def write_tabular(path_stem: Path, rows: list[dict], columns: list[str]) -> list[Path]:
    """Write a table as CSV and Markdown; return written paths."""
    path_stem.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows, columns=columns)
    csv_path = path_stem.with_suffix(".csv")
    md_path = path_stem.with_suffix(".md")
    frame.to_csv(csv_path, index=False)
    header = "| " + " | ".join(columns) + " |"
    sep = "| " + " | ".join("---" for _ in columns) + " |"
    body = [
        "| "
        + " | ".join("" if row.get(col) is None else str(row.get(col)) for col in columns)
        + " |"
        for row in rows
    ]
    md_path.write_text("\n".join([header, sep, *body]) + "\n", encoding="utf-8")
    return [csv_path, md_path]


def write_tables(payload: dict) -> list[Path]:
    written: list[Path] = []
    correction = payload["arm_correction"]
    correction_rows = []
    for arm in ("neutral_repetition", "confidence_pressure"):
        row = correction["arms"][arm]
        c = row["calibration"]
        interval = row["corrected_interval"]
        correction_rows.append(
            {
                "arm": ARM_LABELS[arm],
                "auto_rate": f"{row['target_auto_rate']:.3f}",
                "ref_rate": f"{row['target_human_rate']:.3f}",
                "sensitivity": f"{c['sensitivity']:.3f}",
                "specificity": f"{c['specificity']:.3f}",
                "corrected_point": f"{row['corrected_point']:.3f}",
                "corrected_lo": f"{interval[0]:.3f}",
                "corrected_hi": f"{interval[1]:.3f}",
            }
        )
    contrast = correction["contrast"]
    interval = contrast["corrected_interval"]
    correction_rows.append(
        {
            "arm": "Confidence - Neutral",
            "auto_rate": f"{contrast['automatic_rd']:+.3f}",
            "ref_rate": f"{contrast['human_rd']:+.3f}",
            "sensitivity": "",
            "specificity": "",
            "corrected_point": f"{contrast['corrected_point']:+.3f}",
            "corrected_lo": f"{interval[0]:+.3f}",
            "corrected_hi": f"{interval[1]:+.3f}",
        }
    )
    written.extend(
        write_tabular(
            CORRECTION_TABLE,
            correction_rows,
            [
                "arm",
                "auto_rate",
                "ref_rate",
                "sensitivity",
                "specificity",
                "corrected_point",
                "corrected_lo",
                "corrected_hi",
            ],
        )
    )

    reference_rows = []
    for row in payload["reference_sensitivity"]["contrasts"]:
        bound = row["bounds"]["0.050000"]
        reference_rows.append(
            {
                "contrast": row["contrast"],
                "primary_rd": f"{row['rd']:+.3f}",
                "flips_to_zero": row["minimum_single_label_flips_to_zero"],
                "pct_labels": f"{100 * row['share_of_arm_labels']:.1f}",
                "rd_bound_lo_eps05": f"{bound[0]:+.3f}",
                "rd_bound_hi_eps05": f"{bound[1]:+.3f}",
            }
        )
    written.extend(
        write_tabular(
            REFERENCE_TABLE,
            reference_rows,
            [
                "contrast",
                "primary_rd",
                "flips_to_zero",
                "pct_labels",
                "rd_bound_lo_eps05",
                "rd_bound_hi_eps05",
            ],
        )
    )

    rater_rows = []
    for row in payload["factorial_rater_sensitivity"]["contrasts"]:
        rater_rows.append(
            {
                "contrast": row["contrast"],
                "n_pairs": row["n_pairs"],
                "primary_rd": f"{row['primary_rd']:+.3f}",
                "secondary_rd": f"{row['secondary_rd']:+.3f}",
                "secondary_minus_primary": (f"{row['secondary_minus_primary']:+.3f}"),
            }
        )
    written.extend(
        write_tabular(
            RATER_TABLE,
            rater_rows,
            [
                "contrast",
                "n_pairs",
                "primary_rd",
                "secondary_rd",
                "secondary_minus_primary",
            ],
        )
    )

    heterogeneity = payload["heterogeneity"]
    observed_power = payload["power"]["scenarios"][0]
    smallest_pair = min(heterogeneity["pairwise"], key=lambda row: row["holm_p"])
    hetero_rows = [
        {
            "diagnostic": "Arm omnibus",
            "result": (
                f"chi2_{heterogeneity['global_df']}="
                f"{heterogeneity['global_wald_chi2']:.2f}, p={heterogeneity['global_p']:.4f}"
            ),
            "interpretation": "Model FE; item-clustered",
        },
        {
            "diagnostic": "Strongest pair",
            "result": (
                f"{ARM_LABELS.get(smallest_pair['left'], smallest_pair['left'])} - "
                f"{ARM_LABELS.get(smallest_pair['right'], smallest_pair['right'])}: "
                f"{smallest_pair['adjusted_fpr_difference']:+.3f} "
                f"(Holm p={smallest_pair['holm_p']:.4f})"
            ),
            "interpretation": "Exploratory, 15 pairs",
        },
        {
            "diagnostic": "Observed-extreme planning",
            "result": f"{observed_power['independent_n_per_arm']} negatives/arm",
            "interpretation": "Independent approximation",
        },
        {
            "diagnostic": "10-point planning",
            "result": f"{payload['power']['scenarios'][1]['independent_n_per_arm']} negatives/arm",
            "interpretation": "Independent approximation",
        },
    ]
    written.extend(
        write_tabular(
            HETEROGENEITY_TABLE,
            hetero_rows,
            ["diagnostic", "result", "interpretation"],
        )
    )
    return written


def main() -> None:
    representative = pd.read_csv(REPRESENTATIVE)
    dual = pd.read_csv(REPRESENTATIVE_DUAL)
    factorial = pd.read_csv(FACTORIAL)
    factorial_secondary = pd.read_csv(FACTORIAL_SECONDARY)
    factorial = factorial[
        factorial["branch"].isin(ARM_LABELS)
        & factorial["human_unsupported_assertion"].astype(str).str.lower().isin({"true", "false"})
    ].copy()
    factorial_secondary = factorial_secondary[
        factorial_secondary["branch"].isin(ARM_LABELS)
        & factorial_secondary["human_unsupported_assertion"]
        .astype(str)
        .str.lower()
        .isin({"true", "false"})
    ].copy()
    factorial_raters = factorial_rater_diagnostic(factorial, factorial_secondary)
    heterogeneity = clustered_lpm_heterogeneity(representative)

    payload = {
        "sources": {
            "representative": str(REPRESENTATIVE.relative_to(REPO_ROOT)),
            "representative_dual": str(REPRESENTATIVE_DUAL.relative_to(REPO_ROOT)),
            "factorial": str(FACTORIAL.relative_to(REPO_ROOT)),
            "factorial_secondary": str(FACTORIAL_SECONDARY.relative_to(REPO_ROOT)),
        },
        "arm_correction": correction_analysis(representative, factorial),
        "reference_sensitivity": reference_sensitivity(
            factorial,
            observed_rater_disagreement=factorial_raters["overall_disagreement"],
        ),
        "dual_reference": dual_reference_diagnostic(representative, dual),
        "factorial_rater_sensitivity": factorial_raters,
        "heterogeneity": heterogeneity,
        "power": independent_power(heterogeneity),
    }
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    written = write_tables(payload)
    print(f"Wrote {OUTPUT_JSON.relative_to(PAPER_DIR)}")
    for path in written:
        print(f"Wrote {path.relative_to(PAPER_DIR)}")


if __name__ == "__main__":
    main()
