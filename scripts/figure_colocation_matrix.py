"""
Pressures synthesis: co-location profile heatmap and pressure decomposition.

Panel A  Co-location profile heatmap — region × habitat rows, indicator columns
         showing protection coverage, total anthropogenic pressure intensity, and carbon.

Panel B  Pressure decomposition — relative intensity (0–1) of each pressure
         component per region-habitat unit. All values are min-max normalized
         within the dataset: 0 = lowest observed, 1 = highest observed.
         Components: dredging density, aquaculture density, fishing effort (ERS),
         offshore platforms (within 10 km), unprotected share (1 − %protected/100).

Inputs:
  data/processed/regional_priority_metrics.csv
  data/processed/spatial_analysis/regional_colocation_summary.csv

Outputs:
  figures/figure_pressures_synthesis.png
  figures/figure_pressures_synthesis.pdf
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.gridspec import GridSpec

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
FIG = ROOT / "figures"
FIG.mkdir(exist_ok=True)

METRICS_PATH = PROC / "regional_priority_metrics.csv"
COLOC_SUMMARY_PATH = PROC / "spatial_analysis" / "regional_colocation_summary.csv"

REGION_ORDER = ["Barents Sea", "Norwegian Sea", "Skagerrak"]
REGION_SHORT = {
    "Barents Sea":   "Barents Sea",
    "Norwegian Sea": "Norwegian Sea",
    "Skagerrak":     "Skagerrak\n(incl. Oslofjord)",
}
HABITAT_COLOR = {
    "macroalgae": "#2c6e49",
    "seagrass": "#74c476",
}
HABITAT_LABEL = {"macroalgae": "Kelp", "seagrass": "Seagrass"}


def load_data() -> pd.DataFrame:
    df = pd.read_csv(METRICS_PATH)
    df = df[df["canonical_region"].isin(REGION_ORDER)].copy()

    # Join fishing counts from colocation summary to compute fishing_per_km2
    coloc = pd.read_csv(COLOC_SUMMARY_PATH)[
        ["ecosystem", "canonical_region", "fishing_within_5km_n", "habitat_area_km2"]
    ]
    df = df.merge(coloc, on=["ecosystem", "canonical_region"], how="left", suffixes=("", "_coloc"))
    df["fishing_per_km2"] = df["fishing_within_5km_n"] / df["habitat_area_km2"].replace(0, float("nan"))
    df["total_pressure_per_km2"] = df["dredging_per_km2"] + df["akvakultur_per_km2"] + df["fishing_per_km2"].fillna(0)
    return df


def build_pressure_index(df: pd.DataFrame) -> pd.DataFrame:
    """Composite pressure index (0–1) normalized across all six habitat-region combos."""
    df = df.copy()
    if "fishing_per_km2" not in df.columns:
        df["fishing_per_km2"] = 0.0
    components = ["dredging_per_km2", "akvakultur_per_km2", "fishing_per_km2", "platforms_10km"]
    for col in components:
        vmin, vmax = df[col].min(), df[col].max()
        df[f"{col}_n"] = (df[col] - vmin) / (vmax - vmin) if vmax > vmin else 0.5
    df["pressure_index"] = df[[f"{c}_n" for c in components]].mean(axis=1)
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Panel A: Co-location profile heatmap
# ─────────────────────────────────────────────────────────────────────────────

def panel_a_heatmap(ax, df: pd.DataFrame) -> None:
    indicators = [
        # (column, display_label, category, high_is_good)
        ("percent_habitat_in_mpa",    "In strict\nMPA (%)",           "protection", True),
        ("percent_habitat_protected", "Any\nprotection (%)",           "protection", True),
        ("total_pressure_per_km2",    "Total\npressure\n(n/km²)",     "pressure",   False),
        ("stock_density_g_m2",        "Carbon\ndensity (g/m²)",        "carbon",     True),
        ("stock_GgC",                 "Total carbon\n(Gg C)",          "carbon",     True),
    ]

    # Row order: kelp first, then seagrass; within each, Barents → Norwegian → Skagerrak
    rows = []
    for eco in ["macroalgae", "seagrass"]:
        for region in REGION_ORDER:
            r = df[(df["ecosystem"] == eco) & (df["canonical_region"] == region)]
            if not r.empty:
                rows.append(r.iloc[0])

    row_labels = [
        f"{'  ' if r['ecosystem'] == 'seagrass' else ''}"
        f"{HABITAT_LABEL[r['ecosystem']]} · "
        f"{REGION_SHORT[r['canonical_region']].split(chr(10))[0]}"
        for r in rows
    ]

    n_rows = len(rows)
    n_cols = len(indicators)

    # Raw and min-max normalized matrices
    raw_mat = np.array([[float(r[col]) if not pd.isna(r[col]) else 0.0
                         for col, *_ in indicators]
                        for r in rows])
    norm_mat = np.zeros_like(raw_mat)
    for j in range(n_cols):
        col_vals = raw_mat[:, j]
        vmin, vmax = col_vals.min(), col_vals.max()
        norm_mat[:, j] = (col_vals - vmin) / (vmax - vmin) if vmax > vmin else 0.5

    category_cmaps = {"protection": "YlGn", "pressure": "YlOrRd", "carbon": "Blues"}
    category_invert = {"protection": False, "pressure": False, "carbon": False}

    for i in range(n_rows):
        for j, (_, _, cat, high_is_good) in enumerate(indicators):
            v = norm_mat[i, j]
            cmap = plt.colormaps[category_cmaps[cat]]
            # For pressure: invert so high pressure → dark red
            plot_v = v if high_is_good else v
            color = cmap(0.18 + plot_v * 0.78)

            rect = mpatches.FancyBboxPatch(
                (j - 0.46, i - 0.44), 0.92, 0.88,
                boxstyle="round,pad=0.04",
                facecolor=color, edgecolor="white", linewidth=1.8,
            )
            ax.add_patch(rect)

            # Format raw value for annotation
            raw_v = raw_mat[i, j]
            col_name = indicators[j][0]
            if col_name in ("percent_habitat_in_mpa", "percent_habitat_protected"):
                lbl = f"{raw_v:.1f}%"
            elif col_name in ("dredging_per_km2", "akvakultur_per_km2", "total_pressure_per_km2"):
                lbl = f"{raw_v:.1f}" if raw_v >= 1 else f"{raw_v:.2f}"
            elif col_name == "platforms_10km":
                lbl = f"{int(raw_v)}"
            elif col_name == "stock_density_g_m2":
                lbl = f"{raw_v:.0f}" if raw_v > 0 else "—"
            else:
                lbl = f"{raw_v:.0f}"

            text_color = "white" if plot_v > 0.65 else "#222"
            ax.text(j, i, lbl, ha="center", va="center",
                    fontsize=9, color=text_color, fontweight="bold")

    # Left: ecosystem color strip + group labels
    for i, r in enumerate(rows):
        eco = r["ecosystem"]
        band = mpatches.FancyBboxPatch(
            (-1.55, i - 0.42), 0.35, 0.84,
            boxstyle="round,pad=0.03",
            facecolor=HABITAT_COLOR[eco], edgecolor="none",
        )
        ax.add_patch(band)

    kelp_ys = [i for i, r in enumerate(rows) if r["ecosystem"] == "macroalgae"]
    sg_ys   = [i for i, r in enumerate(rows) if r["ecosystem"] == "seagrass"]
    ax.text(-1.85, np.mean(kelp_ys), "Kelp", ha="center", va="center",
            fontsize=9, fontweight="bold", color=HABITAT_COLOR["macroalgae"],
            rotation=90)
    ax.text(-1.85, np.mean(sg_ys), "Seagrass", ha="center", va="center",
            fontsize=9, fontweight="bold", color=HABITAT_COLOR["seagrass"],
            rotation=90)

    # Separator between kelp and seagrass groups
    if kelp_ys and sg_ys:
        sep_y = (max(kelp_ys) + min(sg_ys)) / 2
        ax.plot([-1.6, n_cols - 0.46], [sep_y, sep_y],
                color="#999", linewidth=1.2, linestyle="--", zorder=3)

    # Column category header bands above the grid
    cat_spans = [
        ([0, 1], "#276221", "PROTECTION"),
        ([2],    "#9b1c1c", "PRESSURE"),
        ([3, 4], "#1e3a5f", "CARBON"),
    ]
    for col_idxs, bcolor, label in cat_spans:
        xstart = min(col_idxs) - 0.46
        xwidth = (max(col_idxs) - min(col_idxs) + 1) * 1.0 - 0.08
        rect = mpatches.FancyBboxPatch(
            (xstart, -1.52), xwidth, 0.46,
            boxstyle="round,pad=0.04",
            facecolor=bcolor, edgecolor="none", alpha=0.9,
        )
        ax.add_patch(rect)
        ax.text(np.mean(col_idxs), -1.29, label,
                ha="center", va="center", fontsize=8, fontweight="bold",
                color="white")

    ax.set_xlim(-2.1, n_cols - 0.38)
    ax.set_ylim(-1.85, n_rows - 0.38)
    ax.invert_yaxis()

    ax.set_xticks(range(n_cols))
    ax.set_xticklabels([lbl for _, lbl, *_ in indicators], fontsize=8.5, ha="center")
    ax.xaxis.set_ticks_position("top")
    ax.xaxis.set_label_position("top")
    ax.tick_params(axis="x", length=0, pad=3)

    ax.set_yticks(range(n_rows))
    ax.set_yticklabels(row_labels, fontsize=9)
    ax.tick_params(axis="y", length=0)

    ax.set_title("A.  Co-location Profile", loc="left",
                 fontweight="bold", fontsize=12, pad=38)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_facecolor("#f5f5f5")


# ─────────────────────────────────────────────────────────────────────────────
# Panel B: Pressure decomposition (normalized 0–1, all-positive bars)
# ─────────────────────────────────────────────────────────────────────────────

def panel_b_pressure_decomp(ax, df: pd.DataFrame) -> None:
    """Stacked horizontal bars showing relative pressure intensity per region-habitat.

    Each component is min-max normalized to [0, 1] across all six region-habitat units,
    so 0 = lowest value observed in the dataset, 1 = highest. This avoids negative bars
    and allows direct comparison of which units face the most pressure.
    """
    components = [
        ("dredging_per_km2",    "Dredging (per km²)"),
        ("akvakultur_per_km2",  "Aquaculture (per km²)"),
        ("fishing_per_km2",     "Fishing effort — ERS (per km²)"),
        ("platforms_10km",      "Platforms within 10 km"),
        ("lack_of_protection",  "Unprotected share"),
    ]
    component_palette = ["#4292c6", "#fd8d3c", "#d94801", "#74c476", "#9e9ac8"]

    # Min-max normalize each component across all rows
    df = df.copy()
    if "lack_of_protection" not in df.columns:
        df["lack_of_protection"] = 1 - df["percent_habitat_protected"] / 100
    if "fishing_per_km2" not in df.columns:
        df["fishing_per_km2"] = 0.0
    for col, _ in components:
        vmin, vmax = df[col].min(), df[col].max()
        df[f"{col}_n"] = (df[col] - vmin) / (vmax - vmin) if vmax > vmin else 0.5

    regions = REGION_ORDER
    ecos = ["macroalgae", "seagrass"]
    bar_h = 0.36
    short = {"Barents Sea": "Barents", "Norwegian Sea": "Norwegian", "Skagerrak": "Skagerrak"}

    y_positions, y_labels = [], []
    pos = 0
    for region in regions:
        for eco in ecos:
            row = df[(df["canonical_region"] == region) & (df["ecosystem"] == eco)]
            if row.empty:
                continue
            row = row.iloc[0]
            left = 0.0
            for (col, _label), color in zip(components, component_palette):
                v = row[f"{col}_n"]
                ax.barh(pos, v, height=bar_h, left=left,
                        color=color, edgecolor="black", linewidth=0.4)
                left += v
            y_positions.append(pos)
            y_labels.append(f"{short[region]}  ·  {HABITAT_LABEL[eco]}")
            pos += 1
        pos += 0.5

    ax.set_yticks(y_positions)
    ax.set_yticklabels(y_labels, fontsize=8.5)
    ax.invert_yaxis()
    ax.set_xlabel("Cumulative relative pressure (normalized 0–1 per component)", fontsize=9)
    ax.set_title("B.  Pressure Decomposition by Region and Habitat", loc="left",
                 fontweight="bold", fontsize=12, pad=38)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    legend_handles = [mpatches.Patch(facecolor=c, edgecolor="#666", linewidth=0.5, label=lbl)
                      for (_, lbl), c in zip(components, component_palette)]
    ax.legend(handles=legend_handles, loc="upper right",
              ncol=1, frameon=True, fontsize=8,
              framealpha=0.92, edgecolor="#ccc")


# ─────────────────────────────────────────────────────────────────────────────
# Main render
# ─────────────────────────────────────────────────────────────────────────────

def render(df: pd.DataFrame) -> Path:
    fig = plt.figure(figsize=(15, 8))
    gs = GridSpec(
        1, 2, figure=fig,
        width_ratios=[1.0, 1.1],
        wspace=0.42,
        left=0.09, right=0.97, top=0.82, bottom=0.10,
    )

    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])

    panel_a_heatmap(ax_a, df)
    panel_b_pressure_decomp(ax_b, df)

    fig.suptitle(
        "Norwegian Eelgrass and Kelp: Co-location Profile and Pressure Decomposition",
        fontsize=14, fontweight="bold", y=0.98,
    )

    caption = (
        "Panel A: Co-location profile. Cells are min-max normalized within each indicator column; "
        "raw values are annotated. Protection (green): % habitat in strict MPA; % under any designation. "
        "Pressure (red): total anthropogenic pressure per km² of habitat — sum of dredging, aquaculture, "
        "and ERS fishing effort facilities/hauls within 5 km, divided by habitat area. "
        "Carbon (blue): mean stock density (g C m⁻²) and total stock (Gg C). "
        "Panel B: Pressure decomposition. Each component is normalized 0–1 across all region-habitat units "
        "(0 = lowest observed, 1 = highest). Bars show cumulative relative pressure; longer bars indicate "
        "more intense cumulative pressure relative to the rest of the dataset. "
        "Fishing effort from Fiskeridir ERS 2019–2023 (DCA catch messages). "
        "Unprotected share = 1 − (% habitat under any protection). "
        "Oslofjord seagrass sites are included in the Skagerrak aggregate."
    )
    fig.text(0.09, 0.022, caption, fontsize=7.5, color="#444",
             ha="left", wrap=True, style="italic",
             bbox=dict(facecolor="#f9f9f9", edgecolor="#ddd",
                       boxstyle="round,pad=0.4", linewidth=0.5))

    out_png = FIG / "figure_pressures_synthesis.png"
    out_pdf = FIG / "figure_pressures_synthesis.pdf"
    fig.savefig(out_png, dpi=200, bbox_inches="tight")
    fig.savefig(out_pdf, bbox_inches="tight")
    plt.close(fig)
    return out_png


def main() -> None:
    df = load_data()
    df = build_pressure_index(df)
    if "lack_of_protection" not in df.columns:
        df["lack_of_protection"] = 1 - df["percent_habitat_protected"] / 100

    print("Co-location summary:")
    print(
        df[["ecosystem", "canonical_region", "pressure_index",
            "percent_habitat_in_mpa", "stock_GgC"]]
        .to_string(index=False)
    )

    out = render(df)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
