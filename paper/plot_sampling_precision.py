#!/usr/bin/env python3
"""Plot arm precision under representative and hard-case audit sampling.

A dumbbell plot: each arm has a representative-audit estimate (filled circle)
and a hard-audit estimate (open diamond), joined by a hairline so the shift is
easy to read. A vertical rule marks the pooled representative precision, which
makes the pooled-versus-arm point visible.

Design follows Nature's figure guidance: Arial/Helvetica, 8--9 pt text,
Okabe--Ito colours, thin marks, recessive grid, vector output with embedded
fonts.
"""

from __future__ import annotations

import json
import math
import os
import tempfile
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "paper_scorer_matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(Path(tempfile.gettempdir()) / "paper_scorer_cache"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

PAPER_DIR = Path(__file__).resolve().parent
REPO_ROOT = PAPER_DIR.parent
SOURCE = REPO_ROOT / "results" / "confirmatory_v1" / "statistics" / "representative_arm_audit.json"
OUTPUT_DIR = PAPER_DIR / "figures"

ARMS = [
    ("spontaneous_baseline", "Spontaneous"),
    ("cue_baseline", "Soft cue"),
    ("neutral_repetition", "Neutral"),
    ("existence_assertion", "Existence"),
    ("confidence_pressure", "Confidence"),
    ("authority_pressure", "Authority"),
]

INK = "#1A1A1A"
MUTED = "#6B6B6B"
GRID = "#E6E6E6"
RULE = "#B8B8B8"
REP = "#0072B2"  # Okabe--Ito blue
HARD = "#D55E00"  # Okabe--Ito vermillion
FONT = ["Arial", "Helvetica", "DejaVu Sans"]


def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Return a two-sided Wilson score interval for a binomial proportion."""
    if n <= 0:
        return math.nan, math.nan
    p = k / n
    denominator = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denominator
    half_width = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denominator
    return center - half_width, center + half_width


def main() -> None:
    payload = json.loads(SOURCE.read_text(encoding="utf-8"))
    representative = payload["by_arm"]
    hard = payload["hard_oversampled_550_by_arm"]

    labels: list[str] = []
    rep_points, rep_low, rep_high = [], [], []
    hard_points, hard_low, hard_high = [], [], []
    hard_n: list[int] = []

    for arm, label in ARMS:
        metrics = representative[arm]
        low, high = wilson_interval(int(metrics["tp"]), int(metrics["tp"] + metrics["fp"]))
        labels.append(label)
        rep_points.append(float(metrics["precision"]))
        rep_low.append(low)
        rep_high.append(high)
        hard_metrics = hard[arm]
        low, high = wilson_interval(
            int(hard_metrics["tp"]), int(hard_metrics["tp"] + hard_metrics["fp"])
        )
        hard_points.append(float(hard_metrics["precision"]))
        hard_low.append(low)
        hard_high.append(high)
        hard_n.append(int(hard_metrics["n"]))

    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": FONT,
            "font.size": 8.4,
            "axes.labelsize": 8.4,
            "xtick.labelsize": 7.8,
            "ytick.labelsize": 8.2,
            "legend.fontsize": 7.6,
            "pdf.fonttype": 42,
        }
    )

    y = list(range(len(ARMS)))
    fig, ax = plt.subplots(figsize=(3.75, 2.75))

    # Recessive vertical grid at readable round values.
    for tick in (0.0, 0.25, 0.5, 0.75, 1.0):
        ax.axvline(tick, color=GRID, linewidth=0.6, zorder=0)

    # Dumbbell connectors first, so the marks sit on top.
    for row, rep, hard_point in zip(y, rep_points, hard_points):
        ax.plot(
            [min(rep, hard_point), max(rep, hard_point)],
            [row, row],
            color=RULE,
            linewidth=0.8,
            solid_capstyle="round",
            zorder=1,
        )

    ax.errorbar(
        rep_points,
        y,
        xerr=[
            [point - low for point, low in zip(rep_points, rep_low)],
            [high - point for point, high in zip(rep_points, rep_high)],
        ],
        fmt="o",
        color=REP,
        ecolor=REP,
        elinewidth=0.9,
        capsize=2.0,
        capthick=0.9,
        markersize=5.4,
        markeredgecolor="#FFFFFF",
        markeredgewidth=0.9,
        label="Representative (n = 48)",
        zorder=3,
    )
    ax.errorbar(
        hard_points,
        y,
        xerr=[
            [point - low for point, low in zip(hard_points, hard_low)],
            [high - point for point, high in zip(hard_points, hard_high)],
        ],
        fmt="D",
        markerfacecolor="#FFFFFF",
        markeredgecolor=HARD,
        markeredgewidth=1.1,
        color=HARD,
        ecolor=HARD,
        elinewidth=0.9,
        capsize=2.0,
        capthick=0.9,
        markersize=4.6,
        label=f"Hard (n = {min(hard_n)}–{max(hard_n)})",
        zorder=3,
    )

    # Pooled representative precision: the number the audit would report alone.
    pooled = float(payload["overall"]["precision"])
    ax.axvline(pooled, color=MUTED, linewidth=0.8, zorder=2)
    ax.text(
        pooled - 0.010,
        -0.78,
        f"pooled {pooled:.3f}",
        ha="right",
        va="center",
        fontsize=6.8,
        color=MUTED,
    )

    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.set_xlim(0, 1.0)
    ax.set_ylim(len(ARMS) - 0.55, -1.0)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_xlabel("Precision vs. primary rater")
    ax.grid(False)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color(RULE)
    ax.spines["bottom"].set_linewidth(0.6)
    ax.tick_params(axis="y", length=0, pad=4)
    ax.tick_params(axis="x", length=2.5, color=RULE, labelcolor=INK)

    ax.legend(
        loc="lower left",
        bbox_to_anchor=(0.0, 1.005),
        frameon=False,
        ncol=2,
        borderaxespad=0.0,
        handlelength=1.4,
        columnspacing=1.6,
        handletextpad=0.5,
    )

    fig.subplots_adjust(left=0.245, right=0.965, top=0.845, bottom=0.170)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT_DIR / "arm_precision_sampling.pdf")
    fig.savefig(OUTPUT_DIR / "arm_precision_sampling.png", dpi=300)
    plt.close(fig)
    print("Wrote paper/figures/arm_precision_sampling.{pdf,png}")


if __name__ == "__main__":
    main()
