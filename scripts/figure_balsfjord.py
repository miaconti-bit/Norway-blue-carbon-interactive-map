"""
Balsfjord case study: divergent eelgrass trajectories under contrasting
eutrophication pressure at two Ramsar-protected sites in Northern Norway.

New design — two clear panels:

  Panel A  Environmental conditions (grouped bars)
           Shows key stress and performance indicators at each site directly,
           so the reader can see at a glance which site is more impacted.
           Bars are normalised: Kobbevågen (low stress) = 1.0 baseline.

  Panel B  Eelgrass ecosystem outcome
           Clean directional comparison of eelgrass cover-area trajectory at
           each site, shown as labelled arrows pointing up or down.

Key message: legal protection (both sites are Ramsar-protected) does not
guarantee ecosystem health — environmental quality improvement is a prerequisite.

Source: Dahl et al. (2024); compiled roadmap database.

Output:
  figures/figure_balsfjord.png / .pdf
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import numpy as np
from matplotlib.gridspec import GridSpec

FIG_DIR = Path(__file__).resolve().parent.parent / "figures"
FIG_DIR.mkdir(exist_ok=True)

# ── Data (from Dahl et al. 2024 and roadmap database) ─────────────────────────
# Environmental indicators — Sørkjosleira relative to Kobbevågen = 1.0 baseline.
# > 1 = Sørkjosleira has MORE of this stressor → worse
# < 1 = Sørkjosleira has LOWER performance → worse
INDICATORS = [
    ("River nitrate\ninput",  5.86, "stress"),     # 5.86× higher at Sørkjosleira
    ("Epiphyte\nload",        1.61, "stress"),     # 1.61× higher (shading eelgrass)
    ("Shoot\nheight",         0.19, "performance"),# only 19% of Kobbevågen shoot height
]

SITE_A = "Sørkjosleira"   # high stress, declining
SITE_B = "Kobbevågen"     # low stress, recovering

# Eelgrass cover area change over monitoring period (%)
AREA_CHANGE = {SITE_A: -38.7, SITE_B: +388.0}

COLOR_A = "#c0392b"   # red  – stressed / declining
COLOR_B = "#27ae60"   # green – healthy / recovering
COLOR_STRESS = "#e67e22"
COLOR_PERF   = "#2980b9"
BASELINE_COLOR = "#555"


def panel_a_conditions(ax) -> None:
    """Grouped horizontal bar chart showing conditions at each site."""
    metrics     = [ind[0] for ind in INDICATORS]
    ratios      = [ind[1] for ind in INDICATORS]
    directions  = [ind[2] for ind in INDICATORS]

    n = len(metrics)
    y = np.arange(n)
    bar_h = 0.38

    # Sørkjosleira bar (actual ratio value) — above each metric label
    # Kobbevågen bar (always 1.0)           — below each metric label
    for i, (metric, ratio, direction) in enumerate(zip(metrics, ratios, directions)):
        # Consistent site colors: Sørkjosleira = red, Kobbevågen = green
        bar_color_b = COLOR_B

        # Sørkjosleira
        ax.barh(y[i] + bar_h / 2, ratio, height=bar_h,
                color=COLOR_A, edgecolor="black", linewidth=0.7,
                label=SITE_A if i == 0 else "_")
        # Kobbevågen (baseline = 1.0)
        ax.barh(y[i] - bar_h / 2, 1.0, height=bar_h,
                color=bar_color_b, edgecolor="black", linewidth=0.7,
                label=SITE_B if i == 0 else "_")

        # Value annotations on bars
        ax.text(ratio + 0.1, y[i] + bar_h / 2,
                f"{ratio:.2f}×", va="center", fontsize=10, fontweight="bold",
                color=COLOR_A)
        ax.text(1.0 + 0.1, y[i] - bar_h / 2,
                "1.0× (baseline)", va="center", fontsize=8.5,
                color="#555", style="italic")

    # Direction arrows at right edge (orange = more stress, blue = lower performance)
    arrow_kw = dict(fontsize=13, va="center", fontweight="bold")
    for i, (_, ratio, direction) in enumerate(zip(metrics, ratios, directions)):
        symbol = "▲" if direction == "stress" else "▼"
        color  = COLOR_STRESS if direction == "stress" else COLOR_PERF
        ax.text(max(ratios) * 1.22, y[i] + bar_h / 2,
                symbol, color=color, **arrow_kw)
        ax.text(max(ratios) * 1.30, y[i] + bar_h / 2,
                "stress" if direction == "stress" else "performance",
                va="center", fontsize=7.5, color=color, style="italic")

    ax.set_yticks(y)
    ax.set_yticklabels(metrics, fontsize=11)
    ax.set_xlabel("Value relative to Kobbevågen (ratio)", fontsize=10)
    ax.set_xlim(0, max(ratios) * 1.35)
    ax.set_ylim(-0.7, n - 0.3)
    ax.set_title("A.  Environmental Conditions at Each Site", loc="left",
                 fontweight="bold", fontsize=11)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Legend: site colors match bar colors
    legend_handles = [
        mpatches.Patch(facecolor=COLOR_A, edgecolor="black", linewidth=0.7,
                       label=f"{SITE_A} (impacted)"),
        mpatches.Patch(facecolor=COLOR_B, edgecolor="black", linewidth=0.7,
                       label=f"{SITE_B} (reference, baseline = 1.0)"),
    ]
    ax.legend(handles=legend_handles, frameon=True, fontsize=9,
              loc="lower right", framealpha=0.9, edgecolor="#ccc")


def panel_b_outcome(ax) -> None:
    """Clean directional outcome panel using arrow annotations."""
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_title("B.  Eelgrass Ecosystem Outcome", loc="left",
                 fontweight="bold", fontsize=11)

    # Helper to draw a large arrow + site name + value
    def draw_outcome(y_center, site, change_pct, color):
        arrow_up = change_pct > 0
        symbol = "↑" if arrow_up else "↓"
        sign   = f"+{change_pct:.0f}%" if arrow_up else f"{change_pct:.0f}%"
        status = "Recovering" if arrow_up else "Declining"

        # Big arrow symbol
        ax.text(0.18, y_center, symbol,
                ha="center", va="center", fontsize=64,
                color=color, alpha=0.20)
        ax.text(0.18, y_center, symbol,
                ha="center", va="center", fontsize=64,
                color=color, alpha=0.85,
                path_effects=[pe.withStroke(linewidth=2, foreground="white")])

        # Site name
        ax.text(0.42, y_center + 0.13, site,
                ha="left", va="center", fontsize=12,
                fontweight="bold", color=color)
        # Percent change
        ax.text(0.42, y_center, sign,
                ha="left", va="center", fontsize=20,
                fontweight="bold", color=color)
        # Status label
        ax.text(0.42, y_center - 0.13, status,
                ha="left", va="center", fontsize=10,
                color=color, style="italic")

        # Thin horizontal divider at coverage box edge
        ax.add_patch(mpatches.FancyBboxPatch(
            (0.04, y_center - 0.22), 0.90, 0.44,
            boxstyle="round,pad=0.02",
            facecolor=color, edgecolor="none", alpha=0.06, zorder=0,
        ))

    draw_outcome(0.73, SITE_A, AREA_CHANGE[SITE_A], COLOR_A)
    draw_outcome(0.27, SITE_B, AREA_CHANGE[SITE_B], COLOR_B)

    ax.text(0.50, 0.50,
            "Change in eelgrass\ncover area (%)",
            ha="center", va="center", fontsize=8,
            color="#777", style="italic",
            bbox=dict(facecolor="white", edgecolor="#ccc",
                      boxstyle="round,pad=0.3", linewidth=0.5))


def render() -> Path:
    fig = plt.figure(figsize=(13, 6.5))
    gs = GridSpec(1, 2, figure=fig, width_ratios=[1.3, 1.0],
                  wspace=0.14, left=0.08, right=0.96,
                  top=0.88, bottom=0.12)
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])

    panel_a_conditions(ax_a)
    panel_b_outcome(ax_b)

    fig.suptitle(
        "Balsfjord Case Study: Divergent Eelgrass Responses\n"
        "Under Contrasting Eutrophication Regimes",
        fontsize=13, fontweight="bold", y=1.00,
    )

    out_png = FIG_DIR / "figure_balsfjord.png"
    out_pdf = FIG_DIR / "figure_balsfjord.pdf"
    fig.savefig(out_png, dpi=200, bbox_inches="tight")
    fig.savefig(out_pdf, bbox_inches="tight")
    plt.close(fig)
    return out_png


def main() -> None:
    out = render()
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
