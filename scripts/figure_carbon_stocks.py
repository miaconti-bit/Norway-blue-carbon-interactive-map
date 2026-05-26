"""Carbon-stock estimation figures with explicit uncertainty propagation.

The point estimates here largely re-cut numbers already in
data/processed/step2_*. The contribution is making uncertainty visible:
non-parametric bootstrap on the seagrass national stock from the 9
true-point-site measurements, regional disaggregation against the HB19
mapped extent, and a sensitivity analysis on extent definition.

Macroalgae has effectively zero Norwegian site-level stock data; the
2.6 Mt C national figure is Krause-Jensen & Duarte 2016 transfer
function applied to Gundersen 2021 extent. We disaggregate that across
HB19 area but flag explicitly that regional variation is not validated.

Reads:
  data/processed/norway_blue_carbon_master_sites.csv
  data/processed/step2_seagrass_stocks_by_region.csv
  data/processed/step2_national_sequestration.csv
  data/processed/step2_valuation.csv
  data/processed/spatial_analysis/regional_colocation_summary.csv

Writes to figures/carbon_stocks/:
  fig09_seagrass_bootstrap.png
  fig11_carbon_balance_sheet.png
  carbon_stock_estimates.csv

Run:
  MPLCONFIGDIR=/tmp/mplconfig python scripts/figure_carbon_stocks.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parent.parent
PROC = REPO_ROOT / "data" / "processed"
SPATIAL = PROC / "spatial_analysis"
OUT_DIR = REPO_ROOT / "figures" / "carbon_stocks"

MASTER_PATH = PROC / "norway_blue_carbon_master_sites.csv"
STEP2_REGIONAL_PATH = PROC / "step2_seagrass_stocks_by_region.csv"
STEP2_NATIONAL_PATH = PROC / "step2_national_sequestration.csv"
STEP2_VALUATION_PATH = PROC / "step2_valuation.csv"
REGIONAL_SUMMARY_PATH = SPATIAL / "regional_colocation_summary.csv"

# Frigstad 2020 / TemaNord 2020:541 published seagrass extent bounds (km^2).
SEAGRASS_EXTENT_KM2_MEASURED = 60.0
SEAGRASS_EXTENT_KM2_MODELED = 90.0
# Gundersen 2021 macroalgae national modelled extent (km^2).
MACROALGAE_EXTENT_KM2_GUNDERSEN = 5355.0

# Macroalgae national stock (kt C). From step2_national_sequestration.csv:
# Krause-Jensen & Duarte 2016 transfer function * Gundersen 2021 area.
MACROALGAE_NATIONAL_STOCK_KT_C = 2600.0
MACROALGAE_SEQ_MT_CO2_YR = 1.7
MACROALGAE_SEQ_MT_CO2_YR_RANGE = (0.36 * 44 / 12 * 1.0,
                                  4.1 * 44 / 12 * 1.0 / 10)  # placeholder; see step2

ECO_COLORS = {"seagrass": "#74c476", "macroalgae": "#2c6e49"}
REGION_COLORS = {
    "Barents Sea":   "#3b6e8f",
    "Norwegian Sea": "#5fa3a3",
    "Skagerrak":     "#d97a4a",
}
REGION_ORDER = ["Barents Sea", "Norwegian Sea", "Skagerrak"]

# Oslofjord and Skagerrak are both southern Norway and are reported as one
# combined region across all project figures. The canonical "Skagerrak" key
# absorbs Oslofjord (and is the join key against HB19 extent / metrics, which
# already group the south under Skagerrak); this maps it to its display label.
REGION_DISPLAY = {
    "Barents Sea":   "Barents Sea",
    "Norwegian Sea": "Norwegian Sea",
    "Skagerrak":     "Skagerrak (+ Oslofjord)",
}


def region_display(region: str) -> str:
    return REGION_DISPLAY.get(region, region)

BOOTSTRAP_N = 10_000
RNG = np.random.default_rng(seed=20260508)


def load_seagrass_points() -> pd.DataFrame:
    df = pd.read_csv(MASTER_PATH)
    sg = df[(df["ecosystem"] == "seagrass")
            & (df["inventory_record_type"] == "true_point_site")
            & df["carbon_stock_g_m2"].notna()].copy()
    # Combine Oslofjord into Skagerrak (canonical 3-region display cut, matching
    # the HB19 extent grouping used for the area-weighted rollups).
    sg["canonical_region"] = sg["canonical_region"].replace({"Oslofjord": "Skagerrak"})
    return sg[["site_name", "canonical_region", "carbon_stock_g_m2",
               "sample_size_n", "depth_m", "year", "source_short"]].reset_index(drop=True)


def load_step2_regional() -> pd.DataFrame:
    return pd.read_csv(STEP2_REGIONAL_PATH)


def load_hb19_extent() -> pd.DataFrame:
    df = pd.read_csv(REGIONAL_SUMMARY_PATH)
    return df[["ecosystem", "canonical_region", "habitat_polygons_n", "habitat_area_km2"]]


# ---------------------------------------------------------------------------
# fig09: bootstrap CI on national seagrass stock
# ---------------------------------------------------------------------------
def bootstrap_pooled_mean(values: np.ndarray, n: int = BOOTSTRAP_N) -> np.ndarray:
    idx = RNG.integers(0, len(values), size=(n, len(values)))
    return values[idx].mean(axis=1)


def fig09_bootstrap(sg: pd.DataFrame, hb19: pd.DataFrame, out: Path) -> dict:
    """National carbon-stock estimates and their uncertainty (seagrass + macroalgae)."""
    sg_color, ma_color, dark, pub_color = (
        ECO_COLORS["seagrass"], ECO_COLORS["macroalgae"], "#1b5e20", "#b3541e")

    # Seagrass: bootstrap the site densities, scale by HB19 extent -> national stock.
    seagrass_extent_km2 = hb19[hb19["ecosystem"] == "seagrass"]["habitat_area_km2"].sum()
    site_vals = sg["carbon_stock_g_m2"].values
    pooled_means = bootstrap_pooled_mean(site_vals)
    national_kt_c = pooled_means * seagrass_extent_km2 * 1_000_000 / 1e9
    median = float(np.median(national_kt_c))
    ci_low, ci_high = (float(v) for v in np.percentile(national_kt_c, [2.5, 97.5]))

    # Macroalgae: fixed literature density x extent; uncertainty = mapped vs modelled extent.
    ma_density = MACROALGAE_NATIONAL_STOCK_KT_C / MACROALGAE_EXTENT_KM2_GUNDERSEN * 1000.0
    ma_hb19_area = hb19[hb19["ecosystem"] == "macroalgae"]["habitat_area_km2"].sum()
    ma_mapped = ma_density * ma_hb19_area * 1_000_000 / 1e9
    ma_modelled = float(MACROALGAE_NATIONAL_STOCK_KT_C)
    ma_lo, ma_hi = sorted([ma_mapped, ma_modelled])

    def _clean(ax):
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    fig, axes = plt.subplots(2, 2, figsize=(13, 9.5))
    xs = np.arange(2)

    # (A) Seagrass bootstrap distribution
    ax = axes[0, 0]
    ax.hist(national_kt_c, bins=40, color=sg_color, alpha=0.85,
            edgecolor="white", linewidth=0.4)
    ymax_a = ax.get_ylim()[1]
    ax.axvspan(ci_low, ci_high, color=sg_color, alpha=0.18, zorder=0)
    ax.axvline(median, color=dark, linewidth=2.0)
    for v in (ci_low, ci_high):
        ax.axvline(v, color=dark, linestyle="--", linewidth=1.2)
    ax.axvline(357.6, color=pub_color, linewidth=1.6)
    ax.set_xlim(right=max(float(national_kt_c.max()), 357.6) * 1.04)
    ax.text(0.03, 0.97,
            f"{median:,.0f} kt C\n95% CI  {ci_low:,.0f}–{ci_high:,.0f}\n"
            f"(± {(ci_high - ci_low) / 2 / median * 100:.0f}%)",
            transform=ax.transAxes, va="top", ha="left", fontsize=11,
            fontweight="bold", color=dark,
            bbox=dict(facecolor="white", edgecolor=dark, boxstyle="round,pad=0.5", linewidth=1.0))
    ax.text(357.6, ymax_a * 0.97, "Frigstad 2020 ", color=pub_color,
            fontsize=7.5, ha="right", va="top")
    ax.set_xlabel("National seagrass stock (kt C)", fontsize=9.5)
    ax.set_ylabel("Bootstrap resamples", fontsize=9.5)
    ax.set_title("A.  Seagrass — Bootstrap Estimate", loc="left",
                 fontweight="bold", fontsize=12)
    _clean(ax)

    # (B) The site measurements that drive the uncertainty
    ax = axes[0, 1]
    rng = np.random.default_rng(3)
    xj = rng.uniform(-0.13, 0.13, len(site_vals))
    ax.scatter(xj, site_vals, s=80, color=sg_color, edgecolor="black",
               linewidth=0.6, alpha=0.85, zorder=3)
    mean_v = float(site_vals.mean())
    ax.axhline(mean_v, color=dark, linestyle="--", linewidth=1.2)
    ax.text(0.45, mean_v, f"mean {mean_v:,.0f}", fontsize=8, color=dark,
            va="bottom", ha="right")
    ax.text(0.97, 0.97,
            f"n = {len(site_vals)} sites\n"
            f"range {site_vals.min():,.0f}–{site_vals.max():,.0f}\n"
            f"CV = {site_vals.std(ddof=1) / mean_v * 100:.0f}%",
            transform=ax.transAxes, va="top", ha="right", fontsize=8.5, color="#333",
            bbox=dict(facecolor="white", edgecolor="#ddd", boxstyle="round,pad=0.4", linewidth=0.6))
    ax.set_xlim(-0.5, 0.5)
    ax.set_xticks([])
    ax.set_ylim(0, site_vals.max() * 1.12)
    ax.set_ylabel("Site carbon density (g C m⁻²)", fontsize=9.5)
    ax.set_title("B.  Why So Uncertain — the 9 Measurements", loc="left",
                 fontweight="bold", fontsize=12)
    _clean(ax)

    # (C) Macroalgae national stock — extent-based range (no field data to bootstrap)
    ax = axes[1, 0]
    svals = [ma_mapped, ma_modelled]
    ax.bar(xs, svals, width=0.55, color=ma_color, edgecolor="black", linewidth=0.6)
    for x, v in zip(xs, svals):
        ax.text(x, v + max(svals) * 0.02, f"{v:,.0f} kt C", ha="center",
                va="bottom", fontsize=9, fontweight="bold")
    ax.set_xticks(xs)
    ax.set_xticklabels(["HB19 mapped\nextent", "Gundersen 2021\nmodelled extent"], fontsize=8.5)
    ax.set_ylim(0, max(svals) * 1.18)
    ax.set_ylabel("Macroalgae national stock (kt C)", fontsize=9.5)
    ax.set_title("C.  Macroalgae — Extent Range (no field data)", loc="left",
                 fontweight="bold", fontsize=12)
    _clean(ax)

    # (D) Both habitats, log scale, with their (different) uncertainty
    ax = axes[1, 1]
    meds = [median, (ma_lo + ma_hi) / 2]
    lo_err = [median - ci_low, (ma_hi - ma_lo) / 2]
    hi_err = [ci_high - median, (ma_hi - ma_lo) / 2]
    ax.bar(xs, meds, width=0.5, color=[sg_color, ma_color], edgecolor="black",
           linewidth=0.6, yerr=[lo_err, hi_err], capsize=8,
           error_kw=dict(elinewidth=1.5, capthick=1.5))
    ax.set_yscale("log")
    ax.set_ylim(50, 6000)
    val_lbls = [f"{median:,.0f}\n[{ci_low:,.0f}–{ci_high:,.0f}]",
                f"{(ma_lo + ma_hi) / 2:,.0f}\n[{ma_lo:,.0f}–{ma_hi:,.0f}]"]
    unc_lbls = ["95% bootstrap CI", "extent range"]
    for x, m, he, vl, ul in zip(xs, meds, hi_err, val_lbls, unc_lbls):
        ax.text(x, (m + he) * 1.3, vl, ha="center", va="bottom",
                fontsize=8.5, fontweight="bold")
        ax.text(x, 62, ul, ha="center", va="bottom", fontsize=7.5,
                style="italic", color="#555")
    ax.set_xticks(xs)
    ax.set_xticklabels(["Seagrass", "Macroalgae"], fontsize=10)
    ax.set_ylabel("National stock (kt C, log scale)", fontsize=9.5)
    ax.set_title("D.  Both Habitats — Stock with Uncertainty", loc="left",
                 fontweight="bold", fontsize=12)
    _clean(ax)

    fig.suptitle("Norwegian Blue Carbon Stock: Estimates and Uncertainty",
                 fontsize=14, fontweight="bold", y=0.985)
    fig.text(0.5, 0.012,
             f"Seagrass (A, B): non-parametric bootstrap ({BOOTSTRAP_N:,} resamples) of {len(site_vals)} site "
             f"measurements (Gagnon 2024; Rohr 2018) × HB19 extent ({seagrass_extent_km2:.0f} km²); the wide CI "
             "reflects few, highly variable sites (B). Orange line in A = Frigstad 2020 published value. "
             "Macroalgae (C): national density from a literature transfer function (Krause-Jensen & Duarte 2016) — "
             "no Norwegian field data, so it cannot be bootstrapped; range = mapped vs modelled extent. "
             "D compares both habitats — note the two different uncertainty types (sampling CI vs extent range).",
             fontsize=7.3, color="#666", ha="center", style="italic")
    fig.subplots_adjust(left=0.08, right=0.97, top=0.91, bottom=0.13, hspace=0.42, wspace=0.22)
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)

    return {
        "pooled_median_kt_c": median,
        "pooled_ci_low": ci_low,
        "pooled_ci_high": ci_high,
        "hb19_extent_km2": float(seagrass_extent_km2),
    }


# ---------------------------------------------------------------------------
# fig11: balance sheet
# ---------------------------------------------------------------------------
def fig11_balance_sheet(sg: pd.DataFrame, hb19: pd.DataFrame, out: Path) -> None:
    sg_color, ma_color = ECO_COLORS["seagrass"], ECO_COLORS["macroalgae"]
    seagrass_extent_km2 = hb19[hb19["ecosystem"] == "seagrass"]["habitat_area_km2"].sum()
    macroalgae_extent_km2 = hb19[hb19["ecosystem"] == "macroalgae"]["habitat_area_km2"].sum()

    pooled_means = bootstrap_pooled_mean(sg["carbon_stock_g_m2"].values)
    sg_kt_c = pooled_means * seagrass_extent_km2 * 1_000_000 / 1e9
    sg_med = float(np.median(sg_kt_c))
    sg_lo, sg_hi = (float(v) for v in np.percentile(sg_kt_c, [2.5, 97.5]))
    sg_density_med = float(np.median(pooled_means))

    macroalgae_density_g_m2 = MACROALGAE_NATIONAL_STOCK_KT_C / MACROALGAE_EXTENT_KM2_GUNDERSEN * 1000.0
    ma_kt_c = macroalgae_density_g_m2 * macroalgae_extent_km2 * 1_000_000 / 1e9

    # Annual sequestration (Mt CO2/yr): seagrass Frigstad 2020; macroalgae Krause-Jensen
    # export-fraction range 23-62% -> 1.32-4.11 Mt CO2/yr around a 1.7 median.
    seq_sg_med, seq_sg_sd = 0.0168, 0.0046
    seq_ma_med = 1.7
    seq_ma_lo = 0.36 * 44 / 12
    seq_ma_hi = 1.12 * 44 / 12
    valuation = pd.read_csv(STEP2_VALUATION_PATH)

    fig, axes = plt.subplots(2, 2, figsize=(13, 9.5))
    eco = ["Seagrass", "Macroalgae"]
    eco_cols = [sg_color, ma_color]

    def _clean(ax):
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    # (A) National carbon stock
    ax = axes[0, 0]
    bars = ax.bar(eco, [sg_med, ma_kt_c],
                  yerr=[[sg_med - sg_lo, 0.0], [sg_hi - sg_med, 0.0]],
                  capsize=6, color=eco_cols, edgecolor="black", linewidth=0.6)
    ax.set_yscale("log")
    ax.set_ylim(top=ma_kt_c * 5)
    for b, lbl in zip(bars,
                      [f"{sg_med:,.0f} kt C\n[{sg_lo:,.0f}–{sg_hi:,.0f}]",
                       f"{ma_kt_c:,.0f} kt C\n(point est.)"]):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() * 1.3, lbl,
                ha="center", va="bottom", fontsize=8.5)
    ax.set_ylabel("Stored carbon (kt C, log scale)", fontsize=9.5)
    ax.set_title("A.  National Carbon Stock", loc="left", fontweight="bold", fontsize=12)
    _clean(ax)

    # (B) Annual CO2 sequestration
    ax = axes[0, 1]
    seq_med = [seq_sg_med, seq_ma_med]
    seq_hi_err = [seq_sg_sd, seq_ma_hi - seq_ma_med]
    ax.bar(eco, seq_med,
           yerr=[[seq_sg_sd, seq_ma_med - seq_ma_lo], seq_hi_err],
           capsize=6, color=eco_cols, edgecolor="black", linewidth=0.6)
    ax.set_yscale("log")
    ax.set_ylim(0.005, seq_ma_hi * 4)
    for i, (v, e, lbl) in enumerate(zip(
            seq_med, seq_hi_err,
            [f"{seq_sg_med:.3f}", f"{seq_ma_med:.2f}  [{seq_ma_lo:.2f}–{seq_ma_hi:.2f}]"])):
        ax.text(i, (v + e) * 1.35, lbl, ha="center", va="bottom", fontsize=8.5)
    ax.set_ylabel("Annual sequestration\n(Mt CO₂ yr⁻¹, log scale)", fontsize=9.5)
    ax.set_title("B.  Annual CO₂ Sequestration", loc="left", fontweight="bold", fontsize=12)
    _clean(ax)

    # (C) Annual value = annual sequestration x carbon price
    ax = axes[1, 0]
    scen_order = ["EU_ETS_2024_EUR_tCO2", "SCC_US_2023_USD_tCO2", "VCM_blue_carbon_USD_tCO2"]
    scen_labels = ["EU ETS 2024\n€65 / tCO₂",
                   "Social Cost of\nCarbon 2023\n$190 / tCO₂",
                   "Voluntary blue\ncarbon\n$20 / tCO₂"]
    pos = np.arange(len(scen_order))
    width = 0.38
    all_vals = []
    for offset, ecosystem, col in zip([-width / 2, width / 2],
                                      ["seagrass", "macroalgae"], eco_cols):
        sub = (valuation[valuation["ecosystem"] == ecosystem]
               .set_index("price_scenario").reindex(scen_order))
        vals = sub["annual_value_million_usd"].values
        all_vals.extend(vals)
        ax.bar(pos + offset, vals, width=width, color=col, edgecolor="black",
               linewidth=0.6, label=ecosystem.capitalize())
        for x, v in zip(pos + offset, vals):
            ax.text(x, v * 1.4, f"${v:,.0f}M" if v >= 1 else f"${v:.1f}M",
                    ha="center", va="bottom", fontsize=7.5)
    ax.set_yscale("log")
    ax.set_ylim(0.15, max(all_vals) * 4)
    ax.set_xticks(pos)
    ax.set_xticklabels(scen_labels, fontsize=8)
    ax.set_ylabel("Annual value\n(M USD yr⁻¹, log scale)", fontsize=9.5)
    ax.set_title("C.  Annual Sequestration Value", loc="left", fontweight="bold", fontsize=12)
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    _clean(ax)

    # (D) Regional seagrass stock (macroalgae has no validated regional breakdown)
    ax = axes[1, 1]
    reg = hb19[hb19["ecosystem"] == "seagrass"].copy()
    reg["stock_kt_c"] = reg["habitat_area_km2"] * sg_density_med * 1_000_000 / 1e9
    reg = reg.groupby("canonical_region")["stock_kt_c"].sum()
    reg = reg.reindex([r for r in REGION_ORDER if r in reg.index])
    xr = np.arange(len(reg))
    ax.bar(xr, reg.values, width=0.6,
           color=[REGION_COLORS.get(r, "#888") for r in reg.index],
           edgecolor="black", linewidth=0.6)
    for i, v in zip(xr, reg.values):
        ax.text(i, v + max(reg.values) * 0.02, f"{v:,.0f}",
                ha="center", va="bottom", fontsize=8.5)
    ax.set_xticks(xr)
    ax.set_xticklabels([region_display(r) for r in reg.index], fontsize=8.5)
    ax.set_ylim(0, max(reg.values) * 1.2)
    ax.set_ylabel("Seagrass stock (kt C)", fontsize=9.5)
    ax.set_title("D.  Regional Seagrass Stock", loc="left", fontweight="bold", fontsize=12)
    ax.annotate("macroalgae: national estimate only\n(no validated regional breakdown)",
                xy=(0.96, 0.96), xycoords="axes fraction", ha="right", va="top",
                fontsize=7.5, style="italic", color="#777")
    _clean(ax)

    fig.suptitle("Norwegian Blue Carbon Balance Sheet: Stock, Sequestration, and Value",
                 fontsize=14, fontweight="bold", y=0.98)
    fig.text(0.5, 0.012,
             "Seagrass: bootstrap of 9 site measurements × HB19 extent (95% CI shown). "
             "Macroalgae: Krause-Jensen & Duarte 2016 transfer function × Gundersen 2021 extent "
             "(national point estimate; no Norwegian field data). "
             "Sequestration: Frigstad 2020 (seagrass); Krause-Jensen export-fraction 23–62% (macroalgae). "
             "Value (C) = annual CO₂ sequestration (B) × carbon price, in USD — "
             "EU ETS 2024 (€65), US Social Cost of Carbon 2023 ($190), Voluntary blue-carbon ($20) per tCO₂.",
             fontsize=7.3, color="#666", ha="center", style="italic")
    fig.subplots_adjust(left=0.07, right=0.97, top=0.91, bottom=0.13, hspace=0.45, wspace=0.24)
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Stats CSV: regional + national stock estimates with CIs
# ---------------------------------------------------------------------------
def stats_csv(sg: pd.DataFrame, hb19: pd.DataFrame, bootstrap_summary: dict, out: Path) -> None:
    pooled_means = bootstrap_pooled_mean(sg["carbon_stock_g_m2"].values)
    macroalgae_density = MACROALGAE_NATIONAL_STOCK_KT_C / MACROALGAE_EXTENT_KM2_GUNDERSEN * 1000.0

    rows = []
    for _, r in hb19.iterrows():
        eco = r["ecosystem"]
        if eco == "seagrass":
            stock_kt = pooled_means * r["habitat_area_km2"] * 1_000_000 / 1e9
            rows.append({
                "ecosystem": eco,
                "canonical_region": r["canonical_region"],
                "habitat_area_km2": round(r["habitat_area_km2"], 2),
                "stock_density_g_m2_median": round(float(np.median(pooled_means)), 1),
                "stock_density_g_m2_ci_low": round(float(np.percentile(pooled_means, 2.5)), 1),
                "stock_density_g_m2_ci_high": round(float(np.percentile(pooled_means, 97.5)), 1),
                "stock_kt_c_median": round(float(np.median(stock_kt)), 2),
                "stock_kt_c_ci_low": round(float(np.percentile(stock_kt, 2.5)), 2),
                "stock_kt_c_ci_high": round(float(np.percentile(stock_kt, 97.5)), 2),
                "uncertainty_source": "non-parametric bootstrap of 9 site measurements",
            })
        else:
            stock_kt = macroalgae_density * r["habitat_area_km2"] * 1_000_000 / 1e9
            rows.append({
                "ecosystem": eco,
                "canonical_region": r["canonical_region"],
                "habitat_area_km2": round(r["habitat_area_km2"], 2),
                "stock_density_g_m2_median": round(macroalgae_density, 1),
                "stock_density_g_m2_ci_low": np.nan,
                "stock_density_g_m2_ci_high": np.nan,
                "stock_kt_c_median": round(float(stock_kt), 2),
                "stock_kt_c_ci_low": np.nan,
                "stock_kt_c_ci_high": np.nan,
                "uncertainty_source": "Krause-Jensen 2016 transfer function (no Norwegian field data)",
            })
    df = pd.DataFrame(rows).sort_values(["ecosystem", "canonical_region"]).reset_index(drop=True)
    df.to_csv(out, index=False)
    return df


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sg = load_seagrass_points()
    hb19 = load_hb19_extent()
    print(f"Loaded {len(sg)} seagrass site-level measurements")
    print(f"HB19 seagrass extent: {hb19[hb19['ecosystem']=='seagrass']['habitat_area_km2'].sum():.1f} km^2")
    print(f"HB19 macroalgae extent: {hb19[hb19['ecosystem']=='macroalgae']['habitat_area_km2'].sum():.1f} km^2")

    bootstrap_summary = fig09_bootstrap(sg, hb19, OUT_DIR / "fig09_seagrass_bootstrap.png")
    fig11_balance_sheet(sg, hb19, OUT_DIR / "fig11_carbon_balance_sheet.png")
    stats_csv(sg, hb19, bootstrap_summary, OUT_DIR / "carbon_stock_estimates.csv")

    print("\nBootstrap summary:")
    for k, v in bootstrap_summary.items():
        print(f"  {k}: {v:.2f}")
    print(f"\nWrote 2 figures + 1 CSV to {OUT_DIR.relative_to(REPO_ROOT)}/")


if __name__ == "__main__":
    main()
