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
  data/processed/spatial_analysis/habitat_colocation_metrics.csv

Writes to figures/carbon_stocks/:
  fig08_seagrass_field_measurements.png
  fig09_seagrass_bootstrap.png
  fig10_extent_sensitivity.png
  fig11_carbon_balance_sheet.png
  fig12_carbon_at_risk.png
  carbon_stock_estimates.csv

Run:
  MPLCONFIGDIR=/tmp/mplconfig /opt/anaconda3/envs/ella-capstone/bin/python scripts/figure_carbon_stocks.py
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
COLOCATION_METRICS_PATH = SPATIAL / "habitat_colocation_metrics.csv"

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

ECO_COLORS = {"seagrass": "#7d3c98", "macroalgae": "#0a6b54"}
REGION_COLORS = {
    "Barents Sea": "#e07a5f",
    "Norwegian Sea": "#3d5a80",
    "Oslofjord": "#81b29a",
    "Skagerrak": "#f2cc8f",
}
REGION_ORDER = ["Barents Sea", "Norwegian Sea", "Oslofjord", "Skagerrak"]

BOOTSTRAP_N = 10_000
RNG = np.random.default_rng(seed=20260508)


def load_seagrass_points() -> pd.DataFrame:
    df = pd.read_csv(MASTER_PATH)
    sg = df[(df["ecosystem"] == "seagrass")
            & (df["inventory_record_type"] == "true_point_site")
            & df["carbon_stock_g_m2"].notna()].copy()
    return sg[["site_name", "canonical_region", "carbon_stock_g_m2",
               "sample_size_n", "depth_m", "year", "source_short"]].reset_index(drop=True)


def load_step2_regional() -> pd.DataFrame:
    return pd.read_csv(STEP2_REGIONAL_PATH)


def load_hb19_extent() -> pd.DataFrame:
    df = pd.read_csv(REGIONAL_SUMMARY_PATH)
    return df[["ecosystem", "canonical_region", "habitat_polygons_n", "habitat_area_km2"]]


# ---------------------------------------------------------------------------
# fig08: seagrass field measurements by region
# ---------------------------------------------------------------------------
def fig08_field_measurements(sg: pd.DataFrame, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 5))
    region_idx = {r: i for i, r in enumerate(REGION_ORDER)}
    for region, sub in sg.groupby("canonical_region"):
        x = region_idx.get(region, len(REGION_ORDER))
        jitter = RNG.uniform(-0.12, 0.12, size=len(sub))
        ax.scatter(x + jitter, sub["carbon_stock_g_m2"],
                   s=80, alpha=0.85, color=REGION_COLORS.get(region, "#444"),
                   edgecolor="black", linewidth=0.6, zorder=3)
        for j, (_, row) in enumerate(sub.iterrows()):
            ax.annotate(row["site_name"], (x + jitter[j], row["carbon_stock_g_m2"]),
                        xytext=(6, 0), textcoords="offset points", fontsize=7,
                        color="#333", zorder=4)

    counts = sg["canonical_region"].value_counts().reindex(REGION_ORDER, fill_value=0)
    for r, n in counts.items():
        i = region_idx[r]
        ax.text(i, -800, f"N={int(n)}", ha="center", fontsize=9, color="#666")

    national_mean = sg["carbon_stock_g_m2"].mean()
    ax.axhline(national_mean, color="#444", linestyle="--", linewidth=1, zorder=1,
               label=f"Pooled mean = {national_mean:,.0f} g C / m^2")

    ax.set_xticks(range(len(REGION_ORDER)))
    ax.set_xticklabels(REGION_ORDER)
    ax.set_ylabel("Sediment carbon stock (g C / m^2)")
    ax.set_xlim(-0.5, len(REGION_ORDER) - 0.5)
    ax.set_ylim(-1500, sg["carbon_stock_g_m2"].max() * 1.1)
    ax.set_title(f"Norwegian seagrass: site-level sediment carbon-stock measurements (N={len(sg)} sites)\n"
                 "Source: Gagnon 2024, Rohr 2018 (compiled in roadmap workbook)")
    ax.legend(loc="upper left", frameon=False, fontsize=9)
    ax.grid(True, axis="y", linestyle=":", alpha=0.4)
    fig.tight_layout()
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# fig09: bootstrap CI on national seagrass stock
# ---------------------------------------------------------------------------
def bootstrap_pooled_mean(values: np.ndarray, n: int = BOOTSTRAP_N) -> np.ndarray:
    idx = RNG.integers(0, len(values), size=(n, len(values)))
    return values[idx].mean(axis=1)


def bootstrap_regional_mean(values: np.ndarray, n: int = BOOTSTRAP_N) -> np.ndarray:
    if len(values) == 0:
        return np.array([np.nan] * n)
    if len(values) == 1:
        return np.full(n, values[0])
    idx = RNG.integers(0, len(values), size=(n, len(values)))
    return values[idx].mean(axis=1)


def fig09_bootstrap(sg: pd.DataFrame, hb19: pd.DataFrame, out: Path) -> None:
    """Bootstrap national seagrass stock using HB19 extent and the 9 point measurements."""
    seagrass_extent_km2 = hb19[hb19["ecosystem"] == "seagrass"]["habitat_area_km2"].sum()

    pooled_means = bootstrap_pooled_mean(sg["carbon_stock_g_m2"].values)
    national_kt_c_pooled = pooled_means * seagrass_extent_km2 * 1_000_000 / 1e9  # g/m^2 * km^2 -> kt C

    # Regional disaggregation: per-region bootstrap of mean × per-region HB19 area.
    # Group Oslofjord measurements with Skagerrak when computing the area-weighted
    # national rollup (HB19's canonical_region groups them under Skagerrak).
    sg_for_areawt = sg.copy()
    sg_for_areawt["region_for_area"] = sg_for_areawt["canonical_region"].replace({"Oslofjord": "Skagerrak"})

    region_extent = (hb19[hb19["ecosystem"] == "seagrass"]
                     .set_index("canonical_region")["habitat_area_km2"].to_dict())

    regional_kt_c = np.zeros(BOOTSTRAP_N)
    region_breakdown: dict[str, np.ndarray] = {}
    for region, sub in sg_for_areawt.groupby("region_for_area"):
        area = region_extent.get(region, 0.0)
        if area == 0:
            continue
        means = bootstrap_regional_mean(sub["carbon_stock_g_m2"].values)
        kt_c = means * area * 1_000_000 / 1e9
        regional_kt_c += kt_c
        region_breakdown[region] = kt_c

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    ax = axes[0]
    ax.hist(national_kt_c_pooled, bins=40, color="#7d3c98", alpha=0.65, edgecolor="white")
    ci_low, ci_high = np.percentile(national_kt_c_pooled, [2.5, 97.5])
    median = np.median(national_kt_c_pooled)
    ymax = ax.get_ylim()[1]
    for v, label, col in [(median, f"median = {median:.0f}", "#222"),
                          (ci_low, f"2.5% = {ci_low:.0f}", "#888"),
                          (ci_high, f"97.5% = {ci_high:.0f}", "#888")]:
        ax.axvline(v, color=col, linestyle="--", linewidth=1)
        ax.text(v, ymax * 0.85, f" {label}", color=col, fontsize=8, rotation=90, va="top")
    ax.axvline(357.6, color="#1b9e77", linewidth=2, linestyle="-",
               label="Step 2 published: 357.6 kt C\n(Frigstad / TemaNord 2020)")
    ax.set_xlabel("National seagrass stock (kt C)")
    ax.set_ylabel("Bootstrap density")
    ax.set_title(f"Pooled bootstrap (N={len(sg)} sites x HB19 extent {seagrass_extent_km2:.0f} km^2)",
                 fontsize=10)
    ax.legend(loc="upper right", frameon=False, fontsize=8)
    ax.grid(True, axis="y", linestyle=":", alpha=0.4)

    ax = axes[1]
    region_keys = list(region_breakdown.keys())
    rolled_data = [region_breakdown[r] for r in region_keys]
    max_y = max(np.percentile(d, 97.5) for d in rolled_data) * 1.25
    parts = ax.violinplot(rolled_data, positions=range(len(region_keys)),
                          showmeans=False, showextrema=False, widths=0.7)
    for pc, region in zip(parts["bodies"], region_keys):
        pc.set_facecolor(REGION_COLORS.get(region, "#888"))
        pc.set_alpha(0.7)
    for i, region in enumerate(region_keys):
        kt = region_breakdown[region]
        ci = np.percentile(kt, [2.5, 97.5])
        med = np.median(kt)
        ax.errorbar(i, med, yerr=[[med - ci[0]], [ci[1] - med]],
                    fmt="o", color="black", markersize=5, capsize=4, zorder=4)
        ax.text(i, med, f"  {med:.0f}", fontsize=9, color="#222", va="center")
        n_sites = (sg_for_areawt["region_for_area"] == region).sum()
        area_km2 = region_extent.get(region, 0)
        ax.text(i, -max_y * 0.06, f"N={n_sites} sites\n{area_km2:.0f} km^2",
                ha="center", fontsize=8, color="#444")
    ax.set_xticks(range(len(region_keys)))
    ax.set_xticklabels(region_keys)
    ax.set_ylim(-max_y * 0.15, max_y)
    ax.set_ylabel("Regional stock (kt C)")
    total_low, total_high = np.percentile(regional_kt_c, [2.5, 97.5])
    total_med = np.median(regional_kt_c)
    ax.set_title(f"Regional disaggregation: sum = {total_med:.0f} kt C [{total_low:.0f} - {total_high:.0f}]",
                 fontsize=10)
    ax.grid(True, axis="y", linestyle=":", alpha=0.4)

    fig.suptitle(
        "Seagrass national carbon stock - bootstrap uncertainty (95% CI)\n"
        f"left: pooled across all {len(sg)} sites; right: per-region area-weighted "
        "(Oslofjord measurements pooled with Skagerrak HB19 area; N=1 regions have no within-region variance)",
        fontsize=11)
    fig.tight_layout()
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)

    return {
        "pooled_median_kt_c": float(median),
        "pooled_ci_low": float(ci_low),
        "pooled_ci_high": float(ci_high),
        "regional_median_kt_c": float(total_med),
        "regional_ci_low": float(total_low),
        "regional_ci_high": float(total_high),
        "hb19_extent_km2": float(seagrass_extent_km2),
    }


# ---------------------------------------------------------------------------
# fig10: extent sensitivity
# ---------------------------------------------------------------------------
def fig10_extent_sensitivity(sg: pd.DataFrame, hb19: pd.DataFrame, out: Path) -> None:
    seagrass_hb19_km2 = hb19[hb19["ecosystem"] == "seagrass"]["habitat_area_km2"].sum()
    macroalgae_hb19_km2 = hb19[hb19["ecosystem"] == "macroalgae"]["habitat_area_km2"].sum()

    pooled_means = bootstrap_pooled_mean(sg["carbon_stock_g_m2"].values)

    def stock_kt_c(mean_g_m2: np.ndarray, extent_km2: float) -> tuple[float, float, float]:
        kt = mean_g_m2 * extent_km2 * 1_000_000 / 1e9
        return float(np.median(kt)), float(np.percentile(kt, 2.5)), float(np.percentile(kt, 97.5))

    seagrass_scenarios = [
        ("HB19 mapped\n(Naturbase important habitat)", seagrass_hb19_km2),
        ("Frigstad 2020 measured", SEAGRASS_EXTENT_KM2_MEASURED),
        ("Frigstad 2020 modelled", SEAGRASS_EXTENT_KM2_MODELED),
    ]
    macroalgae_density_g_m2 = MACROALGAE_NATIONAL_STOCK_KT_C / MACROALGAE_EXTENT_KM2_GUNDERSEN * 1000.0
    macroalgae_scenarios = [
        ("HB19 mapped", macroalgae_hb19_km2 * macroalgae_density_g_m2 * 1_000_000 / 1e9),
        ("Gundersen 2021", MACROALGAE_NATIONAL_STOCK_KT_C),
    ]

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    ax = axes[0]
    sg_results = [(label, stock_kt_c(pooled_means, ext)) for label, ext in seagrass_scenarios]
    labels = [r[0] for r in sg_results]
    medians = [r[1][0] for r in sg_results]
    los = [r[1][1] for r in sg_results]
    his = [r[1][2] for r in sg_results]
    err_low = [m - l for m, l in zip(medians, los)]
    err_high = [h - m for m, h in zip(medians, his)]
    ax.bar(range(len(labels)), medians, yerr=[err_low, err_high],
           capsize=5, color="#7d3c98", alpha=0.85, edgecolor="white")
    for i, (m, lo, hi) in enumerate(zip(medians, los, his)):
        ax.text(i, hi + 30, f"{m:.0f}\n[{lo:.0f}-{hi:.0f}]",
                ha="center", fontsize=8, color="#222")
    ax.axhline(357.6, color="#1b9e77", linestyle=":", linewidth=1.5, label="Step 2 published (357.6 kt C)")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("National stock (kt C)")
    ax.set_title("Seagrass: national stock under three extent assumptions\n(stock g/m^2 from bootstrap of 9 measurements)")
    ax.legend(loc="upper left", frameon=False, fontsize=8)
    ax.grid(True, axis="y", linestyle=":", alpha=0.4)

    ax = axes[1]
    labels = [r[0] for r in macroalgae_scenarios]
    values = [r[1] for r in macroalgae_scenarios]
    ax.bar(range(len(labels)), values, color="#0a6b54", alpha=0.85, edgecolor="white")
    for i, v in enumerate(values):
        ax.text(i, v + 100, f"{v:,.0f} kt C", ha="center", fontsize=9)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("National stock (kt C)")
    ax.set_title(
        "Macroalgae: national stock = Krause-Jensen density x extent\n"
        "(no Norwegian field data; density 485 g C/m^2 fixed)")
    ax.grid(True, axis="y", linestyle=":", alpha=0.4)

    fig.suptitle("Extent sensitivity of national stock estimates", fontsize=11)
    fig.tight_layout()
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# fig11: balance sheet
# ---------------------------------------------------------------------------
def fig11_balance_sheet(sg: pd.DataFrame, hb19: pd.DataFrame, out: Path) -> None:
    seagrass_extent_km2 = hb19[hb19["ecosystem"] == "seagrass"]["habitat_area_km2"].sum()
    macroalgae_extent_km2 = hb19[hb19["ecosystem"] == "macroalgae"]["habitat_area_km2"].sum()

    pooled_means = bootstrap_pooled_mean(sg["carbon_stock_g_m2"].values)
    sg_kt_c = pooled_means * seagrass_extent_km2 * 1_000_000 / 1e9
    sg_med, sg_lo, sg_hi = np.median(sg_kt_c), *np.percentile(sg_kt_c, [2.5, 97.5])

    macroalgae_density_g_m2 = MACROALGAE_NATIONAL_STOCK_KT_C / MACROALGAE_EXTENT_KM2_GUNDERSEN * 1000.0
    ma_kt_c_hb19 = macroalgae_density_g_m2 * macroalgae_extent_km2 * 1_000_000 / 1e9

    # Step 2 national sequestration: seagrass = 0.0168 +/- 0.0046 Mt CO2/yr.
    # Macroalgae median 1.7 Mt CO2/yr; Krause-Jensen export-fraction range
    # 23.2-61.6% maps to Mt C/yr range [0.36, 1.12] (Mt CO2/yr [1.32, 4.11]).
    seq_seagrass_med = 0.0168
    seq_seagrass_sd = 0.0046
    seq_macroalgae_med = 1.7
    seq_macroalgae_lo = 0.36 * 44 / 12  # 1.32 Mt CO2/yr
    seq_macroalgae_hi = 1.12 * 44 / 12  # 4.11 Mt CO2/yr
    valuation = pd.read_csv(STEP2_VALUATION_PATH)

    fig, axes = plt.subplots(2, 2, figsize=(13, 9))

    # (1) National stock totals
    ax = axes[0, 0]
    eco = ["Seagrass", "Macroalgae"]
    medians = [sg_med, ma_kt_c_hb19]
    err_low = [sg_med - sg_lo, 0]
    err_high = [sg_hi - sg_med, 0]
    bars = ax.bar(eco, medians, yerr=[err_low, err_high],
                  capsize=6, color=[ECO_COLORS["seagrass"], ECO_COLORS["macroalgae"]],
                  alpha=0.85, edgecolor="white")
    for b, m, lo, hi in zip(bars, medians, [sg_lo, ma_kt_c_hb19], [sg_hi, ma_kt_c_hb19]):
        if lo == hi:
            label = f"{m:,.0f} kt C\n(no CI)"
        else:
            label = f"{m:,.0f} kt C\n[{lo:,.0f}-{hi:,.0f}]"
        ax.text(b.get_x() + b.get_width() / 2, m + (hi - m) + 50, label,
                ha="center", fontsize=9)
    ax.set_yscale("log")
    ax.set_ylabel("National habitat-stored C (kt C, log scale)")
    ax.set_title("National stock (HB19 extent)\nseagrass: bootstrap CI; macroalgae: Krause-Jensen point estimate")
    ax.grid(True, axis="y", linestyle=":", alpha=0.4, which="both")

    # (2) Annual sequestration
    ax = axes[0, 1]
    seq_med = [seq_seagrass_med, seq_macroalgae_med]
    seq_err_low = [seq_seagrass_sd, seq_macroalgae_med - seq_macroalgae_lo]
    seq_err_high = [seq_seagrass_sd, seq_macroalgae_hi - seq_macroalgae_med]
    ax.bar(eco, seq_med, yerr=[seq_err_low, seq_err_high],
           capsize=6, color=[ECO_COLORS["seagrass"], ECO_COLORS["macroalgae"]],
           alpha=0.85, edgecolor="white")
    seq_labels = [f"{seq_seagrass_med:.3f} Mt CO2/yr",
                  f"{seq_macroalgae_med:.2f} [{seq_macroalgae_lo:.2f}-{seq_macroalgae_hi:.2f}]"]
    for i, (v, label) in enumerate(zip(seq_med, seq_labels)):
        ax.text(i, v + seq_err_high[i] + 0.1, label, ha="center", fontsize=9)
    ax.set_ylabel("Annual sequestration (Mt CO2/yr)")
    ax.set_ylim(0, max(seq_macroalgae_hi * 1.15, 1))
    ax.set_title("Annual sequestration\n(seagrass: Frigstad et al. SD; macroalgae: Krause-Jensen 25.5%, range 23-62% export fraction)")
    ax.grid(True, axis="y", linestyle=":", alpha=0.4)

    # (3) Annual value (3 carbon-price scenarios)
    ax = axes[1, 0]
    val = valuation.copy()
    scen_order = ["EU_ETS_2024_EUR_tCO2", "SCC_US_2023_USD_tCO2", "VCM_blue_carbon_USD_tCO2"]
    scen_labels = ["EU ETS 2024\n(EUR 65/tCO2)", "Social cost of C\n(USD 190/tCO2)", "Voluntary blue C\n(USD 20/tCO2)"]
    pos = np.arange(len(scen_order))
    width = 0.38
    for offset, ecosystem in zip([-width / 2, width / 2], ["seagrass", "macroalgae"]):
        sub = val[val["ecosystem"] == ecosystem].set_index("price_scenario").reindex(scen_order)
        ax.bar(pos + offset, sub["annual_value_million_usd"].values, width=width,
               color=ECO_COLORS[ecosystem], label=ecosystem.capitalize(), alpha=0.85, edgecolor="white")
        for x, v in zip(pos + offset, sub["annual_value_million_usd"].values):
            ax.text(x, v + 5, f"${v:.1f}M", ha="center", fontsize=8)
    ax.set_xticks(pos)
    ax.set_xticklabels(scen_labels, fontsize=8)
    ax.set_ylabel("Annual value (M USD/yr)")
    ax.set_title("Annual sequestration value (3 carbon-price scenarios)")
    ax.legend(frameon=False, fontsize=8)
    ax.grid(True, axis="y", linestyle=":", alpha=0.4)

    # (4) Regional disaggregation: stock per region
    ax = axes[1, 1]
    regional = hb19.copy()
    regional["density_g_m2"] = regional["ecosystem"].map(
        {"seagrass": np.median(pooled_means), "macroalgae": macroalgae_density_g_m2})
    regional["stock_kt_c"] = regional["habitat_area_km2"] * regional["density_g_m2"] * 1_000_000 / 1e9
    pivot = regional.pivot_table(index="canonical_region", columns="ecosystem",
                                 values="stock_kt_c", aggfunc="sum", fill_value=0)
    pivot = pivot.reindex([r for r in REGION_ORDER if r in pivot.index])
    region_order = pivot.sum(axis=1).sort_values(ascending=False).index.tolist()
    pivot = pivot.reindex(region_order)
    bottom = np.zeros(len(pivot))
    for ecosystem in ["seagrass", "macroalgae"]:
        if ecosystem not in pivot.columns:
            continue
        ax.bar(pivot.index, pivot[ecosystem].values, bottom=bottom,
               color=ECO_COLORS[ecosystem], edgecolor="white", linewidth=0.5,
               label=ecosystem.capitalize())
        bottom += pivot[ecosystem].values
    ax.set_yscale("log")
    ax.set_ylabel("Stock (kt C, log scale)")
    ax.set_title("Regional disaggregation\n(seagrass stock area-weighted; macroalgae density uniform - regional variation not validated)")
    ax.legend(frameon=False, fontsize=8)
    ax.grid(True, axis="y", linestyle=":", alpha=0.4, which="both")

    fig.suptitle("Norwegian blue-carbon balance sheet (HB19 extent; CIs where field data permit)", fontsize=13)
    fig.tight_layout()
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# fig12: carbon-at-risk linking stress diagnostics to stock
# ---------------------------------------------------------------------------
def fig12_carbon_at_risk(sg: pd.DataFrame, hb19: pd.DataFrame, out: Path) -> None:
    """Per region x ecosystem: stock x pct_high_pressure_no_strict_protection."""
    metrics = pd.read_csv(COLOCATION_METRICS_PATH)
    metrics["habitat_area_km2"] = metrics["habitat_area_m2"] / 1e6
    risk = (
        metrics.groupby(["canonical_region", "ecosystem"], dropna=False)
        .apply(lambda g: pd.Series({
            "habitat_area_km2": g["habitat_area_km2"].sum(),
            "stressed_area_km2": g.loc[g["high_pressure_no_strict_protection_flag"], "habitat_area_km2"].sum(),
        }), include_groups=False)
        .reset_index()
    )
    risk["pct_stressed"] = risk["stressed_area_km2"] / risk["habitat_area_km2"] * 100

    pooled_means = bootstrap_pooled_mean(sg["carbon_stock_g_m2"].values)
    seagrass_density_med = float(np.median(pooled_means))
    seagrass_density_lo = float(np.percentile(pooled_means, 2.5))
    seagrass_density_hi = float(np.percentile(pooled_means, 97.5))
    macroalgae_density = MACROALGAE_NATIONAL_STOCK_KT_C / MACROALGAE_EXTENT_KM2_GUNDERSEN * 1000.0

    def density(eco: str, scenario: str) -> float:
        if eco == "macroalgae":
            return macroalgae_density
        return {"med": seagrass_density_med, "lo": seagrass_density_lo, "hi": seagrass_density_hi}[scenario]

    rows = []
    for _, r in risk.iterrows():
        eco = r["ecosystem"]
        for scen in ["med", "lo", "hi"]:
            stressed_kt_c = r["stressed_area_km2"] * density(eco, scen) * 1_000_000 / 1e9
            rows.append({
                "canonical_region": r["canonical_region"], "ecosystem": eco,
                "scenario": scen, "stressed_kt_c": stressed_kt_c,
                "pct_stressed": r["pct_stressed"],
            })
    risk_df = pd.DataFrame(rows)

    pivot_med = risk_df[risk_df["scenario"] == "med"].pivot(
        index="canonical_region", columns="ecosystem", values="stressed_kt_c").fillna(0)
    pivot_lo = risk_df[risk_df["scenario"] == "lo"].pivot(
        index="canonical_region", columns="ecosystem", values="stressed_kt_c").fillna(0)
    pivot_hi = risk_df[risk_df["scenario"] == "hi"].pivot(
        index="canonical_region", columns="ecosystem", values="stressed_kt_c").fillna(0)

    region_order = pivot_med.sum(axis=1).sort_values(ascending=False).index.tolist()
    pivot_med = pivot_med.reindex(region_order)
    pivot_lo = pivot_lo.reindex(region_order)
    pivot_hi = pivot_hi.reindex(region_order)

    fig, ax = plt.subplots(figsize=(10, 5))
    width = 0.38
    pos = np.arange(len(region_order))
    for offset, eco in zip([-width / 2, width / 2], ["macroalgae", "seagrass"]):
        med = pivot_med[eco].values if eco in pivot_med.columns else np.zeros(len(region_order))
        lo = pivot_lo[eco].values if eco in pivot_lo.columns else np.zeros(len(region_order))
        hi = pivot_hi[eco].values if eco in pivot_hi.columns else np.zeros(len(region_order))
        err = [med - lo, hi - med] if eco == "seagrass" else None
        ax.bar(pos + offset, med, width=width,
               color=ECO_COLORS[eco], alpha=0.85, edgecolor="white",
               label=eco.capitalize(), yerr=err, capsize=4)
        for x, v in zip(pos + offset, med):
            if v > 0:
                ax.text(x, v + max(med) * 0.02, f"{v:.1f}", ha="center", fontsize=8)
    ax.set_xticks(pos)
    ax.set_xticklabels(region_order)
    ax.set_ylabel("Stressed habitat-stored C (kt C)")
    ax.set_title(
        "Habitat-stored carbon in pressure x no-strict-protection class, by region\n"
        "Seagrass error bars = bootstrap CI on stock density; macroalgae uses national mean only")
    ax.legend(frameon=False, fontsize=9)
    ax.grid(True, axis="y", linestyle=":", alpha=0.4)
    fig.tight_layout()
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)

    risk_df.to_csv(OUT_DIR / "carbon_at_risk.csv", index=False)


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

    fig08_field_measurements(sg, OUT_DIR / "fig08_seagrass_field_measurements.png")
    bootstrap_summary = fig09_bootstrap(sg, hb19, OUT_DIR / "fig09_seagrass_bootstrap.png")
    fig10_extent_sensitivity(sg, hb19, OUT_DIR / "fig10_extent_sensitivity.png")
    fig11_balance_sheet(sg, hb19, OUT_DIR / "fig11_carbon_balance_sheet.png")
    fig12_carbon_at_risk(sg, hb19, OUT_DIR / "fig12_carbon_at_risk.png")
    stats_csv(sg, hb19, bootstrap_summary, OUT_DIR / "carbon_stock_estimates.csv")

    print("\nBootstrap summary:")
    for k, v in bootstrap_summary.items():
        print(f"  {k}: {v:.2f}")
    print(f"\nWrote 5 figures + 2 CSVs to {OUT_DIR.relative_to(REPO_ROOT)}/")


if __name__ == "__main__":
    main()
