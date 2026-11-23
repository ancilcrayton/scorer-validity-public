#!/usr/bin/env python3
"""Regenerate scorer-paper audit results from the frozen local release data."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import fisher_exact

PAPER_DIR = Path(__file__).resolve().parent
REPO_ROOT = PAPER_DIR.parent
DATA_ROOT = REPO_ROOT / "data" / "confirmatory_v1"
AUDIT_ROOT = DATA_ROOT / "human_validation"
RESULTS_ROOT = REPO_ROOT / "results" / "confirmatory_v1" / "statistics"
TABLES_ROOT = PAPER_DIR / "tables"

REPRESENTATIVE = AUDIT_ROOT / "representative_arm_audit.csv"
REPRESENTATIVE_DUAL = AUDIT_ROOT / "representative_arm_audit_dual.csv"
FACTORIAL = AUDIT_ROOT / "factorial_paired_audit_expanded.csv"
FACTORIAL_DUAL = AUDIT_ROOT / "factorial_paired_audit_expanded_secondary_full.csv"
HARD = AUDIT_ROOT / "hard_audit_primary.csv"
PAIRED_H3 = AUDIT_ROOT / "paired_h3_audit.csv"
GASLIGHT = AUDIT_ROOT / "gaslight_scorer_audit.csv"
GASLIGHT_DUAL = AUDIT_ROOT / "gaslight_scorer_audit_dual.csv"
SYCON = AUDIT_ROOT / "sycon_judge_audit.csv"
SYCON_DUAL = AUDIT_ROOT / "sycon_judge_audit_dual.csv"
ALTERNATIVE = DATA_ROOT / "alternative_judge" / "representative_predictions.csv"
EXISTENCE_TAXONOMY = DATA_ROOT / "derived" / "existence_fp_taxonomy.csv"

OUTPUT_JSON = PAPER_DIR / "data" / "scorer_results.json"
REPRESENTATIVE_JSON = RESULTS_ROOT / "representative_arm_audit.json"

ARM_ORDER = [
    "spontaneous_baseline",
    "cue_baseline",
    "neutral_repetition",
    "existence_assertion",
    "confidence_pressure",
    "authority_pressure",
]
ARM_LABELS = {
    "spontaneous_baseline": "Spontaneous",
    "cue_baseline": "Soft cue",
    "neutral_repetition": "Neutral",
    "existence_assertion": "Existence",
    "confidence_pressure": "Confidence",
    "authority_pressure": "Authority",
    "certainty_only": "Certainty-only",
    "existence_directness": "Existence x Directness",
}
FACTORIAL_CONTRASTS = [
    ("certainty_only", "neutral_repetition", "Certainty-only - Neutral"),
    (
        "confidence_pressure",
        "existence_directness",
        "Confidence - Existence x Directness",
    ),
    ("confidence_pressure", "neutral_repetition", "Confidence - Neutral"),
]


def binary(series: pd.Series, *, name: str = "binary field") -> pd.Series:
    """Parse complete bool or 0/1 values without Python string truthiness."""
    values = series.astype(str).str.strip().str.lower()
    mapping = {
        "true": True,
        "false": False,
        "1": True,
        "0": False,
        "yes": True,
        "no": False,
    }
    if not values.isin(mapping).all():
        bad = sorted(values[~values.isin(mapping)].unique())
        raise ValueError(f"{name} contains invalid values: {bad[:5]}")
    return values.map(mapping).astype(bool)


def safe_ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def confusion(
    frame: pd.DataFrame,
    *,
    truth: str = "human_unsupported_assertion",
    prediction: str = "unsupported_assertion",
) -> dict[str, int | float | None]:
    y = binary(frame[truth], name=truth)
    pred = binary(frame[prediction], name=prediction)
    tp = int((pred & y).sum())
    fp = int((pred & ~y).sum())
    fn = int((~pred & y).sum())
    tn = int((~pred & ~y).sum())
    precision = safe_ratio(tp, tp + fp)
    recall = safe_ratio(tp, tp + fn)
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and precision + recall
        else None
    )
    return {
        "n": len(frame),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "agreement": (tp + tn) / len(frame) if len(frame) else None,
        "fpr": safe_ratio(fp, fp + tn),
        "sensitivity": recall,
        "specificity": safe_ratio(tn, tn + fp),
    }


def wilson_interval(k: int, n: int, z: float = 1.96) -> list[float] | None:
    if n <= 0:
        return None
    p = k / n
    denominator = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denominator
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denominator
    return [center - half, center + half]


def kappa(left: pd.Series, right: pd.Series) -> float | None:
    a = binary(left)
    b = binary(right)
    observed = float(a.eq(b).mean())
    expected = float(a.mean() * b.mean() + (1 - a.mean()) * (1 - b.mean()))
    return None if expected == 1 else (observed - expected) / (1 - expected)


def agreement(
    primary: pd.DataFrame, secondary: pd.DataFrame, *, by: str = "branch"
) -> dict[str, Any]:
    left = primary[["record_id", by, "human_unsupported_assertion"]].rename(
        columns={"human_unsupported_assertion": "primary"}
    )
    right = secondary[["record_id", "human_unsupported_assertion"]].rename(
        columns={"human_unsupported_assertion": "secondary"}
    )
    joined = left.merge(right, on="record_id", validate="one_to_one")
    joined["primary"] = binary(joined["primary"])
    joined["secondary"] = binary(joined["secondary"])
    by_group: dict[str, dict[str, int | float | None]] = {}
    for value, group in joined.groupby(by, sort=True):
        by_group[str(value)] = {
            "n": len(group),
            "agree_n": int(group["primary"].eq(group["secondary"]).sum()),
            "disagree_n": int(group["primary"].ne(group["secondary"]).sum()),
            "agreement": float(group["primary"].eq(group["secondary"]).mean()),
            "kappa": kappa(group["primary"], group["secondary"]),
            "primary_rate": float(group["primary"].mean()),
            "secondary_rate": float(group["secondary"].mean()),
            "disagreement": float(group["primary"].ne(group["secondary"]).mean()),
        }
    return {
        "n": len(joined),
        "agree_n": int(joined["primary"].eq(joined["secondary"]).sum()),
        "disagree_n": int(joined["primary"].ne(joined["secondary"]).sum()),
        "agreement": float(joined["primary"].eq(joined["secondary"]).mean()),
        "kappa": kappa(joined["primary"], joined["secondary"]),
        "disagreement": float(joined["primary"].ne(joined["secondary"]).mean()),
        f"by_{by}": by_group,
    }


def paired_contrast(
    frame: pd.DataFrame,
    treatment: str,
    comparator: str,
    label: str,
    *,
    seed: int,
    draws: int,
) -> dict[str, Any]:
    subset = frame[frame["branch"].isin([treatment, comparator])].copy()
    subset["_label"] = binary(subset[label], name=label).astype(int)
    wide = subset.pivot_table(
        index=["item_id", "model_slug"],
        columns="branch",
        values="_label",
        aggfunc="first",
    ).dropna(subset=[treatment, comparator])
    differences = (wide[treatment] - wide[comparator]).rename("difference").reset_index()
    clusters = {
        key: group["difference"].to_numpy(dtype=float)
        for key, group in differences.groupby("item_id")
    }
    if len(clusters) < 2:
        interval = [None, None]
    else:
        keys = list(clusters)
        rng = np.random.default_rng(seed)
        # Resample item clusters and pool the keys inside each draw. This keeps the
        # bootstrap target equal to the key-weighted point estimate; averaging the
        # cluster means instead would silently weight sparse items more heavily.
        bootstrap = np.asarray(
            [
                float(
                    np.concatenate(
                        [clusters[key] for key in rng.choice(keys, size=len(keys), replace=True)]
                    ).mean()
                )
                for _ in range(draws)
            ]
        )
        interval = [float(value) for value in np.quantile(bootstrap, [0.025, 0.975])]
    return {
        "treatment": treatment,
        "comparator": comparator,
        "n_pairs": len(wide),
        "n_item_clusters": int(differences["item_id"].nunique()),
        "treatment_rate": float(wide[treatment].mean()),
        "comparator_rate": float(wide[comparator].mean()),
        "risk_difference": float(differences["difference"].mean()),
        "cluster_bootstrap_interval": interval,
        "bootstrap_draws": draws,
        "seed": seed,
    }


def paired_contrast_difference(
    frame: pd.DataFrame,
    treatment: str,
    comparator: str,
    *,
    automatic_label: str,
    reference_label: str,
    seed: int,
    draws: int,
) -> dict[str, Any]:
    """Estimate how much automatic scoring moves a paired contrast.

    For each item--model key we subtract the reference-rater contrast from the
    automatic contrast. Positive values mean the automatic scorer overstates
    the treatment effect relative to the reference rater.
    """
    subset = frame[frame["branch"].isin([treatment, comparator])].copy()
    subset["_automatic"] = binary(subset[automatic_label], name=automatic_label).astype(int)
    subset["_reference"] = binary(subset[reference_label], name=reference_label).astype(int)
    auto = subset.pivot_table(
        index=["item_id", "model_slug"],
        columns="branch",
        values="_automatic",
        aggfunc="first",
    ).dropna(subset=[treatment, comparator])
    reference = subset.pivot_table(
        index=["item_id", "model_slug"],
        columns="branch",
        values="_reference",
        aggfunc="first",
    ).dropna(subset=[treatment, comparator])
    keys = auto.index.intersection(reference.index)
    auto_difference = auto.loc[keys, treatment] - auto.loc[keys, comparator]
    reference_difference = reference.loc[keys, treatment] - reference.loc[keys, comparator]
    differences = (auto_difference - reference_difference).rename("difference").reset_index()
    clusters = {
        key: group["difference"].to_numpy(dtype=float)
        for key, group in differences.groupby("item_id")
    }
    if len(clusters) < 2:
        interval = [None, None]
    else:
        cluster_keys = list(clusters)
        rng = np.random.default_rng(seed)
        bootstrap = np.asarray(
            [
                float(
                    np.concatenate(
                        [
                            clusters[key]
                            for key in rng.choice(cluster_keys, size=len(cluster_keys), replace=True)
                        ]
                    ).mean()
                )
                for _ in range(draws)
            ]
        )
        interval = [float(value) for value in np.quantile(bootstrap, [0.025, 0.975])]
    return {
        "treatment": treatment,
        "comparator": comparator,
        "n_pairs": len(keys),
        "n_item_clusters": len(clusters),
        "automatic_risk_difference": float(auto_difference.mean()),
        "reference_risk_difference": float(reference_difference.mean()),
        "difference": float(differences["difference"].mean()),
        "cluster_bootstrap_interval": interval,
        "bootstrap_draws": draws,
        "seed": seed,
    }


def representative_analysis(
    representative: pd.DataFrame,
    representative_dual: pd.DataFrame,
    hard: pd.DataFrame,
) -> tuple[dict[str, Any], dict[str, Any]]:
    by_arm: dict[str, dict[str, Any]] = {}
    hard_by_arm: dict[str, dict[str, Any]] = {}
    for arm in ARM_ORDER:
        group = representative[representative["branch"].eq(arm)]
        metrics = confusion(group)
        metrics["precision_interval"] = wilson_interval(
            int(metrics["tp"]), int(metrics["tp"]) + int(metrics["fp"])
        )
        metrics["fpr_interval"] = wilson_interval(
            int(metrics["fp"]), int(metrics["fp"]) + int(metrics["tn"])
        )
        metrics["signed_bias"] = (int(metrics["fp"]) - int(metrics["fn"])) / len(group)
        by_arm[arm] = metrics

        hard_group = hard[hard["branch"].eq(arm)]
        hard_metrics = confusion(hard_group)
        hard_metrics["precision_interval"] = wilson_interval(
            int(hard_metrics["tp"]), int(hard_metrics["tp"]) + int(hard_metrics["fp"])
        )
        hard_by_arm[arm] = hard_metrics

    dual = agreement(representative, representative_dual)

    def arm_rates(arm: str) -> dict[str, float]:
        metrics = by_arm[arm]
        return {
            "automatic": (metrics["tp"] + metrics["fp"]) / metrics["n"],
            "primary_rater": (metrics["tp"] + metrics["fn"]) / metrics["n"],
            "signed_bias": metrics["signed_bias"],
        }

    rates = {arm: arm_rates(arm) for arm in ARM_ORDER}
    unpaired_diagnostics = {}
    for treatment, comparator, name in (
        ("authority_pressure", "existence_assertion", "Authority - Existence"),
        ("confidence_pressure", "neutral_repetition", "Confidence - Neutral"),
    ):
        unpaired_diagnostics[name] = {
            "automatic_rd": (rates[treatment]["automatic"] - rates[comparator]["automatic"]),
            "primary_rater_rd": (
                rates[treatment]["primary_rater"] - rates[comparator]["primary_rater"]
            ),
            "bias_difference": (rates[treatment]["signed_bias"] - rates[comparator]["signed_bias"]),
        }
    authority = by_arm["authority_pressure"]
    existence = by_arm["existence_assertion"]
    _, authority_existence_fpr_p = fisher_exact(
        [
            [authority["fp"], authority["tn"]],
            [existence["fp"], existence["tn"]],
        ],
        alternative="two-sided",
    )
    current = {
        "status": "complete",
        "n_labeled": len(representative),
        "overall": confusion(representative),
        "by_arm": by_arm,
        "hard_oversampled_550_by_arm": hard_by_arm,
        "dual": {
            "n": dual["n"],
            "agreement": dual["agreement"],
            "kappa": dual["kappa"],
        },
        "unpaired_diagnostics": unpaired_diagnostics,
        "authority_existence_fpr_fisher_two_sided_p": float(authority_existence_fpr_p),
        "sampling": "representative arm x model",
        "primary_rater": "Mistral Large 3 2512",
        "secondary_rater": "MiniMax M3",
    }
    return current, dual


def hard_analysis(hard: pd.DataFrame, representative: dict[str, Any]) -> dict[str, Any]:
    routed = hard["scoring_source"].astype(str).str.contains("judge", case=False, na=False)
    routes = {
        "heuristic_only": confusion(hard[~routed]),
        "routed_llm_judge": confusion(hard[routed]),
        "pooled": confusion(hard),
    }
    for metrics in routes.values():
        metrics["share"] = int(metrics["n"]) / len(hard)

    by_arm = {str(arm): confusion(group) for arm, group in hard.groupby("branch", sort=True)}
    sampling = {}
    for arm in ARM_ORDER:
        hard_metrics = by_arm[arm]
        rep_metrics = representative["by_arm"][arm]
        hard_denominator = int(hard_metrics["tp"]) + int(hard_metrics["fp"])
        rep_denominator = int(rep_metrics["tp"]) + int(rep_metrics["fp"])
        sampling[arm] = {
            "hard": {
                **hard_metrics,
                "precision_interval": wilson_interval(int(hard_metrics["tp"]), hard_denominator),
            },
            "representative": {
                **rep_metrics,
                "precision_interval": wilson_interval(int(rep_metrics["tp"]), rep_denominator),
            },
        }

    def unpaired(column: str) -> dict[str, float]:
        rates = {
            arm: float(binary(hard.loc[hard["branch"].eq(arm), column]).mean())
            for arm in ("authority_pressure", "existence_assertion")
        }
        return {
            "authority_rate": rates["authority_pressure"],
            "existence_rate": rates["existence_assertion"],
            "authority_minus_existence": (
                rates["authority_pressure"] - rates["existence_assertion"]
            ),
        }

    return {
        "overall": confusion(hard),
        "routes": routes,
        "by_arm": by_arm,
        "six_arm_rows": int(hard["branch"].isin(ARM_ORDER).sum()),
        "sampling_comparison": sampling,
        "authority_existence_unpaired": {
            "automatic": unpaired("unsupported_assertion"),
            "primary_rater": unpaired("human_unsupported_assertion"),
        },
        "interpretation": "Stress sample; route and arm metrics are descriptive, not causal.",
    }


def factorial_analysis(
    primary: pd.DataFrame, secondary: pd.DataFrame
) -> tuple[dict[str, Any], dict[str, Any]]:
    contrasts: dict[str, Any] = {}
    for treatment, comparator, name in FACTORIAL_CONTRASTS:
        contrasts[name] = {
            "automatic": paired_contrast(
                primary,
                treatment,
                comparator,
                "unsupported_assertion",
                seed=20260804,
                draws=2000,
            ),
            "primary_rater": paired_contrast(
                primary,
                treatment,
                comparator,
                "human_unsupported_assertion",
                seed=20260804,
                draws=2000,
            ),
            "secondary_rater": paired_contrast(
                secondary,
                treatment,
                comparator,
                "human_unsupported_assertion",
                seed=20260804,
                draws=2000,
            ),
            "difference": paired_contrast_difference(
                primary,
                treatment,
                comparator,
                automatic_label="unsupported_assertion",
                reference_label="human_unsupported_assertion",
                seed=20260804,
                draws=2000,
            ),
        }
    dual = agreement(primary, secondary)
    return {
        "n_rows": len(primary),
        "n_keys": int(primary[["item_id", "model_slug"]].drop_duplicates().shape[0]),
        "contrasts": contrasts,
        "dual_rater": dual,
    }, dual


def h3_analysis(frame: pd.DataFrame) -> dict[str, Any]:
    return {
        "automatic": paired_contrast(
            frame,
            "authority_pressure",
            "existence_assertion",
            "unsupported_assertion",
            seed=2,
            draws=4000,
        ),
        "primary_rater": paired_contrast(
            frame,
            "authority_pressure",
            "existence_assertion",
            "human_unsupported_assertion",
            seed=2,
            draws=4000,
        ),
        "decision": "quarantine: comparator changes the construct",
    }


def alternative_analysis(representative: pd.DataFrame, alternative: pd.DataFrame) -> dict[str, Any]:
    joined = representative.merge(
        alternative,
        on=["record_id", "model_slug", "item_id", "branch"],
        validate="one_to_one",
    )
    joined["pipeline"] = binary(joined["unsupported_assertion"])
    joined["reference"] = binary(joined["human_unsupported_assertion"])
    joined["alternative"] = binary(joined["alternative_unsupported_assertion"])
    by_arm: dict[str, Any] = {}
    for arm in ARM_ORDER:
        group = joined[joined["branch"].eq(arm)].copy()
        group["pipeline_prediction"] = group["pipeline"]
        group["alternative_prediction"] = group["alternative"]
        pipeline_metrics = confusion(
            group,
            truth="reference",
            prediction="pipeline_prediction",
        )
        alternative_metrics = confusion(
            group,
            truth="reference",
            prediction="alternative_prediction",
        )
        by_arm[arm] = {
            "pipeline": pipeline_metrics,
            "alternative": alternative_metrics,
            "alternative_reference_agreement": float(
                group["alternative"].eq(group["reference"]).mean()
            ),
        }
    joined["alternative_prediction"] = joined["alternative"]
    overall = confusion(
        joined,
        truth="reference",
        prediction="alternative_prediction",
    )
    return {
        "n": len(joined),
        "model": str(joined["alternative_judge_model"].iloc[0]),
        "pipeline_alternative_agree_n": int(joined["pipeline"].eq(joined["alternative"]).sum()),
        "pipeline_alternative_agreement": float(
            joined["pipeline"].eq(joined["alternative"]).mean()
        ),
        "alternative_reference_agree_n": int(joined["alternative"].eq(joined["reference"]).sum()),
        "alternative_reference_agreement": float(
            joined["alternative"].eq(joined["reference"]).mean()
        ),
        "overall_vs_primary_rater": overall,
        "by_arm": by_arm,
        "interpretation": "Correlated alternative automatic scorer, not an audit rater.",
    }


def external_analysis(
    gaslight: pd.DataFrame,
    gaslight_dual: pd.DataFrame,
    sycon: pd.DataFrame,
    sycon_dual: pd.DataFrame,
) -> dict[str, Any]:
    gaslight_by_arm = {
        str(arm): confusion(
            group,
            truth="human_unsupported_assertion",
            prediction="auto_incorrect",
        )
        for arm, group in gaslight.groupby("branch", sort=True)
    }
    gaslight_result = {
        "overall": confusion(
            gaslight,
            truth="human_unsupported_assertion",
            prediction="auto_incorrect",
        ),
        "by_arm": gaslight_by_arm,
        "dual_rater": agreement(gaslight, gaslight_dual),
    }

    sycon_by_trajectory = {
        str(trajectory): confusion(
            group,
            truth="human_unsupported_assertion",
            prediction="auto_accepts",
        )
        for trajectory, group in sycon.groupby("trajectory", sort=True)
    }
    sycon_work = sycon.copy()
    sycon_work["_reference"] = binary(sycon_work["human_unsupported_assertion"]).astype(int)
    ever = (
        sycon_work.groupby(["topic_id", "model_slug", "trajectory"])["_reference"]
        .max()
        .reset_index(name="ever_accept")
    )
    ever_accept: dict[str, Any] = {}
    for trajectory, group in ever.groupby("trajectory", sort=True):
        positives = int(group["ever_accept"].sum())
        ever_accept[str(trajectory)] = {
            "n": len(group),
            "positive": positives,
            "rate": float(group["ever_accept"].mean()),
            "wilson_interval": wilson_interval(positives, len(group)),
        }
    sycon_result = {
        "overall": confusion(
            sycon,
            truth="human_unsupported_assertion",
            prediction="auto_accepts",
        ),
        "by_trajectory": sycon_by_trajectory,
        "primary_rater_ever_accept": ever_accept,
        "dual_rater": agreement(sycon, sycon_dual, by="trajectory"),
    }
    return {"gaslight": gaslight_result, "sycon": sycon_result}


def taxonomy_analysis(frame: pd.DataFrame) -> dict[str, Any]:
    counts = frame.groupby(["category", "scorer"]).size().unstack(fill_value=0).sort_index()
    rows = []
    for category in (
        "hypothetical_or_speculative_completion",
        "hypothetical_abstention_or_needs_context",
        "referent_substitution",
    ):
        rows.append(
            {
                "category": category,
                "automatic_pipeline": int(
                    counts.loc[category, "automatic_pipeline"]
                    if category in counts.index and "automatic_pipeline" in counts.columns
                    else 0
                ),
                "alternative_automatic_judge": int(
                    counts.loc[category, "alternative_automatic_judge"]
                    if category in counts.index and "alternative_automatic_judge" in counts.columns
                    else 0
                ),
            }
        )
    return {"n": len(frame), "categories": rows}


def display(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        return f"{value:.6f}".rstrip("0").rstrip(".")
    if isinstance(value, (list, dict)):
        return json.dumps(value, sort_keys=True)
    return str(value)


def write_table(name: str, rows: list[dict[str, Any]], columns: list[str]) -> None:
    TABLES_ROOT.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows, columns=columns)
    frame.to_csv(TABLES_ROOT / f"{name}.csv", index=False, float_format="%.9f")
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    body = [
        "| " + " | ".join(display(row.get(column)) for column in columns) + " |" for row in rows
    ]
    (TABLES_ROOT / f"{name}.md").write_text(
        "\n".join([header, separator, *body]) + "\n",
        encoding="utf-8",
    )


def write_tables(payload: dict[str, Any]) -> None:
    representative_rows = []
    for arm in ARM_ORDER:
        metrics = payload["representative"]["by_arm"][arm]
        representative_rows.append(
            {
                "arm": ARM_LABELS[arm],
                "n": metrics["n"],
                "tp": metrics["tp"],
                "fp": metrics["fp"],
                "fn": metrics["fn"],
                "tn": metrics["tn"],
                "precision": metrics["precision"],
                "precision_ci_low": metrics["precision_interval"][0],
                "precision_ci_high": metrics["precision_interval"][1],
                "fpr": metrics["fpr"],
                "fpr_ci_low": metrics["fpr_interval"][0],
                "fpr_ci_high": metrics["fpr_interval"][1],
                "signed_bias": metrics["signed_bias"],
            }
        )
    write_table(
        "representative_audit",
        representative_rows,
        list(representative_rows[0]),
    )

    hard_rows = []
    for route, label in (
        ("heuristic_only", "Heuristic-only"),
        ("routed_llm_judge", "Routed LLM judge"),
        ("pooled", "Pooled"),
    ):
        metrics = payload["hard_audit"]["routes"][route]
        hard_rows.append(
            {
                "route": label,
                "n": metrics["n"],
                "share": metrics["share"],
                "tp": metrics["tp"],
                "fp": metrics["fp"],
                "fn": metrics["fn"],
                "tn": metrics["tn"],
                "precision": metrics["precision"],
                "recall": metrics["recall"],
                "f1": metrics["f1"],
            }
        )
    write_table("hard_audit_routing", hard_rows, list(hard_rows[0]))

    sampling_rows = []
    for arm in ARM_ORDER:
        item = payload["hard_audit"]["sampling_comparison"][arm]
        sampling_rows.append(
            {
                "arm": ARM_LABELS[arm],
                "hard_n": item["hard"]["n"],
                "hard_precision": item["hard"]["precision"],
                "hard_ci_low": item["hard"]["precision_interval"][0],
                "hard_ci_high": item["hard"]["precision_interval"][1],
                "representative_n": item["representative"]["n"],
                "representative_precision": item["representative"]["precision"],
                "representative_ci_low": item["representative"]["precision_interval"][0],
                "representative_ci_high": item["representative"]["precision_interval"][1],
            }
        )
    write_table("sampling_shift", sampling_rows, list(sampling_rows[0]))

    factorial_rows = []
    for name, result in payload["factorial"]["contrasts"].items():
        factorial_rows.append(
            {
                "contrast": name,
                "n_pairs": result["primary_rater"]["n_pairs"],
                "automatic_rd": result["automatic"]["risk_difference"],
                "primary_rater_rd": result["primary_rater"]["risk_difference"],
                "primary_ci_low": result["primary_rater"]["cluster_bootstrap_interval"][0],
                "primary_ci_high": result["primary_rater"]["cluster_bootstrap_interval"][1],
                "secondary_rater_rd": result["secondary_rater"]["risk_difference"],
                "difference": result["difference"]["difference"],
                "difference_ci_low": result["difference"]["cluster_bootstrap_interval"][0],
                "difference_ci_high": result["difference"]["cluster_bootstrap_interval"][1],
            }
        )
    write_table("factorial_same_key", factorial_rows, list(factorial_rows[0]))

    h3 = payload["paired_h3"]
    h3_rows = [
        {
            "contrast": "Authority - Existence",
            "n_pairs": h3["primary_rater"]["n_pairs"],
            "automatic_rd": h3["automatic"]["risk_difference"],
            "primary_rater_rd": h3["primary_rater"]["risk_difference"],
            "primary_ci_low": h3["primary_rater"]["cluster_bootstrap_interval"][0],
            "primary_ci_high": h3["primary_rater"]["cluster_bootstrap_interval"][1],
            "decision": h3["decision"],
        }
    ]
    write_table("paired_h3", h3_rows, list(h3_rows[0]))

    alternative_rows = []
    for arm in ARM_ORDER:
        result = payload["alternative_judge"]["by_arm"][arm]
        alternative_rows.append(
            {
                "arm": ARM_LABELS[arm],
                "pipeline_tp": result["pipeline"]["tp"],
                "pipeline_predicted_positive": (
                    result["pipeline"]["tp"] + result["pipeline"]["fp"]
                ),
                "pipeline_precision": result["pipeline"]["precision"],
                "alternative_tp": result["alternative"]["tp"],
                "alternative_predicted_positive": (
                    result["alternative"]["tp"] + result["alternative"]["fp"]
                ),
                "alternative_precision": result["alternative"]["precision"],
                "alternative_reference_agreement": result["alternative_reference_agreement"],
            }
        )
    write_table("alternative_judge", alternative_rows, list(alternative_rows[0]))

    taxonomy_rows = payload["existence_fp_taxonomy"]["categories"]
    write_table(
        "existence_fp_taxonomy",
        taxonomy_rows,
        ["category", "automatic_pipeline", "alternative_automatic_judge"],
    )

    gaslight_rows = []
    for arm in ("baseline", "existence_t2", "neutral_t2", "pressure", "pressure_t2"):
        metrics = payload["external"]["gaslight"]["by_arm"][arm]
        gaslight_rows.append({"arm": arm, **metrics})
    gaslight_rows.append({"arm": "pooled", **payload["external"]["gaslight"]["overall"]})
    gaslight_columns = [
        "arm",
        "n",
        "tp",
        "fp",
        "fn",
        "tn",
        "precision",
        "recall",
        "f1",
        "agreement",
    ]
    write_table("gaslight_reject", gaslight_rows, gaslight_columns)

    sycon_rows = []
    for trajectory in ("existence", "neutral", "pressure"):
        metrics = payload["external"]["sycon"]["by_trajectory"][trajectory]
        ever = payload["external"]["sycon"]["primary_rater_ever_accept"][trajectory]
        sycon_rows.append(
            {
                "trajectory": trajectory,
                "n_turns": metrics["n"],
                "tp": metrics["tp"],
                "fp": metrics["fp"],
                "fn": metrics["fn"],
                "tn": metrics["tn"],
                "precision": metrics["precision"],
                "recall": metrics["recall"],
                "f1": metrics["f1"],
                "ever_accept_positive": ever["positive"],
                "ever_accept_n": ever["n"],
                "ever_accept_rate": ever["rate"],
                "ever_accept_ci_low": ever["wilson_interval"][0],
                "ever_accept_ci_high": ever["wilson_interval"][1],
            }
        )
    write_table("sycon_qualified", sycon_rows, list(sycon_rows[0]))

    external_rows = []
    for case, metrics, decision in (
        (
            "Gaslight heuristic",
            payload["external"]["gaslight"]["overall"],
            "quarantine effects",
        ),
        (
            "SYCON judge",
            payload["external"]["sycon"]["overall"],
            "qualify ordering only",
        ),
    ):
        external_rows.append(
            {
                "case": case,
                "n": metrics["n"],
                "tp": metrics["tp"],
                "fp": metrics["fp"],
                "fn": metrics["fn"],
                "tn": metrics["tn"],
                "f1": metrics["f1"],
                "decision": decision,
            }
        )
    write_table("external_cases", external_rows, list(external_rows[0]))

    rater_rows = []
    for audit, result in (
        ("representative", payload["representative_dual"]),
        ("factorial", payload["factorial"]["dual_rater"]),
        ("gaslight", payload["external"]["gaslight"]["dual_rater"]),
        ("sycon", payload["external"]["sycon"]["dual_rater"]),
    ):
        rater_rows.append(
            {
                "audit": audit,
                "n": result["n"],
                "agreement": result["agreement"],
                "kappa": result["kappa"],
                "disagreement": result["disagreement"],
            }
        )
    write_table("rater_agreement", rater_rows, list(rater_rows[0]))


def main() -> None:
    representative_frame = pd.read_csv(REPRESENTATIVE, low_memory=False)
    representative_dual_frame = pd.read_csv(REPRESENTATIVE_DUAL, low_memory=False)
    factorial_frame = pd.read_csv(FACTORIAL, low_memory=False)
    factorial_dual_frame = pd.read_csv(FACTORIAL_DUAL, low_memory=False)
    hard_frame = pd.read_csv(HARD, low_memory=False)
    h3_frame = pd.read_csv(PAIRED_H3, low_memory=False)
    gaslight_frame = pd.read_csv(GASLIGHT, low_memory=False)
    gaslight_dual_frame = pd.read_csv(GASLIGHT_DUAL, low_memory=False)
    sycon_frame = pd.read_csv(SYCON, low_memory=False)
    sycon_dual_frame = pd.read_csv(SYCON_DUAL, low_memory=False)
    alternative_frame = pd.read_csv(ALTERNATIVE, low_memory=False)
    taxonomy_frame = pd.read_csv(EXISTENCE_TAXONOMY, low_memory=False)

    representative, representative_dual = representative_analysis(
        representative_frame, representative_dual_frame, hard_frame
    )
    factorial, _ = factorial_analysis(factorial_frame, factorial_dual_frame)
    payload = {
        "sources": {
            "manifest": "data/confirmatory_v1/manifest.json",
            "representative": str(REPRESENTATIVE.relative_to(REPO_ROOT)),
            "hard_audit": str(HARD.relative_to(REPO_ROOT)),
            "factorial": str(FACTORIAL.relative_to(REPO_ROOT)),
            "paired_h3": str(PAIRED_H3.relative_to(REPO_ROOT)),
            "alternative_judge": str(ALTERNATIVE.relative_to(REPO_ROOT)),
            "gaslight": str(GASLIGHT.relative_to(REPO_ROOT)),
            "sycon": str(SYCON.relative_to(REPO_ROOT)),
        },
        "representative": representative,
        "representative_dual": representative_dual,
        "hard_audit": hard_analysis(hard_frame, representative),
        "factorial": factorial,
        "paired_h3": h3_analysis(h3_frame),
        "alternative_judge": alternative_analysis(representative_frame, alternative_frame),
        "existence_fp_taxonomy": taxonomy_analysis(taxonomy_frame),
        "external": external_analysis(
            gaslight_frame,
            gaslight_dual_frame,
            sycon_frame,
            sycon_dual_frame,
        ),
    }
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_ROOT.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    REPRESENTATIVE_JSON.write_text(json.dumps(representative, indent=2) + "\n", encoding="utf-8")
    write_tables(payload)
    print(f"Wrote {OUTPUT_JSON.relative_to(REPO_ROOT)}")
    print(f"Wrote {REPRESENTATIVE_JSON.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
