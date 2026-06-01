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

Writes to figures/:
  seagrass_bootstrap.png
  carbon_balance_sheet.png
  carbon_stock_estimates.csv

Run:
  MPLCONFIGDIR=/tmp/mplconfig python scripts/figure_carbon_stocks.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from figure_style import add_caption, use_min_font


REPO_ROOT = Path(__file__).resolve().parent.parent
PROC = REPO_ROOT / "data" / "processed"
SPATIAL = PROC / "spatial_analysis"
OUT_DIR = REPO_ROOT / "figures"

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

# Published seagrass sediment-stock benchmarks (Gg C, top 50/25 cm at source).
# Used as independent reference points against the bootstrap, NOT as the headline.
SEAGRASS_STOCK_FRIGSTAD_GG_C = 245.0        # Frigstad 2020 Table 8: 90 km² x ~2,722 g C m-2 Nordic-weighted, top 25 cm
SEAGRASS_STOCK_GAGNON_GG_C = 250.0          # Gagnon 2024 Nordic-weighted national: 0.25 Mt C
SEAGRASS_STOCK_GAGNON_RANGE_GG_C = (60.0, 400.0)  # Gagnon 2024 published range

# Macroalgae national LIVING-BIOMASS stock (Gg C). Primary source:
# Frigstad 2020 (kelp 4,969 + rockweed 927 = 5,896 Gg C). This is biomass C,
# not sediment carbon stock — the two cannot be combined.
MACROALGAE_LIVING_BIOMASS_FRIGSTAD_GG_C = 5896.0
MACROALGAE_LIVING_BIOMASS_KELP_GG_C = 4969.0
MACROALGAE_LIVING_BIOMASS_ROCKWEED_GG_C = 927.0
# Alternative reference: Gundersen 2021 extent × Krause-Jensen & Duarte 2016
# transfer function = 2,600 Gg C (different area + density assumptions; shown
# for context only).
MACROALGAE_LIVING_BIOMASS_GUNDERSEN_GG_C = 2600.0
MACROALGAE_SEQ_MT_CO2_YR = 1.7
MACROALGAE_SEQ_MT_CO2_YR_RANGE = (0.36 * 44 / 12 * 1.0,
                                  4.1 * 44 / 12 * 1.0 / 10)  # placeholder; see step2

# Macroalgae sequestration transfer-function range: Krause-Jensen & Duarte 2016
# export/sequestration fraction (central 25.5%, range 23.2-61.6%). This single
# parameter is the dominant macroalgae uncertainty; the Mt CO2/yr figures it
# produces are in step2_national_sequestration.csv (seq_mt_co2_yr + CI).
MACROALGAE_SEQ_FRACTION_PCT = (23.2, 25.5, 61.6)

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


def load_national_seq() -> pd.DataFrame:
    return pd.read_csv(STEP2_NATIONAL_PATH)


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

    # Seagrass: bootstrap the site densities, scale by Frigstad 2020 national
    # modeled extent (90 km²) -> national stock. Frigstad's headline 245 Gg C
    # uses the same 90 km² basis, so this keeps the bootstrap on the same
    # extent footing as the published national estimate. HB19 (~65 km²) is
    # the mapped/surveyed area, which would undercount national stock.
    seagrass_extent_km2 = SEAGRASS_EXTENT_KM2_MODELED
    site_vals = sg["carbon_stock_g_m2"].values
    pooled_means = bootstrap_pooled_mean(site_vals)
    national_kt_c = pooled_means * seagrass_extent_km2 * 1_000_000 / 1e9
    median = float(np.median(national_kt_c))
    ci_low, ci_high = (float(v) for v in np.percentile(national_kt_c, [2.5, 97.5]))

    # Macroalgae: no Norwegian field stock data. Its dominant uncertainty is the
    # literature transfer function, documented for the export/sequestration
    # fraction, so it is shown on annual sequestration (Mt CO2/yr) from step2.
    nat = load_national_seq().set_index("ecosystem")
    sg_seq = float(nat.loc["seagrass", "seq_mt_co2_yr"])
    sg_seq_sd = float(nat.loc["seagrass", "seq_mt_co2_yr_sd"])
    sg_seq_err = 1.96 * sg_seq_sd
    ma_seq = float(nat.loc["macroalgae", "seq_mt_co2_yr"])
    ma_seq_lo = float(nat.loc["macroalgae", "seq_mt_co2_yr_ci_low"])
    ma_seq_hi = float(nat.loc["macroalgae", "seq_mt_co2_yr_ci_high"])
    frac_lo, frac_mid, frac_hi = MACROALGAE_SEQ_FRACTION_PCT

    def _clean(ax):
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    fig, axes = plt.subplots(2, 2, figsize=(13, 9.5))
    xs = np.arange(2)

    # (A) Seagrass bootstrap distribution. Headline only — independent
    # benchmarks (Frigstad / Gagnon Nordic-weighted) discussed in the report
    # text rather than overlaid here.
    ax = axes[0, 0]
    ax.hist(national_kt_c, bins=40, color=sg_color, alpha=0.85,
            edgecolor="white", linewidth=0.4)
    ax.axvspan(ci_low, ci_high, color=sg_color, alpha=0.18, zorder=0)
    ax.axvline(median, color=dark, linewidth=2.0)
    for v in (ci_low, ci_high):
        ax.axvline(v, color=dark, linestyle="--", linewidth=1.2)
    ax.set_xlim(right=float(national_kt_c.max()) * 1.04)
    ax.text(0.03, 0.97,
            f"{median:,.0f} Gg C\n95% CI  {ci_low:,.0f}–{ci_high:,.0f}\n"
            f"(± {(ci_high - ci_low) / 2 / median * 100:.0f}%)",
            transform=ax.transAxes, va="top", ha="left", fontsize=11,
            fontweight="bold", color=dark,
            bbox=dict(facecolor="white", edgecolor=dark, boxstyle="round,pad=0.5", linewidth=1.0))
    ax.set_xlabel("National seagrass sediment stock (Gg C)", fontsize=9.5)
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
    ax.text(0.45, mean_v, f"mean {mean_v:,.0f}", fontsize=9, color=dark,
            va="bottom", ha="right")
    ax.text(0.97, 0.97,
            f"n = {len(site_vals)} sites\n"
            f"range {site_vals.min():,.0f}–{site_vals.max():,.0f}\n"
            f"CV = {site_vals.std(ddof=1) / mean_v * 100:.0f}%",
            transform=ax.transAxes, va="top", ha="right", fontsize=9, color="#333",
            bbox=dict(facecolor="white", edgecolor="#ddd", boxstyle="round,pad=0.4", linewidth=0.6))
    ax.set_xlim(-0.5, 0.5)
    ax.set_xticks([])
    ax.set_ylim(0, site_vals.max() * 1.12)
    ax.set_ylabel("Site carbon density (g C m⁻²)", fontsize=9.5)
    ax.set_title("B.  Data Spread — Source of the Uncertainty", loc="left",
                 fontweight="bold", fontsize=12)
    _clean(ax)

    # (C) Macroalgae sequestration — what the transfer function does to the answer.
    #     Annual CO2 sequestration is the standing stock × the fraction that is
    #     exported and buried. That export/sequestration fraction (Krause-Jensen &
    #     Duarte 2016) is the dominant unknown: as it ranges 23-62% the answer
    #     ranges 1.3-4.1 Mt CO2/yr. Shown as three points along that spread.
    ax = axes[1, 0]
    seq_pts = [ma_seq_lo, ma_seq, ma_seq_hi]
    frac_pts = [frac_lo, frac_mid, frac_hi]
    names = ["low", "central", "high"]
    pt_colors = [ma_color, dark, ma_color]
    ax.plot([ma_seq_lo, ma_seq_hi], [0, 0], color=ma_color, linewidth=4.0,
            alpha=0.35, solid_capstyle="round", zorder=1)
    for s, frac, name, c in zip(seq_pts, frac_pts, names, pt_colors):
        is_mid = name == "central"
        ax.scatter(s, 0, s=320 if is_mid else 150, color=c, edgecolor="black",
                   linewidth=1.0, zorder=3)
        dy, va = (0.45, "bottom") if is_mid else (-0.45, "top")
        ax.text(s, dy,
                f"{name}\n{frac:.1f}% exported\n→ {s:.1f} Mt CO₂ yr⁻¹",
                ha="center", va=va, fontsize=9,
                fontweight="bold" if is_mid else "normal",
                color=dark if is_mid else "#444")
    ax.set_ylim(-1.3, 1.3)
    ax.set_yticks([])
    ax.set_xlim(0, ma_seq_hi * 1.22)
    ax.set_xlabel("Annual CO₂ sequestration (Mt CO₂ yr⁻¹)", fontsize=9.5)
    ax.set_title("C.  Macroalgae — Transfer-Function Spread", loc="left",
                 fontweight="bold", fontsize=12)
    # In-panel commentary removed — keeping the panel visually clean; the
    # transfer-function range and living-biomass attribution are summarized
    # in the figure footnote and discussed in the report text.
    ax.spines["left"].set_visible(False)
    _clean(ax)

    # (D) Both habitats' annual sequestration, log scale, with their
    #     different uncertainty types: sampling CI vs transfer-function range.
    ax = axes[1, 1]
    meds = [sg_seq, ma_seq]
    lo_err = [sg_seq_err, ma_seq - ma_seq_lo]
    hi_err = [sg_seq_err, ma_seq_hi - ma_seq]
    ax.bar(xs, meds, width=0.5, color=[sg_color, ma_color], edgecolor="black",
           linewidth=0.6, yerr=[lo_err, hi_err], capsize=8,
           error_kw=dict(elinewidth=1.5, capthick=1.5, ecolor="#333"))
    ax.set_yscale("log")
    ax.set_ylim(0.005, 30)
    # Value + CI labels sit above each error-bar cap, on white, so they never
    # overlap the bars or the (dark grey) error bars.
    val_lbls = [f"{sg_seq:.3f}\n[{sg_seq - sg_seq_err:.3f}–{sg_seq + sg_seq_err:.3f}]",
                f"{ma_seq:.1f}\n[{ma_seq_lo:.1f}–{ma_seq_hi:.1f}]"]
    cap_tops = [sg_seq + sg_seq_err, ma_seq_hi]
    for x, top, vl in zip(xs, cap_tops, val_lbls):
        ax.text(x, top * 1.6, vl, ha="center", va="bottom",
                fontsize=9, fontweight="bold", color="#222")
    ax.set_xticks(xs)
    ax.set_xticklabels(["Seagrass\n(seq-rate SD)",
                        "Macroalgae\n(transfer-function range)"], fontsize=9)
    ax.set_ylabel("Annual sequestration (Mt CO₂ yr⁻¹, log scale)", fontsize=9.5)
    ax.set_title("D.  Both Habitats — Sequestration with Uncertainty", loc="left",
                 fontweight="bold", fontsize=12)
    _clean(ax)

    add_caption(
        fig,
        f"(A) Non-parametric bootstrap ({BOOTSTRAP_N:,} resamples) of {len(site_vals)} site sediment-stock "
        f"measurements (Gagnon 2024; Rohr 2018) × Frigstad 2020 national modeled extent "
        f"({seagrass_extent_km2:.0f} km²). "
        "(B) Site data spread driving the bootstrap CI. "
        f"(C) Macroalgae sequestration governed by Krause-Jensen & Duarte 2016 export fraction "
        f"({frac_lo:.0f}–{frac_hi:.0f}%, central {frac_mid:.1f}%); the living-biomass C pool itself is "
        f"source-dependent (Frigstad 2020: {MACROALGAE_LIVING_BIOMASS_FRIGSTAD_GG_C:,.0f} Gg C; "
        f"Gundersen × KJD: {MACROALGAE_LIVING_BIOMASS_GUNDERSEN_GG_C:,.0f} Gg C). "
        "(D) Annual sequestration with the two uncertainty types side-by-side: seagrass ±1.96 SD of the "
        "TemaNord 2020:541 rate; macroalgae the transfer-function range from C.",
        y=0.04, fontsize=10)
    fig.subplots_adjust(left=0.08, right=0.97, top=0.95, bottom=0.20, hspace=0.42, wspace=0.22)
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
def fig11_balance_sheet(sg: pd.DataFrame, hb19: pd.DataFrame,
                        bootstrap_summary: dict, out: Path) -> None:
    sg_color, ma_color = ECO_COLORS["seagrass"], ECO_COLORS["macroalgae"]
    pub_color, dark = "#b3541e", "#1b5e20"

    # National carbon-pool headlines (Gg C). This figure precedes the bootstrap
    # in the report, so published source values are used as the primary numbers:
    #   seagrass   - SEDIMENT stock from Frigstad 2020 Table 8 (245 Gg C;
    #                90 km² × Nordic-weighted density, top 25 cm).
    #   macroalgae - LIVING BIOMASS C from Frigstad 2020 (5,896 Gg C = kelp
    #                4,969 + rockweed 927). Gundersen × KJD areal alternative
    #                (2,600 Gg C, different area + density assumptions) shown
    #                as a reference line.
    sg_stock_gg = SEAGRASS_STOCK_FRIGSTAD_GG_C
    ma_stock_gg = MACROALGAE_LIVING_BIOMASS_FRIGSTAD_GG_C
    ma_alt_gg = MACROALGAE_LIVING_BIOMASS_GUNDERSEN_GG_C
    nat = load_national_seq().set_index("ecosystem")

    # Regional seagrass stock = regional mean sediment density (Gagnon 2024;
    # Rohr 2018, by region) x HB19 mapped seagrass area for that region.
    region_density = sg.groupby("canonical_region")["carbon_stock_g_m2"].mean()
    region_area = (hb19[hb19["ecosystem"] == "seagrass"]
                   .groupby("canonical_region")["habitat_area_km2"].sum())

    # Annual sequestration (Mt CO2/yr): seagrass Frigstad 2020; macroalgae Krause-Jensen
    # export-fraction range 23-62% -> 1.3-4.1 Mt CO2/yr around a 1.7 central value.
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

    # (A) National carbon pool — sediment (seagrass) vs living biomass (macroalgae).
    # NOTE: the two bars are NOT directly comparable: seagrass is a sediment
    # carbon stock (long-term storage); macroalgae is standing-biomass C
    # (annual turnover pool). The panel title and labels say so explicitly.
    ax = axes[0, 0]
    stocks = [sg_stock_gg, ma_stock_gg]
    bars = ax.bar(eco, stocks, color=eco_cols, edgecolor="black", linewidth=0.6)
    ax.set_yscale("log")
    ax.set_ylim(top=ma_stock_gg * 8)
    labels = [
        (f"{sg_stock_gg:,.0f} Gg C  (Frigstad 2020)\n"
         f"Sediment stock"),
        (f"{ma_stock_gg:,.0f} Gg C  (Frigstad 2020)\n"
         f"kelp {MACROALGAE_LIVING_BIOMASS_KELP_GG_C:,.0f} + rockweed "
         f"{MACROALGAE_LIVING_BIOMASS_ROCKWEED_GG_C:,.0f}\n"
         f"Living biomass"),
    ]
    for b, lbl in zip(bars, labels):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() * 1.35,
                lbl, ha="center", va="bottom", fontsize=8.5)
    # Single alternative-reference line: Gundersen × KJD areal estimate for
    # macroalgae (the only one not already encoded by the primary Frigstad
    # bars). Placed only over bar 1; label sits to the LEFT of the bar so it
    # doesn't bleed into panel B.
    bar1_x = bars[1].get_x()
    bar1_w = bars[1].get_width()
    ax.hlines(ma_alt_gg, bar1_x - 0.04, bar1_x + bar1_w + 0.04,
              color=pub_color, linewidth=1.6, linestyle="--")
    ax.text(bar1_x - 0.06, ma_alt_gg,
            f"Gundersen × KJD\n({ma_alt_gg:,.0f} Gg C; alt.)",
            va="center", ha="right", fontsize=8, color=pub_color)
    ax.set_ylabel("Carbon pool (Gg C, log scale)", fontsize=9.5)
    ax.set_title("A.  National Carbon Pool  (sediment vs. living biomass)",
                 loc="left", fontweight="bold", fontsize=12)
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
        ax.text(i, (v + e) * 1.35, lbl, ha="center", va="bottom", fontsize=9)
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
                    ha="center", va="bottom", fontsize=9)
    ax.set_yscale("log")
    ax.set_ylim(0.15, max(all_vals) * 4)
    ax.set_xticks(pos)
    ax.set_xticklabels(scen_labels, fontsize=9)
    ax.set_ylabel("Annual value\n(M USD yr⁻¹, log scale)", fontsize=9.5)
    ax.set_title("C.  Annual Sequestration Value", loc="left", fontweight="bold", fontsize=12)
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    _clean(ax)

    # (D) Regional seagrass stock = regional source density x HB19 mapped area
    ax = axes[1, 1]
    regions = [r for r in REGION_ORDER if r in region_density.index]
    reg_vals = [region_density[r] * region_area.get(r, 0.0) * 1_000_000 / 1e9
                for r in regions]
    xr = np.arange(len(regions))
    ax.bar(xr, reg_vals, width=0.6,
           color=[REGION_COLORS.get(r, "#888") for r in regions],
           edgecolor="black", linewidth=0.6)
    for i, v in zip(xr, reg_vals):
        ax.text(i, v + max(reg_vals) * 0.02, f"{v:,.1f}" if v < 10 else f"{v:,.0f}",
                ha="center", va="bottom", fontsize=9)
    ax.set_xticks(xr)
    ax.set_xticklabels([region_display(r) for r in regions], fontsize=9)
    ax.set_ylim(0, max(reg_vals) * 1.2)
    ax.set_ylabel("Seagrass stock (Gg C)", fontsize=9.5)
    ax.set_title("D.  Regional Seagrass Stock", loc="left", fontweight="bold", fontsize=12)
    _clean(ax)

    add_caption(
        fig,
        "(A) Bars are different carbon types and not directly comparable: seagrass = sediment stock "
        f"(Frigstad 2020 Table 8); macroalgae = living biomass C (Frigstad 2020). Gundersen × KJD areal "
        f"alternative ({ma_alt_gg:,.0f} Gg C) shown for context. "
        "(B) Sequestration: TemaNord 2020:541 (seagrass); Krause-Jensen export-fraction 23–62% (macroalgae). "
        "(C) Annual sequestration × carbon price: EU ETS 2024 (€65), Social Cost of Carbon 2023 ($190), "
        "Voluntary blue-carbon ($20) per tCO₂. "
        "(D) Regional mean sediment density (Gagnon 2024; Rohr 2018) × HB19 mapped area; need not sum to the "
        "national total. Barents and Norwegian Sea each rest on a single site.",
        y=0.04, fontsize=10)
    fig.subplots_adjust(left=0.07, right=0.97, top=0.95, bottom=0.20, hspace=0.45, wspace=0.24)
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Stats CSV: regional + national stock estimates with CIs
# ---------------------------------------------------------------------------
def stats_csv(sg: pd.DataFrame, hb19: pd.DataFrame, bootstrap_summary: dict, out: Path) -> None:
    pooled_means = bootstrap_pooled_mean(sg["carbon_stock_g_m2"].values)
    # Regional macroalgae disaggregation is areal (no field stock data exists),
    # so it uses the Gundersen 2021 × KJD areal alternative — NOT the Frigstad
    # national living-biomass total, which has no per-region split. Labeled in
    # the CSV's uncertainty_source column.
    macroalgae_density = (MACROALGAE_LIVING_BIOMASS_GUNDERSEN_GG_C * 1000.0
                          / MACROALGAE_EXTENT_KM2_GUNDERSEN)

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
    use_min_font()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sg = load_seagrass_points()
    hb19 = load_hb19_extent()
    print(f"Loaded {len(sg)} seagrass site-level measurements")
    print(f"HB19 seagrass extent: {hb19[hb19['ecosystem']=='seagrass']['habitat_area_km2'].sum():.1f} km^2")
    print(f"HB19 macroalgae extent: {hb19[hb19['ecosystem']=='macroalgae']['habitat_area_km2'].sum():.1f} km^2")

    bootstrap_summary = fig09_bootstrap(sg, hb19, OUT_DIR / "seagrass_bootstrap.png")
    fig11_balance_sheet(sg, hb19, bootstrap_summary,
                        OUT_DIR / "carbon_balance_sheet.png")
    stats_csv(sg, hb19, bootstrap_summary, OUT_DIR / "carbon_stock_estimates.csv")

    print("\nBootstrap summary:")
    for k, v in bootstrap_summary.items():
        print(f"  {k}: {v:.2f}")
    print(f"\nWrote 2 figures + 1 CSV to {OUT_DIR.relative_to(REPO_ROOT)}/")


if __name__ == "__main__":
    main()
