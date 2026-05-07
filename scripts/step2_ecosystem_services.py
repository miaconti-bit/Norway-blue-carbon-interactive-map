"""
Step 2 – Ecosystem Service Assessment
Produces tables for 2.1 (sequestration) and 2.2 (co-benefits) for both
seagrass and macroalgae.

Run: source .venv/bin/activate && python scripts/step2_ecosystem_services.py
Outputs written to: data/processed/step2_*.csv
"""

import pathlib
import sys
import warnings

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).parent.parent
DATA = ROOT / "data"
PROCESSED = DATA / "processed"
EXTERNAL = DATA / "external"
OUT = PROCESSED  # same dir, prefixed "step2_"

# ── Carbon price assumptions (2024 reference values) ─────────────────────────
# Choose one for headline valuation; report all three in the output table.
CARBON_PRICES = {
    "EU_ETS_2024_EUR_tCO2":    65.0,   # approximate 2024 EU ETS spot
    "SCC_US_2023_USD_tCO2":   190.0,   # US EPA social cost of carbon
    "VCM_blue_carbon_USD_tCO2": 20.0,  # voluntary carbon market (blue carbon)
}
EUR_TO_USD = 1.08  # approximate conversion

# National extent for seagrass (from Frigstad et al. 2020 / TemaNord 2020:541)
SEAGRASS_EXTENT_KM2_MODELED = 90.0    # 90 km² modeled national extent
SEAGRASS_EXTENT_KM2_MEASURED = 60.0  # 60 km² directly measured

# Seagrass sequestration rate (from TemaNord 2020:541 / Frigstad et al. 2020)
# Units: g C m⁻² yr⁻¹
SEAGRASS_SEQ_RATE_MEAN = 51.0
SEAGRASS_SEQ_RATE_SD = 14.0


def load_observations() -> pd.DataFrame:
    path = PROCESSED / "norway_blue_carbon_observations.csv"
    return pd.read_csv(path)


def load_sites() -> pd.DataFrame:
    path = PROCESSED / "norway_blue_carbon_master_sites.csv"
    return pd.read_csv(path)


def load_gundersen_national() -> pd.DataFrame:
    path = EXTERNAL / "gundersen2021" / "table4_national_carbon_estimates.csv"
    if not path.exists():
        raise FileNotFoundError(f"Gundersen 2021 table not found at {path}")
    return pd.read_csv(path)


def load_nature_index() -> pd.DataFrame | None:
    """Returns coastal indicator averages or None if data not yet downloaded."""
    path = EXTERNAL / "nature_index" / "NI2025_IndicatorData" / "Indikator_Average.csv"
    if not path.exists():
        warnings.warn(
            "Nature Index data not found. Download manually from "
            "https://www.naturindeks.no/DownloadData and unzip into "
            "data/external/nature_index/NI2025_IndicatorData/. "
            "Returning None — 2.2 biodiversity section will be skipped.",
            stacklevel=2,
        )
        return None
    df = pd.read_csv(path)

    # Indicator IDs belonging to the Kystvann (coastal) ecosystem.
    # Ecosystem membership is stored in the NI database (not in the CSV);
    # this set was determined from indicator names and NI documentation.
    # Subset annotated for blue-carbon relevance:
    #   74  Hardbunn vegetasjon algeindeks      ← macroalgae/kelp condition
    #   75  Hardbunn vegetasjon nedre voksegrense ← kelp lower growth limit (climate risk)
    #   21  Bløtbunn artsmangfold fauna kyst    ← soft-bottom diversity (seagrass habitat)
    #   22  Bløtbunn eutrofiindeks              ← eutrophication pressure
    #   145 Planteplankton (Chl a)              ← light/eutrophication proxy
    COASTAL_IDS = {
        1, 12, 18, 21, 22, 36, 72, 74, 75, 84, 101, 104, 105, 115, 135,
        141, 145, 165, 222, 234, 235, 236, 239, 241, 242, 245, 246, 247,
        248, 249, 250, 251, 253, 257, 287, 293, 296, 298, 440,
    }
    return df[df["id"].isin(COASTAL_IDS)].copy()


# ═══════════════════════════════════════════════════════════════════════════
# 2.1 SEQUESTRATION
# ═══════════════════════════════════════════════════════════════════════════

def compute_seagrass_sequestration(obs: pd.DataFrame) -> dict:
    """
    Returns dict with regional and national seagrass carbon estimates.

    Method:
    - Regional mean sediment C stock from Gagnon 2024 site-level data
    - National estimate = mean stock × national modeled extent (90 km²)
    - Sequestration = literature rate (51 g C m⁻² yr⁻¹) × 90 km²
    - Uncertainty propagated from SD of site-level stocks and rate SD
    """
    sg = obs[(obs["ecosystem"] == "seagrass") &
             obs["sediment_c_stock_g_m2"].notna()].copy()

    # Regional breakdown
    regional = (sg.groupby("canonical_region")["sediment_c_stock_g_m2"]
                  .agg(n="count", mean="mean", sd="std", min="min", max="max")
                  .reset_index())
    regional.columns = ["canonical_region", "n_sites", "mean_stock_g_m2",
                        "sd_stock_g_m2", "min_stock_g_m2", "max_stock_g_m2"]

    # National aggregation from site means
    national_mean = sg["sediment_c_stock_g_m2"].mean()
    national_sd = sg["sediment_c_stock_g_m2"].std()
    n_sites = len(sg)

    # Stock in Gg C: mean g/m² × 90 km² × (1e6 m²/km²) ÷ (1e9 g/Gg)
    extent_m2 = SEAGRASS_EXTENT_KM2_MODELED * 1e6
    stock_gg = national_mean * extent_m2 / 1e9
    stock_gg_sd = national_sd * extent_m2 / 1e9

    # Sequestration in Gg C yr⁻¹
    seq_gg = SEAGRASS_SEQ_RATE_MEAN * extent_m2 / 1e9
    seq_gg_sd = SEAGRASS_SEQ_RATE_SD * extent_m2 / 1e9

    # Mt CO₂ yr⁻¹: Gg C × (44/12) ÷ 1000 Gg/Mt
    seq_mt_co2 = seq_gg * (44 / 12) / 1e3
    seq_mt_co2_sd = seq_gg_sd * (44 / 12) / 1e3

    national = {
        "ecosystem": "seagrass",
        "n_sites": n_sites,
        "extent_km2_modeled": SEAGRASS_EXTENT_KM2_MODELED,
        "extent_km2_measured": SEAGRASS_EXTENT_KM2_MEASURED,
        "mean_stock_g_m2": round(national_mean, 1),
        "sd_stock_g_m2": round(national_sd, 1),
        "stock_gg_c": round(stock_gg, 2),
        "stock_gg_c_sd": round(stock_gg_sd, 2),
        "seq_rate_g_m2_yr": SEAGRASS_SEQ_RATE_MEAN,
        "seq_rate_sd_g_m2_yr": SEAGRASS_SEQ_RATE_SD,
        "seq_gg_c_yr": round(seq_gg, 3),
        "seq_gg_c_yr_sd": round(seq_gg_sd, 3),
        "seq_mt_co2_yr": round(seq_mt_co2, 4),
        "seq_mt_co2_yr_sd": round(seq_mt_co2_sd, 4),
        "ipcc_tier": "Tier 2",
        "tier_notes": (
            "Extent from Frigstad 2020 (national model); "
            "sequestration rate from TemaNord 2020:541 (regional literature); "
            "no Norwegian sediment dating — Tier 3 not achieved"
        ),
    }

    return {"regional": regional, "national": national}


def compute_macroalgae_sequestration(gundersen: pd.DataFrame) -> dict:
    """
    Returns national macroalgae carbon estimates from Gundersen 2021.

    The Gundersen data covers Saccharina latissima + Laminaria hyperborea.
    No site-level carbon stock data exists in the processed observations —
    all macroalgae observations are from Ribeiro 2022 (genetics paper).
    """
    def _get(metric):
        row = gundersen[gundersen["metric"] == metric].iloc[0]
        return row["value"], row["ci_low"], row["ci_high"], row["unit"]

    area_val, area_lo, area_hi, area_unit = _get("kelp_forest_area")
    stock_val, stock_lo, stock_hi, stock_unit = _get("carbon_standing_stock")
    seq_val, seq_lo, seq_hi, seq_unit = _get("annual_sequestration_c")
    seq_co2_val, seq_co2_lo, seq_co2_hi, _ = _get("annual_sequestration_co2")
    export_val, export_lo, export_hi, _ = _get("annual_carbon_export")

    # Convert to Gg C for consistency with seagrass
    # Gundersen reports in million tonnes C; 1 Mt C = 1000 Gg C
    national = {
        "ecosystem": "macroalgae",
        "species": "Saccharina latissima + Laminaria hyperborea",
        "n_transects": 630,
        "extent_km2": area_val,
        "extent_km2_ci_low": area_lo,
        "extent_km2_ci_high": area_hi,
        "stock_mt_c": stock_val,
        "stock_mt_c_ci_low": stock_lo,
        "stock_mt_c_ci_high": stock_hi,
        "stock_gg_c": stock_val * 1000,
        "annual_export_mt_c_yr": export_val,
        "seq_mt_c_yr": seq_val,
        "seq_mt_c_yr_ci_low": seq_lo,
        "seq_mt_c_yr_ci_high": seq_hi,
        "seq_mt_co2_yr": seq_co2_val,
        "seq_mt_co2_yr_ci_low": seq_co2_lo,
        "seq_mt_co2_yr_ci_high": seq_co2_hi,
        "seq_gg_c_yr": seq_val * 1000,
        "ipcc_tier": "Tier 2",
        "tier_notes": (
            "Area from Gundersen 2021 national model (630 scuba transects); "
            "sequestration fraction from Krause-Jensen & Duarte 2016 "
            "(25.5%, range 23.2–61.6%); wide CI driven by this transfer function. "
            "No Norwegian sediment dating — Tier 3 not achieved."
        ),
        "source": "Gundersen et al. 2021, doi:10.3389/fmars.2021.578629",
    }

    return national


def compute_carbon_valuation(seq_seagrass_gg: float,
                              seq_macroalgae_gg: float) -> pd.DataFrame:
    """
    Returns a valuation table (USD) for three carbon price scenarios.

    Inputs are in Gg C yr⁻¹; converted to Mt CO₂ yr⁻¹ for pricing.
    """
    def gg_c_to_mt_co2(gg_c):
        return gg_c * (44 / 12) / 1e3

    rows = []
    for ecosystem, seq_gg in [("seagrass", seq_seagrass_gg),
                               ("macroalgae", seq_macroalgae_gg)]:
        mt_co2 = gg_c_to_mt_co2(seq_gg)
        for price_name, price_val in CARBON_PRICES.items():
            currency = "USD" if "USD" in price_name else "EUR"
            val = mt_co2 * 1e6 * price_val  # Mt CO₂ → tonnes CO₂ × price
            val_usd = val * (EUR_TO_USD if currency == "EUR" else 1.0)
            rows.append({
                "ecosystem": ecosystem,
                "seq_mt_co2_yr": round(mt_co2, 4),
                "price_scenario": price_name,
                "price_per_tco2": price_val,
                "currency": currency,
                "annual_value_million_usd": round(val_usd / 1e6, 2),
            })

    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════════════════
# 2.2 CO-BENEFITS
# ═══════════════════════════════════════════════════════════════════════════

def build_cobenefits_summary(ni_df: pd.DataFrame | None) -> pd.DataFrame:
    """
    Assembles co-benefit evidence table.

    Uses Nature Index data if available; falls back to cited literature values.
    Coastal protection and fisheries are literature-only (no Norwegian spatial data).
    """
    rows = [
        # Biodiversity
        {
            "co_benefit": "Biodiversity",
            "metric": "Norwegian Nature Index — coastal waters (NI score)",
            "value": 0.766,
            "uncertainty": "SD = 0.011",
            "unit": "index (0–1)",
            "geographic_scope": "National",
            "year": 2024,
            "data_source": "NINA / Naturindeks 2025",
            "data_quality": "high — national monitoring programme",
            "norway_specific": True,
            "notes": "Score of 1 = reference (undisturbed) state; 0.766 indicates moderate condition",
        },
        {
            "co_benefit": "Biodiversity",
            "metric": "Infaunal species richness — eelgrass vs unvegetated",
            "value": None,
            "uncertainty": None,
            "unit": "qualitative",
            "geographic_scope": "Skagerrak / W Norway sites",
            "year": None,
            "data_source": "Boström et al. 2014 (cited in roadmap)",
            "data_quality": "medium — site-level comparison",
            "norway_specific": True,
            "notes": "Eelgrass supports higher infaunal diversity than unvegetated sediments at Norwegian sites",
        },
        # Fisheries
        {
            "co_benefit": "Fisheries / nursery habitat",
            "metric": "Eelgrass nursery function for juvenile cod, flatfish",
            "value": None,
            "uncertainty": None,
            "unit": "qualitative",
            "geographic_scope": "Norway / Nordic",
            "year": None,
            "data_source": "Literature (global/Nordic)",
            "data_quality": "low — no Norway-specific quantification",
            "norway_specific": False,
            "notes": "No Norwegian study quantifies fish biomass or yield attributable to eelgrass area",
        },
        # Coastal protection
        {
            "co_benefit": "Coastal protection",
            "metric": "Wave attenuation by eelgrass canopy",
            "value": None,
            "uncertainty": None,
            "unit": "qualitative",
            "geographic_scope": "Global literature",
            "year": None,
            "data_source": "Ondiviela et al. 2014; Infantes et al. 2022",
            "data_quality": "low — no Norway-specific measurement",
            "norway_specific": False,
            "notes": (
                "No Norwegian empirical quantification of coastal protection by eelgrass. "
                "Root/rhizome sediment stabilization well-established globally."
            ),
        },
        # Economic valuation
        {
            "co_benefit": "Economic valuation (blue carbon)",
            "metric": "Annual value of seagrass carbon sequestration (EU ETS)",
            "value": None,  # populated by valuation table
            "uncertainty": None,
            "unit": "million USD yr⁻¹",
            "geographic_scope": "National",
            "year": 2024,
            "data_source": "Derived — EU ETS 2024 price × sequestration estimate",
            "data_quality": "medium — price is market rate, sequestration is Tier 2",
            "norway_specific": True,
            "notes": "See step2_valuation.csv for full price-scenario breakdown",
        },
    ]

    # If Nature Index data was downloaded, add 2024 indicator-level rows
    BLUE_CARBON_NI_IDS = {74, 75, 21, 22, 145}  # most relevant for blue carbon
    if ni_df is not None and not ni_df.empty:
        ni_2024 = ni_df[ni_df["year_t"] == 2024]
        for _, row in ni_2024.iterrows():
            relevance = "blue_carbon_relevant" if row["id"] in BLUE_CARBON_NI_IDS else "coastal_ecosystem"
            rows.append({
                "co_benefit": "Biodiversity — NI indicator",
                "metric": row.get("name", ""),
                "value": round(row.get("median", None), 4),
                "uncertainty": f"q025={round(row.get('q025', 0), 4)}, q975={round(row.get('q975', 0), 4)}",
                "unit": "scaled index (0–1)",
                "geographic_scope": "National",
                "year": 2024,
                "data_source": "NINA / Naturindeks 2025",
                "data_quality": "high",
                "norway_specific": True,
                "notes": relevance,
            })

    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main():
    obs = load_observations()
    gundersen = load_gundersen_national()
    ni_df = load_nature_index()

    # ── 2.1 Sequestration ────────────────────────────────────────────────
    sg_results = compute_seagrass_sequestration(obs)
    ma_results = compute_macroalgae_sequestration(gundersen)

    # Regional seagrass table
    sg_regional = sg_results["regional"]
    sg_regional["ecosystem"] = "seagrass"
    sg_regional.to_csv(OUT / "step2_seagrass_stocks_by_region.csv", index=False)
    print("✓ step2_seagrass_stocks_by_region.csv")

    # National summary — both ecosystems
    national_rows = [sg_results["national"], ma_results]
    national_df = pd.DataFrame(national_rows)
    national_df.to_csv(OUT / "step2_national_sequestration.csv", index=False)
    print("✓ step2_national_sequestration.csv")

    # Carbon valuation
    valuation_df = compute_carbon_valuation(
        seq_seagrass_gg=sg_results["national"]["seq_gg_c_yr"],
        seq_macroalgae_gg=ma_results["seq_gg_c_yr"],
    )
    valuation_df.to_csv(OUT / "step2_valuation.csv", index=False)
    print("✓ step2_valuation.csv")

    # ── 2.2 Co-benefits ──────────────────────────────────────────────────
    cobenefits_df = build_cobenefits_summary(ni_df)
    cobenefits_df.to_csv(OUT / "step2_cobenefits.csv", index=False)
    print("✓ step2_cobenefits.csv")

    # ── Print key numbers ─────────────────────────────────────────────────
    sg = sg_results["national"]
    print("\n── Seagrass national sequestration ──")
    print(f"  Extent (modeled):  {sg['extent_km2_modeled']} km²")
    print(f"  Mean stock:        {sg['mean_stock_g_m2']:.0f} ± {sg['sd_stock_g_m2']:.0f} g C m⁻²")
    print(f"  Stock (national):  {sg['stock_gg_c']:.1f} ± {sg['stock_gg_c_sd']:.1f} Gg C")
    print(f"  Sequestration:     {sg['seq_gg_c_yr']:.2f} ± {sg['seq_gg_c_yr_sd']:.2f} Gg C yr⁻¹")
    print(f"  IPCC tier:         {sg['ipcc_tier']}")

    ma = ma_results
    print("\n── Macroalgae national sequestration (Gundersen 2021) ──")
    print(f"  Extent:            {ma['extent_km2']:,.0f} km² "
          f"(CI: {ma['extent_km2_ci_low']:,.0f}–{ma['extent_km2_ci_high']:,.0f})")
    print(f"  Stock:             {ma['stock_mt_c']} Mt C "
          f"(= {ma['stock_gg_c']:,.0f} Gg C)")
    print(f"  Sequestration:     {ma['seq_mt_c_yr']} Mt C yr⁻¹ "
          f"(CI: {ma['seq_mt_c_yr_ci_low']}–{ma['seq_mt_c_yr_ci_high']})")
    print(f"  IPCC tier:         {ma['ipcc_tier']}")

    print("\n── Carbon valuation (EU ETS scenario) ──")
    eu_rows = valuation_df[valuation_df["price_scenario"] == "EU_ETS_2024_EUR_tCO2"]
    for _, r in eu_rows.iterrows():
        print(f"  {r['ecosystem']:12s}: {r['annual_value_million_usd']:.1f} M USD yr⁻¹ "
              f"({r['seq_mt_co2_yr']:.4f} Mt CO₂ × €{r['price_per_tco2']}/t)")

    if ni_df is None:
        print("\n⚠  Nature Index data not available — download manually (see "
              "data/external/nature_index/README.md)")
    else:
        print(f"\n✓ Nature Index: {len(ni_df)} coastal indicators loaded")


if __name__ == "__main__":
    main()
