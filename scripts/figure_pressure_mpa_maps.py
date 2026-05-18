"""
Two-panel spatial map: pressure index and strict MPA overlap for Norwegian
eelgrass and kelp habitat polygons (HB19 Naturbase).

Each point is the centroid of one mapped habitat polygon. Point size scales
with habitat area. The left panel shows co-location pressure (dredging +
aquaculture + platforms within 5 km); the right shows the fraction of each
polygon's area within a strict marine MPA (MarintVerneomraade only).

The third panel (permissive verneomrader, mostly bird reserves) is excluded
because those designations do not regulate marine activities.

Input:
  data/processed/spatial_analysis/habitat_colocation_metrics.csv

Output:
  figures/figure_pressure_mpa_maps.png / .pdf
"""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.gridspec import GridSpec
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parent.parent
METRICS_PATH = ROOT / "data" / "processed" / "spatial_analysis" / "habitat_colocation_metrics.csv"
FIG_DIR = ROOT / "figures"
FIG_DIR.mkdir(exist_ok=True)

# Norway bounding box
LON_MIN, LON_MAX = 3.5, 31.5
LAT_MIN, LAT_MAX = 57.5, 71.5


def load_data() -> pd.DataFrame:
    df = pd.read_csv(METRICS_PATH)
    df = df.dropna(subset=["centroid_lon", "centroid_lat"])
    df = df[
        (df["centroid_lon"].between(LON_MIN, LON_MAX)) &
        (df["centroid_lat"].between(LAT_MIN, LAT_MAX))
    ].copy()
    df["area_km2"] = df["habitat_area_m2"] / 1e6
    return df


def norway_aspect(ax) -> None:
    ax.set_xlim(LON_MIN, LON_MAX)
    ax.set_ylim(LAT_MIN, LAT_MAX)
    ax.set_facecolor("#eaf4fb")
    ax.set_xlabel("Longitude", fontsize=8.5)
    ax.set_ylabel("Latitude", fontsize=8.5)
    ax.tick_params(labelsize=8)
    for spine in ax.spines.values():
        spine.set_linewidth(0.6)


def size_from_area(area_km2: np.ndarray) -> np.ndarray:
    """Point size proportional to sqrt(area), clamped for readability."""
    s = np.sqrt(np.clip(area_km2, 0.001, 50)) * 8
    return np.clip(s, 2, 80)


def render(df: pd.DataFrame) -> Path:
    fig = plt.figure(figsize=(13, 8.5))
    gs = GridSpec(1, 2, figure=fig, wspace=0.10,
                  left=0.06, right=0.97, top=0.84, bottom=0.12)
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])

    sizes = size_from_area(df["area_km2"].values)

    # ── Panel 1: Pressure index ────────────────────────────────────────────
    pressure_levels = [0, 0.5, 2.5, 5.5, 11.5, 50]
    pressure_cmap = ListedColormap(["#d9d9d9", "#fee08b", "#fdae61", "#f46d43", "#d73027"])
    pressure_norm = BoundaryNorm(pressure_levels, pressure_cmap.N)

    norway_aspect(ax1)
    # Draw zero-pressure (grey) points first so coloured ones sit on top
    mask_zero = df["colocation_pressure_index"] == 0
    ax1.scatter(df.loc[mask_zero, "centroid_lon"],
                df.loc[mask_zero, "centroid_lat"],
                c="#d9d9d9", s=sizes[mask_zero.values],
                linewidths=0, alpha=0.35, zorder=2)
    sc1 = ax1.scatter(df.loc[~mask_zero, "centroid_lon"],
                      df.loc[~mask_zero, "centroid_lat"],
                      c=df.loc[~mask_zero, "colocation_pressure_index"],
                      cmap=pressure_cmap, norm=pressure_norm,
                      s=sizes[~mask_zero.values],
                      linewidths=0.3, edgecolors="black", alpha=0.85, zorder=3)

    cb1 = plt.colorbar(
        mpl.cm.ScalarMappable(norm=pressure_norm, cmap=pressure_cmap),
        ax=ax1, orientation="horizontal", pad=0.08, fraction=0.04,
        ticks=[0, 1.5, 4, 8.5, 30],
    )
    cb1.set_label("Co-location pressure index\n(dredging + aquaculture + platforms within 5 km)", fontsize=8)
    cb1.ax.set_xticklabels(["0\n(none)", "1–2\n(trace)", "3–5\n(mod.)", "6–11\n(high)", "12+\n(severe)"],
                            fontsize=7.5)

    ax1.set_title("A.  Co-location Pressure Index", loc="left",
                  fontweight="bold", fontsize=11, pad=6)

    # ── Panel 2: Strict MPA overlap ───────────────────────────────────────
    mpa_levels = [0, 0.01, 1, 10, 50, 100.01]
    mpa_cmap = ListedColormap(["#d9d9d9", "#c6dbef", "#6baed6", "#3182bd", "#08306b"])
    mpa_norm = BoundaryNorm(mpa_levels, mpa_cmap.N)

    norway_aspect(ax2)
    mask_zero_mpa = df["percent_mpa"] < 0.01
    ax2.scatter(df.loc[mask_zero_mpa, "centroid_lon"],
                df.loc[mask_zero_mpa, "centroid_lat"],
                c="#d9d9d9", s=sizes[mask_zero_mpa.values],
                linewidths=0, alpha=0.35, zorder=2)
    sc2 = ax2.scatter(df.loc[~mask_zero_mpa, "centroid_lon"],
                      df.loc[~mask_zero_mpa, "centroid_lat"],
                      c=df.loc[~mask_zero_mpa, "percent_mpa"],
                      cmap=mpa_cmap, norm=mpa_norm,
                      s=sizes[~mask_zero_mpa.values],
                      linewidths=0.3, edgecolors="black", alpha=0.85, zorder=3)

    cb2 = plt.colorbar(
        mpl.cm.ScalarMappable(norm=mpa_norm, cmap=mpa_cmap),
        ax=ax2, orientation="horizontal", pad=0.08, fraction=0.04,
        ticks=[0.005, 0.5, 5, 30, 75],
    )
    cb2.set_label("Polygon area in strict marine MPA (%)\n(MarintVerneomraade only)", fontsize=8)
    cb2.ax.set_xticklabels(["0%\n(none)", "<1%\n(trace)", "1–10%\n(low)", "10–50%\n(partial)", "50%+\n(high)"],
                            fontsize=7.5)
    ax2.set_ylabel("")

    ax2.set_title("B.  Strict MPA Coverage", loc="left",
                  fontweight="bold", fontsize=11, pad=6)

    n_kelp = (df["ecosystem"] == "macroalgae").sum()
    n_sg   = (df["ecosystem"] == "seagrass").sum()

    fig.suptitle(
        "Eelgrass and Kelp Habitat Polygons: Pressure and MPA Coverage (Norway)",
        fontsize=13, fontweight="bold", y=0.97,
    )
    fig.text(
        0.5, 0.935,
        f"{n_sg:,} eelgrass + {n_kelp:,} kelp polygons (HB19 Naturbase). "
        "Point size ∝ habitat area. Grey = no signal. "
        "Strict MPA = MarintVerneomraade only.",
        fontsize=8.5, color="#555", ha="center",
    )

    # Size-scale legend only (dots are coloured by pressure or MPA, not by ecosystem)
    size_handles = []
    for area, label in [(0.05, "0.05 km²"), (1, "1 km²"), (20, "20 km²")]:
        s = size_from_area(np.array([area]))[0]
        size_handles.append(
            Line2D([0], [0], marker="o", color="w", markerfacecolor="#888",
                   markeredgecolor="black", markersize=max(np.sqrt(s), 3),
                   label=label)
        )
    # Place size legend at far right, outside the panel
    ax2.legend(handles=size_handles, loc="center left",
               bbox_to_anchor=(1.02, 0.5),
               fontsize=8.5, title="Marker size\n= habitat area",
               title_fontsize=8.5, frameon=True, edgecolor="#ccc",
               framealpha=0.9)

    out_png = FIG_DIR / "figure_pressure_mpa_maps.png"
    out_pdf = FIG_DIR / "figure_pressure_mpa_maps.pdf"
    fig.savefig(out_png, dpi=200, bbox_inches="tight")
    fig.savefig(out_pdf, bbox_inches="tight")
    plt.close(fig)
    return out_png


def main() -> None:
    df = load_data()
    print(f"Loaded {len(df):,} habitat polygons "
          f"({(df['ecosystem']=='seagrass').sum():,} eelgrass, "
          f"{(df['ecosystem']=='macroalgae').sum():,} kelp)")
    out = render(df)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
