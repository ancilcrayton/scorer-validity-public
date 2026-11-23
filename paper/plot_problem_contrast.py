#!/usr/bin/env python3
"""Problem schematic for scorer-validity (Figure 1).

A three-panel schematic drawn at the paper's final print width (5.4 in) so the
type stays at 7.5--9 pt. Panel (a) shows that pooling hides arm identity;
panel (b) shows unequal false positives by arm; panel (c) shows how the
difference in signed error moves the reported contrast. All counts and rates
are illustrative.

Design follows Nature's figure guidance: Arial/Helvetica, panel labels
(a)--(c), the Okabe--Ito colour-blind palette, vector output with embedded
fonts, and no decorative fills or shadows.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "paper_scorer_matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, Rectangle

PAPER_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PAPER_DIR / "figures"

INK = "#1A1A1A"
MUTED = "#6B6B6B"
RULE = "#C8C8C8"
ARM_A = "#D55E00"  # Okabe--Ito vermillion
ARM_C = "#0072B2"  # Okabe--Ito blue

FONT = ["Arial", "Helvetica", "DejaVu Sans"]


def _arrow(ax, start, end, *, color=MUTED, linewidth=0.8) -> None:
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=7,
            linewidth=linewidth,
            color=color,
            shrinkA=1.5,
            shrinkB=1.5,
        )
    )


def _key(ax, x, y, color, label) -> None:
    ax.add_patch(Rectangle((x, y - 0.018), 0.011, 0.036, facecolor=color, edgecolor="none"))
    ax.text(x + 0.016, y, label, ha="left", va="center", fontsize=7.2, color=INK)


def _panel_header(ax, x, letter, title) -> None:
    ax.text(x, 0.945, f"({letter})", ha="left", va="center", fontsize=9.2, fontweight="bold", color=INK)
    ax.text(x + 0.036, 0.945, title, ha="left", va="center", fontsize=8.4, color=INK)


def main() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": FONT,
            "mathtext.fontset": "stixsans",
            "font.size": 7.6,
            "axes.linewidth": 0.6,
            "pdf.fonttype": 42,
        }
    )

    # Drawn at final print width: 0.98 * 5.5 in = 5.39 in.
    fig, ax = plt.subplots(figsize=(5.4, 1.78))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # ---------------------------------------------------------------- panel (a)
    _panel_header(ax, 0.012, "a", "Pooled validation")

    for y, label, color, target in (
        (0.600, "arm a", ARM_A, 0.525),
        (0.310, "arm c", ARM_C, 0.355),
    ):
        ax.add_patch(
            Rectangle((0.020, y - 0.020), 0.011, 0.040, facecolor=color, edgecolor="none")
        )
        ax.text(0.038, y, label, ha="left", va="center", fontsize=7.5, color=INK)
        _arrow(ax, (0.098, y), (0.138, target))

    ax.text(0.148, 0.525, r"one $F_1$", ha="left", va="center", fontsize=8.8, fontweight="bold", color=INK)
    ax.text(0.148, 0.355, r"$= 0.916$", ha="left", va="center", fontsize=8.8, fontweight="bold", color=INK)

    # ---------------------------------------------------------------- panel (b)
    _panel_header(ax, 0.352, "b", "Errors by arm")

    for y, label, color, fp in ((0.600, "arm a", ARM_A, 3), (0.310, "arm c", ARM_C, 1)):
        ax.add_patch(
            Rectangle((0.360, y - 0.020), 0.011, 0.040, facecolor=color, edgecolor="none")
        )
        ax.text(0.378, y, label, ha="left", va="center", fontsize=7.5, color=INK)
        for index in range(10):
            is_fp = index < fp
            ax.add_patch(
                Circle(
                    (0.442 + index * 0.0190, y),
                    radius=0.0088,
                    facecolor=color if is_fp else "#FFFFFF",
                    edgecolor=color if is_fp else RULE,
                    linewidth=0.65,
                )
            )
        ax.text(
            0.632,
            y,
            f"{fp} FP",
            ha="left",
            va="center",
            fontsize=7.5,
            fontweight="bold",
            color=color,
        )

    ax.text(
        0.505,
        0.135,
        r"$b_a \neq b_c$",
        ha="center",
        va="center",
        fontsize=8.2,
        color=INK,
    )

    # ---------------------------------------------------------------- panel (c)
    _panel_header(ax, 0.690, "c", "Reported contrast")

    _key(ax, 0.795, 0.855, ARM_A, "arm a")
    _key(ax, 0.882, 0.855, ARM_C, "arm c")

    base_y = 0.285
    bar_w = 0.016
    # Primary-rater labels: equal rates.
    ax.add_patch(Rectangle((0.728, base_y), bar_w, 0.315, facecolor=ARM_A, edgecolor="none"))
    ax.add_patch(Rectangle((0.750, base_y), bar_w, 0.315, facecolor=ARM_C, edgecolor="none"))
    # Automatic labels: arm a inflates, so the contrast moves.
    ax.add_patch(Rectangle((0.858, base_y), bar_w, 0.500, facecolor=ARM_A, edgecolor="none"))
    ax.add_patch(Rectangle((0.880, base_y), bar_w, 0.355, facecolor=ARM_C, edgecolor="none"))

    ax.plot([0.710, 0.960], [base_y, base_y], color=RULE, linewidth=0.7)
    ax.text(0.747, 0.225, "primary rater", ha="center", va="center", fontsize=7.1, color=INK)
    ax.text(0.877, 0.225, "automatic", ha="center", va="center", fontsize=7.1, color=INK)
    ax.text(0.747, 0.145, r"$\Delta = 0$", ha="center", va="center", fontsize=7.8, color=INK)
    ax.text(0.877, 0.145, r"$\widetilde{\Delta} > 0$", ha="center", va="center", fontsize=7.8, color=INK)

    ax.text(
        0.835,
        0.045,
        r"contrast error  $b_a - b_c$",
        ha="center",
        va="center",
        fontsize=7.8,
        fontweight="bold",
        color=INK,
    )

    fig.subplots_adjust(left=0.004, right=0.998, top=0.998, bottom=0.005)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT_DIR / "problem_contrast.pdf")
    fig.savefig(OUTPUT_DIR / "problem_contrast.png", dpi=300)
    plt.close(fig)
    print("Wrote paper/figures/problem_contrast.{pdf,png}")


if __name__ == "__main__":
    main()
