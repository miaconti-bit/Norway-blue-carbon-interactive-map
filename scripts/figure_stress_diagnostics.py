"""Static stress-diagnostic figure pack for Norway blue-carbon habitats.

Reads:
  data/processed/spatial_analysis/habitat_colocation_metrics.csv

Writes to figures/stress_diagnostics/:
  fig01_risk_matrix.png             - 2D bin counts of pressure x protection, by ecosystem
  fig02_pressure_protection_maps.png - static centroid maps (pressure quantile / protection)
  fig03_regional_class_breakdown.png - habitat area by colocation class x region
  fig04_pressure_type_mix.png       - which pressures dominate among stressed polygons
  fig05_sampling_coverage.png       - pressure x protection grid colored by study-site coverage
  regional_stress_stats.csv         - per region x ecosystem summary table

Run from repo root with the project venv:
  python scripts/figure_stress_diagnostics.py
"""

from __future__ import annotations

import math
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch


REPO_ROOT = Path(__file__).resolve().parent.parent
METRICS_PATH = REPO_ROOT / "data" / "processed" / "spatial_analysis" / "habitat_colocation_metrics.csv"
OUT_DIR = REPO_ROOT / "figures" / "stress_diagnostics"

PRESSURE_BINS = [-0.5, 0.5, 2.5, 5.5, 11.5, np.inf]
PRESSURE_LABELS = ["0\n(none)", "1-2\n(trace)", "3-5\n(moderate)", "6-11\n(high)", "12+\n(severe)"]
PROTECTION_BINS = [-0.001, 0.001, 1.0, 10.0, 50.0, 100.001]
PROTECTION_LABELS = ["0%\n(none)", "<1%\n(trace)", "1-10%\n(low)", "10-50%\n(partial)", "50%+\n(high)"]

CLASS_ORDER = ["pressure_low_protection", "pressure_and_protected", "protected", "study_covered", "mapped_gap"]
CLASS_COLORS = {
    "pressure_low_protection": "#c1272d",
    "pressure_and_protected": "#f6ae2d",
    "protected": "#2e8b57",
    "study_covered": "#4a6fa5",
    "mapped_gap": "#9aa0a6",
}
CLASS_LABELS = {
    "pressure_low_protection": "Pressure, <1% protected",
    "pressure_and_protected": "Pressure, >=10% protected",
    "protected": "Protected, no pressure",
    "study_covered": "Study site within 5 km",
    "mapped_gap": "Mapped, no other signal",
}

ECO_COLORS = {"macroalgae": "#0a6b54", "seagrass": "#7d3c98"}
NORWAY_LON = (3.5, 32.0)
NORWAY_LAT = (57.5, 71.5)


def colocation_class(row: pd.Series) -> str:
    pct_prot = float(row["percent_protected"] or 0)
    pressure = float(row["colocation_pressure_index"] or 0) > 0
    if pressure and pct_prot < 1:
        return "pressure_low_protection"
    if pressure and pct_prot >= 10:
        return "pressure_and_protected"
    if pct_prot >= 10:
        return "protected"
    if float(row["study_sites_within_5km_n"] or 0) > 0:
        return "study_covered"
    return "mapped_gap"


def load_metrics() -> pd.DataFrame:
    df = pd.read_csv(METRICS_PATH)
    df["habitat_area_km2"] = df["habitat_area_m2"] / 1e6
    df["map_class"] = df.apply(colocation_class, axis=1)
    df["pressure_bin"] = pd.cut(df["colocation_pressure_index"], bins=PRESSURE_BINS, labels=PRESSURE_LABELS)
    df["protection_bin"] = pd.cut(df["percent_protected"], bins=PROTECTION_BINS, labels=PROTECTION_LABELS, include_lowest=True)
    return df


def set_norway_aspect(ax: plt.Axes) -> None:
    ax.set_xlim(*NORWAY_LON)
    ax.set_ylim(*NORWAY_LAT)
    mid_lat_rad = math.radians(0.5 * sum(NORWAY_LAT))
    ax.set_aspect(1.0 / math.cos(mid_lat_rad))
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.grid(True, linestyle=":", linewidth=0.4, alpha=0.5)


def fig01_risk_matrix(df: pd.DataFrame, out: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5), sharey=True)
    for ax, eco in zip(axes, ["macroalgae", "seagrass"]):
        sub = df[df["ecosystem"] == eco]
        counts = (
            pd.crosstab(sub["protection_bin"], sub["pressure_bin"], dropna=False)
            .reindex(index=PROTECTION_LABELS, columns=PRESSURE_LABELS, fill_value=0)
        )
        im = ax.imshow(counts.values, cmap="OrRd", aspect="auto", origin="lower",
                       norm=mpl.colors.LogNorm(vmin=1, vmax=max(counts.values.max(), 2)))
        for i in range(counts.shape[0]):
            for j in range(counts.shape[1]):
                v = counts.values[i, j]
                if v == 0:
                    continue
                color = "white" if v > counts.values.max() * 0.3 else "black"
                ax.text(j, i, f"{v:,}", ha="center", va="center", fontsize=9, color=color)
        ax.set_xticks(range(len(PRESSURE_LABELS)))
        ax.set_xticklabels(PRESSURE_LABELS, fontsize=8)
        ax.set_yticks(range(len(PROTECTION_LABELS)))
        ax.set_yticklabels(PROTECTION_LABELS, fontsize=8)
        ax.set_title(f"{eco.capitalize()} polygons (n={len(sub):,})")
        ax.set_xlabel("Co-location pressure index")
        if ax is axes[0]:
            ax.set_ylabel("% of polygon area protected")
        cb = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cb.set_label("polygon count (log)")
    fig.suptitle("Risk matrix: pressure x protection per HB19 polygon", y=1.02, fontsize=12)
    fig.tight_layout()
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)


def fig02_static_maps(df: pd.DataFrame, out: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13, 8.5))

    pressure_levels = [0, 1, 3, 6, 12, df["colocation_pressure_index"].max() + 1]
    pressure_cmap = ListedColormap(["#dddddd", "#fee08b", "#fdae61", "#f46d43", "#d73027"])
    pressure_norm = BoundaryNorm(pressure_levels, pressure_cmap.N)

    ax = axes[0]
    df_sorted = df.sort_values("colocation_pressure_index")
    sizes = np.clip(df_sorted["habitat_area_km2"].values * 4, 1.5, 60)
    ax.scatter(df_sorted["centroid_lon"], df_sorted["centroid_lat"],
               c=df_sorted["colocation_pressure_index"], cmap=pressure_cmap, norm=pressure_norm,
               s=sizes, linewidths=0, alpha=0.85)
    set_norway_aspect(ax)
    ax.set_title("Co-location pressure index")
    cb = plt.colorbar(mpl.cm.ScalarMappable(norm=pressure_norm, cmap=pressure_cmap),
                      ax=ax, fraction=0.04, pad=0.04, ticks=pressure_levels)
    cb.set_label("pressure index")

    protection_levels = [0, 0.001, 1, 10, 50, 100.001]
    protection_cmap = ListedColormap(["#dddddd", "#c6dbef", "#6baed6", "#3182bd", "#08519c"])
    protection_norm = BoundaryNorm(protection_levels, protection_cmap.N)

    ax = axes[1]
    df_sorted = df.sort_values("percent_protected")
    sizes = np.clip(df_sorted["habitat_area_km2"].values * 4, 1.5, 60)
    ax.scatter(df_sorted["centroid_lon"], df_sorted["centroid_lat"],
               c=df_sorted["percent_protected"], cmap=protection_cmap, norm=protection_norm,
               s=sizes, linewidths=0, alpha=0.85)
    set_norway_aspect(ax)
    ax.set_title("% of polygon area protected")
    cb = plt.colorbar(mpl.cm.ScalarMappable(norm=protection_norm, cmap=protection_cmap),
                      ax=ax, fraction=0.04, pad=0.04, ticks=[0, 1, 10, 50, 100])
    cb.set_label("% protected")

    fig.suptitle("Pressure and protection per HB19 polygon (centroids; size ~ habitat area)",
                 fontsize=12)
    fig.tight_layout()
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)


def fig03_regional_breakdown(df: pd.DataFrame, out: Path) -> None:
    pivot = (
        df.pivot_table(index="canonical_region", columns="map_class",
                       values="habitat_area_km2", aggfunc="sum", fill_value=0)
        .reindex(columns=CLASS_ORDER, fill_value=0)
    )
    region_order = pivot.sum(axis=1).sort_values(ascending=False).index.tolist()
    pivot = pivot.reindex(region_order)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    ax = axes[0]
    bottom = np.zeros(len(pivot))
    for cls in CLASS_ORDER:
        ax.bar(pivot.index, pivot[cls].values, bottom=bottom,
               color=CLASS_COLORS[cls], label=CLASS_LABELS[cls], edgecolor="white", linewidth=0.5)
        bottom += pivot[cls].values
    ax.set_ylabel("Habitat area (km^2)")
    ax.set_title("Total habitat area by class")
    ax.tick_params(axis="x", labelsize=9)

    ax = axes[1]
    pivot_pct = pivot.div(pivot.sum(axis=1), axis=0) * 100
    bottom = np.zeros(len(pivot_pct))
    for cls in CLASS_ORDER:
        ax.bar(pivot_pct.index, pivot_pct[cls].values, bottom=bottom,
               color=CLASS_COLORS[cls], edgecolor="white", linewidth=0.5)
        bottom += pivot_pct[cls].values
    ax.set_ylabel("Share of region area (%)")
    ax.set_ylim(0, 100)
    ax.set_title("Class share within region")
    ax.tick_params(axis="x", labelsize=9)

    handles = [Patch(facecolor=CLASS_COLORS[c], label=CLASS_LABELS[c]) for c in CLASS_ORDER]
    fig.legend(handles=handles, loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.05),
               frameon=False, fontsize=9)
    fig.suptitle("Regional breakdown of co-location classes", fontsize=12)
    fig.tight_layout()
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)


def fig04_pressure_type_mix(df: pd.DataFrame, out: Path) -> None:
    stressed = df[df["high_pressure_low_protection_flag"]].copy()
    pressure_cols = {
        "Aquaculture (within 5 km)": "akvakultur_within_5km_n",
        "Dredging (within 5 km)": "dredging_within_5km_n",
        "Platforms (within 10 km)": "platforms_within_10km_n",
        "Windfarms (within 10 km)": "windfarms_within_10km_n",
    }
    rows = []
    for eco in ["macroalgae", "seagrass"]:
        sub = stressed[stressed["ecosystem"] == eco]
        for label, col in pressure_cols.items():
            present = (sub[col] > 0).mean() * 100 if len(sub) else 0
            rows.append({"ecosystem": eco, "pressure": label, "pct": present, "n": len(sub)})
    mix = pd.DataFrame(rows)

    fig, ax = plt.subplots(figsize=(9, 4.5))
    pressure_order = list(pressure_cols.keys())
    y = np.arange(len(pressure_order))
    width = 0.38
    for offset, eco in zip([-width / 2, width / 2], ["macroalgae", "seagrass"]):
        sub = mix[mix["ecosystem"] == eco].set_index("pressure").reindex(pressure_order)
        n = int(sub["n"].iloc[0]) if len(sub) else 0
        ax.barh(y + offset, sub["pct"].values, height=width,
                color=ECO_COLORS[eco], label=f"{eco.capitalize()} (n={n:,})")
        for yi, v in zip(y + offset, sub["pct"].values):
            if pd.notna(v) and v > 0:
                ax.text(v + 1, yi, f"{v:.0f}%", va="center", fontsize=8)
    ax.set_yticks(y)
    ax.set_yticklabels(pressure_order)
    ax.set_xlabel("% of stressed polygons with pressure within buffer")
    ax.set_xlim(0, 105)
    ax.invert_yaxis()
    ax.set_title("Pressure-type mix among stressed polygons\n(high_pressure_low_protection_flag = True)")
    ax.legend(loc="lower right", frameon=False)
    fig.tight_layout()
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)


def fig05_sampling_coverage(df: pd.DataFrame, out: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5), sharey=True)
    for ax, eco in zip(axes, ["macroalgae", "seagrass"]):
        sub = df[df["ecosystem"] == eco]
        total = pd.crosstab(sub["protection_bin"], sub["pressure_bin"], dropna=False) \
            .reindex(index=PROTECTION_LABELS, columns=PRESSURE_LABELS, fill_value=0)
        covered = pd.crosstab(
            sub.loc[sub["study_sites_within_5km_n"] > 0, "protection_bin"],
            sub.loc[sub["study_sites_within_5km_n"] > 0, "pressure_bin"],
            dropna=False,
        ).reindex(index=PROTECTION_LABELS, columns=PRESSURE_LABELS, fill_value=0)
        with np.errstate(divide="ignore", invalid="ignore"):
            pct = np.where(total.values > 0, covered.values / total.values * 100, np.nan)

        im = ax.imshow(pct, cmap="viridis", origin="lower", vmin=0, vmax=max(np.nanmax(pct), 1) if not np.all(np.isnan(pct)) else 1)
        for i in range(pct.shape[0]):
            for j in range(pct.shape[1]):
                tot = total.values[i, j]
                cov = covered.values[i, j]
                if tot == 0:
                    ax.text(j, i, "-", ha="center", va="center", fontsize=9, color="#444444")
                    continue
                ax.text(j, i, f"{cov}/{tot}", ha="center", va="center", fontsize=8,
                        color="white" if not np.isnan(pct[i, j]) and pct[i, j] > 25 else "black")
        ax.set_xticks(range(len(PRESSURE_LABELS)))
        ax.set_xticklabels(PRESSURE_LABELS, fontsize=8)
        ax.set_yticks(range(len(PROTECTION_LABELS)))
        ax.set_yticklabels(PROTECTION_LABELS, fontsize=8)
        ax.set_title(f"{eco.capitalize()}")
        ax.set_xlabel("Co-location pressure index")
        if ax is axes[0]:
            ax.set_ylabel("% of polygon area protected")
        cb = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cb.set_label("% of polygons w/ study site <5 km")
    fig.suptitle("Sampling coverage of the risk matrix\n(cells: 'studied / total'; color = study-site coverage %)",
                 fontsize=12)
    fig.tight_layout()
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)


def regional_stats(df: pd.DataFrame, out: Path) -> None:
    rows = []
    for (region, eco), sub in df.groupby(["canonical_region", "ecosystem"]):
        n = len(sub)
        area_km2 = sub["habitat_area_km2"].sum()
        n_studied = int((sub["study_sites_within_5km_n"] > 0).sum())
        n_stressed = int(sub["high_pressure_low_protection_flag"].sum())
        area_stressed = sub.loc[sub["high_pressure_low_protection_flag"], "habitat_area_km2"].sum()
        top3 = (
            sub.nlargest(3, "colocation_pressure_index")[["habitat_name", "colocation_pressure_index"]]
            .apply(lambda r: f"{r['habitat_name']} (idx={int(r['colocation_pressure_index'])})", axis=1)
            .tolist()
        )
        rows.append({
            "canonical_region": region,
            "ecosystem": eco,
            "n_polygons": n,
            "total_area_km2": round(area_km2, 1),
            "median_pressure_index": float(sub["colocation_pressure_index"].median()),
            "max_pressure_index": int(sub["colocation_pressure_index"].max()),
            "pct_unprotected": round((sub["percent_protected"] == 0).mean() * 100, 1),
            "pct_high_protection": round((sub["percent_protected"] >= 50).mean() * 100, 1),
            "n_high_pressure_low_protection": n_stressed,
            "pct_area_high_pressure_low_protection": round(area_stressed / area_km2 * 100, 2) if area_km2 else 0.0,
            "n_with_study_site_within_5km": n_studied,
            "pct_with_study_site_within_5km": round(n_studied / n * 100, 1) if n else 0.0,
            "top3_pressured_polygons": "; ".join(top3),
        })
    out_df = pd.DataFrame(rows).sort_values(["canonical_region", "ecosystem"]).reset_index(drop=True)
    out_df.to_csv(out, index=False)
    return out_df


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df = load_metrics()
    print(f"Loaded {len(df):,} habitat polygons")

    fig01_risk_matrix(df, OUT_DIR / "fig01_risk_matrix.png")
    fig02_static_maps(df, OUT_DIR / "fig02_pressure_protection_maps.png")
    fig03_regional_breakdown(df, OUT_DIR / "fig03_regional_class_breakdown.png")
    fig04_pressure_type_mix(df, OUT_DIR / "fig04_pressure_type_mix.png")
    fig05_sampling_coverage(df, OUT_DIR / "fig05_sampling_coverage.png")
    stats = regional_stats(df, OUT_DIR / "regional_stress_stats.csv")

    print("\nRegional stress summary:")
    print(stats.to_string(index=False))
    print(f"\nWrote 5 figures + stats CSV to {OUT_DIR.relative_to(REPO_ROOT)}/")


if __name__ == "__main__":
    main()
