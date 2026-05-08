"""Static stress-diagnostic figure pack for Norway blue-carbon habitats.

Reads:
  data/processed/spatial_analysis/habitat_colocation_metrics.csv

Writes to figures/stress_diagnostics/:
  fig01_risk_matrix.png             - 2D bin counts of pressure x strict protection, by ecosystem
  fig02_pressure_protection_maps.png - static centroid maps (pressure / strict / permissive)
  fig03_regional_class_breakdown.png - habitat area by colocation class x region (strict definition)
  fig04_pressure_type_mix.png       - which pressures dominate among stressed polygons
  fig05_sampling_coverage.png       - pressure x protection grid coloured by study coverage
  fig06_protection_definition.png   - how protection share collapses across the three tiers
  fig07_importance_tier_breakdown.png - stress class share within each HB19 value code (A/B/C)
  regional_stress_stats.csv         - per region x ecosystem x importance summary table

Definition note:
  We treat the strict-MPA fraction (`percent_mpa`, MarintVerneomraade only)
  as the operational protection axis. The broader `percent_protected`
  counts 884 marine-relevant verneomrader, most of which are bird-focused
  coastal reserves that do not regulate marine activities. See
  `protection_tier_definitions` in the manifest.

Run from repo root:
  MPLCONFIGDIR=/tmp/mplconfig /opt/anaconda3/envs/ella-capstone/bin/python scripts/figure_stress_diagnostics.py
  (or any env with matplotlib + pandas + numpy)
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

# Strict definition: enforceable marine MPA (MarintVerneomraade) overlap.
PROTECTION_COL = "percent_mpa"
PROTECTION_LABEL = "% of polygon area in strict MPA"

CLASS_ORDER = ["pressure_unprotected", "pressure_protected", "protected_no_pressure", "study_covered", "mapped_gap"]
CLASS_COLORS = {
    "pressure_unprotected": "#c1272d",
    "pressure_protected": "#f6ae2d",
    "protected_no_pressure": "#2e8b57",
    "study_covered": "#4a6fa5",
    "mapped_gap": "#9aa0a6",
}
CLASS_LABELS = {
    "pressure_unprotected": "Pressure, <1% strict MPA",
    "pressure_protected": "Pressure, >=10% strict MPA",
    "protected_no_pressure": ">=10% strict MPA, no pressure",
    "study_covered": "Study site within 5 km",
    "mapped_gap": "Mapped, no other signal",
}

ECO_COLORS = {"macroalgae": "#0a6b54", "seagrass": "#7d3c98"}
NORWAY_LON = (3.5, 32.0)
NORWAY_LAT = (57.5, 71.5)

VALUE_CODE_LABELS = {"A": "A: Svært viktig", "B": "B: Viktig", "C": "C: Lokalt viktig"}
VALUE_CODE_ORDER = ["A", "B", "C"]


def colocation_class_strict(row: pd.Series) -> str:
    pct_strict = float(row[PROTECTION_COL] or 0)
    pressure = float(row["colocation_pressure_index"] or 0) > 0
    if pressure and pct_strict < 1:
        return "pressure_unprotected"
    if pressure and pct_strict >= 10:
        return "pressure_protected"
    if pct_strict >= 10:
        return "protected_no_pressure"
    if float(row["study_sites_within_5km_n"] or 0) > 0:
        return "study_covered"
    return "mapped_gap"


def load_metrics() -> pd.DataFrame:
    df = pd.read_csv(METRICS_PATH)
    df["habitat_area_km2"] = df["habitat_area_m2"] / 1e6
    df["map_class"] = df.apply(colocation_class_strict, axis=1)
    df["pressure_bin"] = pd.cut(df["colocation_pressure_index"], bins=PRESSURE_BINS, labels=PRESSURE_LABELS)
    df["protection_bin"] = pd.cut(df[PROTECTION_COL], bins=PROTECTION_BINS, labels=PROTECTION_LABELS, include_lowest=True)
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
            ax.set_ylabel(PROTECTION_LABEL)
        cb = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cb.set_label("polygon count (log)")
    fig.suptitle("Risk matrix: pressure x strict marine protection (per HB19 polygon)", y=1.02, fontsize=12)
    fig.tight_layout()
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)


def fig02_static_maps(df: pd.DataFrame, out: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(16, 8.5))

    pressure_levels = [0, 1, 3, 6, 12, df["colocation_pressure_index"].max() + 1]
    pressure_cmap = ListedColormap(["#dddddd", "#fee08b", "#fdae61", "#f46d43", "#d73027"])
    pressure_norm = BoundaryNorm(pressure_levels, pressure_cmap.N)

    ax = axes[0]
    ds = df.sort_values("colocation_pressure_index")
    sizes = np.clip(ds["habitat_area_km2"].values * 4, 1.5, 60)
    ax.scatter(ds["centroid_lon"], ds["centroid_lat"],
               c=ds["colocation_pressure_index"], cmap=pressure_cmap, norm=pressure_norm,
               s=sizes, linewidths=0, alpha=0.85)
    set_norway_aspect(ax)
    ax.set_title("Co-location pressure index")
    cb = plt.colorbar(mpl.cm.ScalarMappable(norm=pressure_norm, cmap=pressure_cmap),
                      ax=ax, fraction=0.04, pad=0.04, ticks=pressure_levels)
    cb.set_label("pressure index")

    protection_levels = [0, 0.001, 1, 10, 50, 100.001]
    protection_cmap = ListedColormap(["#dddddd", "#c6dbef", "#6baed6", "#3182bd", "#08519c"])
    protection_norm = BoundaryNorm(protection_levels, protection_cmap.N)

    for ax, col, title in zip(
        axes[1:],
        ["percent_mpa", "percent_protected"],
        ["Strict MPA overlap (MarintVerneomraade)",
         "Permissive overlap\n(any verneomrade; mostly bird reserves)"],
    ):
        ds = df.sort_values(col)
        sizes = np.clip(ds["habitat_area_km2"].values * 4, 1.5, 60)
        ax.scatter(ds["centroid_lon"], ds["centroid_lat"],
                   c=ds[col], cmap=protection_cmap, norm=protection_norm,
                   s=sizes, linewidths=0, alpha=0.85)
        set_norway_aspect(ax)
        ax.set_title(title)
        cb = plt.colorbar(mpl.cm.ScalarMappable(norm=protection_norm, cmap=protection_cmap),
                          ax=ax, fraction=0.04, pad=0.04, ticks=[0, 1, 10, 50, 100])
        cb.set_label("% of polygon area")

    fig.suptitle("Pressure and protection per HB19 polygon (centroids; size ~ habitat area)",
                 fontsize=12)
    fig.tight_layout()
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _stack_plot(ax: plt.Axes, pivot: pd.DataFrame, percent: bool) -> None:
    bottom = np.zeros(len(pivot))
    for cls in CLASS_ORDER:
        ax.bar(pivot.index, pivot[cls].values, bottom=bottom,
               color=CLASS_COLORS[cls], edgecolor="white", linewidth=0.5)
        bottom += pivot[cls].values
    if percent:
        ax.set_ylim(0, 100)
        ax.set_ylabel("Share of region area (%)")
    else:
        ax.set_ylabel("Habitat area (km^2)")
    ax.tick_params(axis="x", labelsize=9)


def fig03_regional_breakdown(df: pd.DataFrame, out: Path) -> None:
    pivot = (
        df.pivot_table(index="canonical_region", columns="map_class",
                       values="habitat_area_km2", aggfunc="sum", fill_value=0)
        .reindex(columns=CLASS_ORDER, fill_value=0)
    )
    region_order = pivot.sum(axis=1).sort_values(ascending=False).index.tolist()
    pivot = pivot.reindex(region_order)
    pivot_pct = pivot.div(pivot.sum(axis=1), axis=0) * 100

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    _stack_plot(axes[0], pivot, percent=False)
    axes[0].set_title("Total habitat area by class (strict-protection definition)")
    _stack_plot(axes[1], pivot_pct, percent=True)
    axes[1].set_title("Class share within region")

    handles = [Patch(facecolor=CLASS_COLORS[c], label=CLASS_LABELS[c]) for c in CLASS_ORDER]
    fig.legend(handles=handles, loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.08),
               frameon=False, fontsize=9)
    fig.suptitle("Regional breakdown of co-location classes", fontsize=12)
    fig.tight_layout()
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)


def fig04_pressure_type_mix(df: pd.DataFrame, out: Path) -> None:
    stressed = df[df["high_pressure_no_strict_protection_flag"]].copy()
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
    ax.set_title("Pressure-type mix among stressed polygons\n"
                 "(pressure > 0 AND <1% in a strict marine MPA)")
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

        vmax = max(np.nanmax(pct), 1) if not np.all(np.isnan(pct)) else 1
        im = ax.imshow(pct, cmap="viridis", origin="lower", vmin=0, vmax=vmax)
        for i in range(pct.shape[0]):
            for j in range(pct.shape[1]):
                tot = total.values[i, j]
                cov = covered.values[i, j]
                if tot == 0:
                    ax.text(j, i, "-", ha="center", va="center", fontsize=9, color="#444444")
                    continue
                ax.text(j, i, f"{cov}/{tot}", ha="center", va="center", fontsize=8,
                        color="white" if not np.isnan(pct[i, j]) and pct[i, j] > vmax * 0.5 else "black")
        ax.set_xticks(range(len(PRESSURE_LABELS)))
        ax.set_xticklabels(PRESSURE_LABELS, fontsize=8)
        ax.set_yticks(range(len(PROTECTION_LABELS)))
        ax.set_yticklabels(PROTECTION_LABELS, fontsize=8)
        ax.set_title(f"{eco.capitalize()}")
        ax.set_xlabel("Co-location pressure index")
        if ax is axes[0]:
            ax.set_ylabel(PROTECTION_LABEL)
        cb = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cb.set_label("% of polygons w/ study site <5 km")
    fig.suptitle("Sampling coverage of the risk matrix\n(cells: 'studied / total'; color = study-site coverage %)",
                 fontsize=12)
    fig.tight_layout()
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)


def fig06_protection_definition(df: pd.DataFrame, out: Path) -> None:
    """How much of each region's habitat AREA falls in each protection tier."""
    rows = []
    for (region, eco), sub in df.groupby(["canonical_region", "ecosystem"]):
        total_area = sub["habitat_area_m2"].sum()
        if total_area == 0:
            continue
        rows.append({
            "region_eco": f"{region}\n{eco}",
            "permissive_only": (sub["protected_area_m2"].sum() - sub["substantive_area_m2"].sum()) / total_area * 100,
            "substantive_only": (sub["substantive_area_m2"].sum() - sub["mpa_area_m2"].sum()) / total_area * 100,
            "strict_mpa": sub["mpa_area_m2"].sum() / total_area * 100,
            "no_overlap": (1 - sub["protected_area_m2"].sum() / total_area) * 100,
        })
    tier_df = pd.DataFrame(rows).set_index("region_eco")
    tier_df = tier_df.sort_values("strict_mpa", ascending=True)

    fig, ax = plt.subplots(figsize=(10, 5))
    colors = {"strict_mpa": "#1b6e3d", "substantive_only": "#7fbf7b",
              "permissive_only": "#d9b3a3", "no_overlap": "#e0e0e0"}
    labels = {
        "strict_mpa": "Strict MPA (MarintVerneomraade only)",
        "substantive_only": "Substantive (Nasjonalpark / IUCN II/Ib, beyond strict)",
        "permissive_only": "Permissive only (bird reserves etc.)",
        "no_overlap": "No verneomrade overlap",
    }
    order = ["strict_mpa", "substantive_only", "permissive_only", "no_overlap"]
    bottom = np.zeros(len(tier_df))
    for col in order:
        ax.barh(tier_df.index, tier_df[col].values, left=bottom,
                color=colors[col], edgecolor="white", linewidth=0.5, label=labels[col])
        bottom += tier_df[col].values
    ax.set_xlim(0, 100)
    ax.set_xlabel("Share of regional habitat area (%)")
    ax.set_title("Protection coverage collapses under stricter definitions\n"
                 "(area-weighted; MarintVerneomraade is the only operational marine MPA category)")
    ax.legend(loc="lower right", frameon=False, fontsize=8)
    ax.tick_params(axis="y", labelsize=9)
    fig.tight_layout()
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)


def fig07_importance_breakdown(df: pd.DataFrame, out: Path) -> None:
    """Stress-class share within each HB19 importance tier (A/B/C), area-weighted."""
    fig, axes = plt.subplots(1, 3, figsize=(15, 5), sharey=True)
    for ax, code in zip(axes, VALUE_CODE_ORDER):
        sub = df[df["value_code"] == code]
        if sub.empty:
            ax.set_visible(False)
            continue
        pivot = (
            sub.pivot_table(index="canonical_region", columns="map_class",
                            values="habitat_area_km2", aggfunc="sum", fill_value=0)
            .reindex(columns=CLASS_ORDER, fill_value=0)
        )
        region_order = pivot.sum(axis=1).sort_values(ascending=False).index.tolist()
        pivot = pivot.reindex(region_order)
        pivot_pct = pivot.div(pivot.sum(axis=1), axis=0) * 100

        bottom = np.zeros(len(pivot_pct))
        for cls in CLASS_ORDER:
            ax.bar(pivot_pct.index, pivot_pct[cls].values, bottom=bottom,
                   color=CLASS_COLORS[cls], edgecolor="white", linewidth=0.5)
            bottom += pivot_pct[cls].values
        ax.set_ylim(0, 100)
        total_km2 = sub["habitat_area_km2"].sum()
        ax.set_title(f"{VALUE_CODE_LABELS[code]}\n"
                     f"(n={len(sub):,} polygons; {total_km2:,.0f} km^2)")
        ax.tick_params(axis="x", labelsize=8)
        if ax is axes[0]:
            ax.set_ylabel("Share of importance-tier area (%)")

    handles = [Patch(facecolor=CLASS_COLORS[c], label=CLASS_LABELS[c]) for c in CLASS_ORDER]
    fig.legend(handles=handles, loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.08),
               frameon=False, fontsize=9)
    fig.suptitle("Stress class by HB19 importance tier (area-weighted)\n"
                 "A = Svært viktig (very important) ... C = Lokalt viktig (locally important)",
                 fontsize=12)
    fig.tight_layout()
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)


def regional_stats(df: pd.DataFrame, out: Path) -> pd.DataFrame:
    rows = []
    grouper = df.groupby(["canonical_region", "ecosystem", "value_code"], dropna=False)
    for (region, eco, code), sub in grouper:
        n = len(sub)
        area_km2 = sub["habitat_area_km2"].sum()
        if area_km2 == 0:
            continue
        n_studied = int((sub["study_sites_within_5km_n"] > 0).sum())
        n_stressed_strict = int(sub["high_pressure_no_strict_protection_flag"].sum())
        area_stressed_strict = sub.loc[sub["high_pressure_no_strict_protection_flag"], "habitat_area_km2"].sum()
        n_stressed_substantive = int(sub["high_pressure_no_substantive_protection_flag"].sum())
        rows.append({
            "canonical_region": region,
            "ecosystem": eco,
            "value_code": code,
            "value_label": sub["value_label"].iloc[0],
            "n_polygons": n,
            "total_area_km2": round(area_km2, 2),
            "median_pressure_index": float(sub["colocation_pressure_index"].median()),
            "max_pressure_index": int(sub["colocation_pressure_index"].max()),
            "pct_area_unprotected_permissive": round((1 - sub["protected_area_m2"].sum() / sub["habitat_area_m2"].sum()) * 100, 1),
            "pct_area_in_strict_mpa": round(sub["mpa_area_m2"].sum() / sub["habitat_area_m2"].sum() * 100, 2),
            "pct_area_in_substantive": round(sub["substantive_area_m2"].sum() / sub["habitat_area_m2"].sum() * 100, 2),
            "n_high_pressure_no_strict_protection": n_stressed_strict,
            "pct_area_high_pressure_no_strict_protection": round(area_stressed_strict / area_km2 * 100, 2),
            "n_high_pressure_no_substantive_protection": n_stressed_substantive,
            "n_with_study_site_within_5km": n_studied,
            "pct_with_study_site_within_5km": round(n_studied / n * 100, 1),
        })
    out_df = pd.DataFrame(rows).sort_values(["canonical_region", "ecosystem", "value_code"]).reset_index(drop=True)
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
    fig06_protection_definition(df, OUT_DIR / "fig06_protection_definition.png")
    fig07_importance_breakdown(df, OUT_DIR / "fig07_importance_tier_breakdown.png")
    stats = regional_stats(df, OUT_DIR / "regional_stress_stats.csv")

    print("\nRegional x importance summary (selected columns):")
    print(stats[["canonical_region", "ecosystem", "value_code", "n_polygons",
                 "total_area_km2", "pct_area_in_strict_mpa",
                 "pct_area_high_pressure_no_strict_protection",
                 "pct_with_study_site_within_5km"]].to_string(index=False))
    print(f"\nWrote 7 figures + stats CSV to {OUT_DIR.relative_to(REPO_ROOT)}/")


if __name__ == "__main__":
    main()
