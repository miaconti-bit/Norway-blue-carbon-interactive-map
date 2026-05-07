"""Build normalized Norway blue-carbon inventory tables.

Inputs are the raw Excel workbooks in data/. They are treated as read-only.

Outputs:
  - data/processed/norway_blue_carbon_master_sites.csv
  - data/processed/norway_blue_carbon_observations.csv
  - data/processed/norway_blue_carbon_sources.csv
  - data/processed/norway_blue_carbon_inventory.xlsx

The "master_sites" table is an inventory-unit table. It includes true point
sites, aggregate regional survey/case-study rows, and national summaries, with
the row type explicit in inventory_record_type.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "data"
OUT_DIR = RAW_DIR / "processed"

KELP_PATH = RAW_DIR / "Norway_Macroalgae_Database.xlsm"
SEAGRASS_PATH = RAW_DIR / "Norway_Seagrass_ Master_Database (4).xlsx"

SITES_OUT = OUT_DIR / "norway_blue_carbon_master_sites.csv"
OBS_OUT = OUT_DIR / "norway_blue_carbon_observations.csv"
SOURCES_OUT = OUT_DIR / "norway_blue_carbon_sources.csv"
XLSX_OUT = OUT_DIR / "norway_blue_carbon_inventory.xlsx"

SEAGRASS_SOURCE_URL = "https://www.nature.com/articles/s41598-024-74760-3"
SEAGRASS_COORD_SOURCE = (
    "Gagnon et al. 2024 supplementary Table S1 (MOESM2_ESM.docx)"
)

# Decimal-degree coordinates from Gagnon et al. 2024 supplementary Table S1.
SEAGRASS_COORDS: dict[str, tuple[float, float]] = {
    "Sømskilen": (58.404, 8.714),
    "Ærøya": (58.417, 8.763),
    "Merdø": (58.428, 8.808),
    "Langerompa": (58.431, 8.801),
    "Hove": (58.448, 8.818),
    "Sandspollen": (59.663, 10.590),
    "Kapellkilen": (59.666, 10.587),
    "Røvik": (67.215, 15.008),
    "Porsanger": (70.112, 25.232),
}


def clean_text(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return pd.NA
    text = str(value).strip()
    return text if text else pd.NA


def first_number(value) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    m = re.search(r"[-+]?\d+(?:\.\d+)?", str(value))
    return float(m.group(0)) if m else None


def extract_year(value) -> int | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    m = re.search(r"(19|20)\d{2}", str(value))
    return int(m.group(0)) if m else None


def dms_to_dd(value) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = unicodedata.normalize("NFKC", str(value)).strip()
    s = (
        s.replace("’", "'")
        .replace("‘", "'")
        .replace("”", '"')
        .replace("“", '"')
        .replace("′", "'")
        .replace("″", '"')
    )
    s = s.replace("''", '"')
    m = re.search(
        r"([0-9]+(?:\.[0-9]+)?)°\s*([0-9]+(?:\.[0-9]+)?)?'?\s*"
        r"([0-9]+(?:\.[0-9]+)?)?\"?\s*([NSEW])",
        s,
    )
    if not m:
        return None
    deg = float(m.group(1))
    minutes = float(m.group(2) or 0)
    seconds = float(m.group(3) or 0)
    hemi = m.group(4)
    dd = deg + minutes / 60 + seconds / 3600
    return -dd if hemi in ("S", "W") else round(dd, 6)


def canonical_region(region_str: str | None, lat: float | None) -> str:
    s = (region_str or "").lower()
    if any(k in s for k in ("barents", "porsanger", "hammerfest", "northern norway", "bodø")):
        return "Barents Sea"
    if "norwegian sea" in s:
        return "Norwegian Sea"
    if "outer oslofjord" in s or "skagerrak" in s:
        return "Skagerrak"
    if "oslofjord" in s:
        return "Oslofjord"
    if any(k in s for k in ("hardanger", "sognef", "mid-norway", "north sea", "southwest norway", "west norway")):
        return "Norwegian Sea"
    if lat is None or pd.isna(lat):
        return "Unknown"
    if lat >= 67:
        return "Barents Sea"
    if lat >= 60:
        return "Norwegian Sea"
    return "Skagerrak"


def source_id(source_text) -> str:
    text = str(clean_text(source_text) or "Unknown source")
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return f"src_{slug[:56]}" if slug else "src_unknown"


def classify_macro_site(row: pd.Series) -> str:
    if pd.notna(row.get("lat")) and pd.notna(row.get("lon")):
        return "true_point_site"
    name = str(row.get("Site", "")).lower()
    source = str(row.get("Source_short", "")).lower()
    notes = str(row.get("Notes", "")).lower()
    if any(k in name for k in ("recolonization", "artificial reefs", "experiment")):
        return "case_study"
    if "christie" in source and any(k in name for k in ("survey", "monitoring stations")):
        return "regional_survey"
    if "resurvey" in name or "survey" in name:
        return "regional_survey"
    if "intervention" in notes or "restoration" in notes:
        return "case_study"
    return "regional_survey"


def make_site_id(ecosystem: str, scale: str, name, region, index: int) -> str:
    base = f"{ecosystem}_{scale}_{name}_{region}_{index}".lower()
    slug = re.sub(r"[^a-z0-9]+", "_", base).strip("_")
    return f"site_{slug}"


def metric(row: pd.Series, *names):
    for name in names:
        if name in row and pd.notna(row[name]):
            return row[name]
    return pd.NA


def build_macro_tables() -> tuple[list[dict], list[dict], list[dict]]:
    sites: list[dict] = []
    observations: list[dict] = []
    sources: list[dict] = []

    for sheet_name, scale in [
        ("Site_Level", "site"),
        ("Regional", "regional"),
        ("National", "national"),
    ]:
        df = pd.read_excel(KELP_PATH, sheet_name=sheet_name, header=1, engine="openpyxl")
        df = df.dropna(how="all").copy()
        if "Latitude" in df:
            df["lat"] = df["Latitude"].apply(dms_to_dd)
            df["lon"] = df["Longitude"].apply(dms_to_dd)
        else:
            df["lat"] = pd.NA
            df["lon"] = pd.NA

        source_col = "Source_short" if "Source_short" in df else "Source"
        for i, row in df.iterrows():
            src = row.get(source_col)
            sid = source_id(src)
            rec_type = (
                classify_macro_site(row)
                if scale == "site"
                else f"{scale}_summary"
            )
            lat = row.get("lat")
            region = clean_text(row.get("Region"))
            site_id = make_site_id("macroalgae", scale, row.get("Site"), region, i)
            canonical = canonical_region(region, lat)
            sites.append(
                {
                    "site_id": site_id,
                    "ecosystem": "macroalgae",
                    "inventory_record_type": rec_type,
                    "source_scale": scale,
                    "site_name": clean_text(row.get("Site")),
                    "region_source": region,
                    "canonical_region": canonical,
                    "latitude": lat,
                    "longitude": row.get("lon"),
                    "coordinate_source": "raw workbook DMS coordinates" if pd.notna(lat) else pd.NA,
                    "coordinate_status": "present" if pd.notna(lat) and pd.notna(row.get("lon")) else "missing_or_aggregate",
                    "species": clean_text(row.get("Species")),
                    "habitat": clean_text(row.get("Habitat_type") or row.get("Habitat")),
                    "substrate": clean_text(row.get("Substrate_type")),
                    "year_raw": clean_text(row.get("Year")),
                    "year": extract_year(row.get("Year")),
                    "sample_size_n": first_number(row.get("Sample_size_n")),
                    "depth_m": first_number(row.get("Water_depth_mean_m")),
                    "depth_range_m": clean_text(row.get("Depth_range_m")),
                    "area_measured_km2": first_number(row.get("Area_measured_km2")),
                    "area_modeled_km2": first_number(row.get("Area_modeled_km2")),
                    "carbon_stock_g_m2": first_number(row.get("Biomass_C_stock_mean_g_m2")),
                    "standing_biomass_g_m2": first_number(row.get("Standing_biomass_g_m2")),
                    "npp_g_m2_yr": first_number(row.get("NPP_g_m2_yr")),
                    "sequestration_rate_g_m2_yr": pd.NA,
                    "source_id": sid,
                    "source_short": clean_text(src),
                    "source_url": clean_text(row.get("Source_URL")),
                    "source_location": clean_text(row.get("Source_location")),
                    "notes": clean_text(row.get("Notes")),
                    "raw_workbook": KELP_PATH.name,
                    "raw_sheet": sheet_name,
                    "raw_row_number_excel": int(i) + 3,
                }
            )

            if scale == "site":
                observations.append(
                    {
                        "observation_id": f"obs_{site_id}",
                        "site_id": site_id,
                        "ecosystem": "macroalgae",
                        "inventory_record_type": rec_type,
                        "site_name": clean_text(row.get("Site")),
                        "canonical_region": canonical,
                        "year_raw": clean_text(row.get("Year")),
                        "year": extract_year(row.get("Year")),
                        "habitat": clean_text(row.get("Habitat_type")),
                        "species": clean_text(row.get("Species")),
                        "water_depth_m": first_number(row.get("Water_depth_mean_m")),
                        "depth_range_m": clean_text(row.get("Depth_range_m")),
                        "sample_size_n": first_number(row.get("Sample_size_n")),
                        "sediment_or_substrate": clean_text(row.get("Substrate_type")),
                        "sediment_c_stock_g_m2": pd.NA,
                        "biomass_c_stock_g_m2": first_number(row.get("Biomass_C_stock_mean_g_m2")),
                        "standing_biomass_g_m2": first_number(row.get("Standing_biomass_g_m2")),
                        "aboveground_biomass_g_m2": pd.NA,
                        "belowground_biomass_g_m2": pd.NA,
                        "temperature_mean_c": first_number(row.get("Temperature_mean_C")),
                        "salinity_psu": first_number(row.get("Salinity_mean_psu")),
                        "wave_exposure_index": first_number(row.get("Wave_exposure_mean")),
                        "source_id": sid,
                        "raw_workbook": KELP_PATH.name,
                        "raw_sheet": sheet_name,
                        "raw_row_number_excel": int(i) + 3,
                    }
                )

            sources.append(
                {
                    "source_id": sid,
                    "source_short": clean_text(src),
                    "source_url": clean_text(row.get("Source_URL")),
                    "source_location": clean_text(row.get("Source_location")),
                    "ecosystem": "macroalgae",
                    "raw_workbook": KELP_PATH.name,
                }
            )
    return sites, observations, sources


def build_seagrass_tables() -> tuple[list[dict], list[dict], list[dict]]:
    sites: list[dict] = []
    observations: list[dict] = []
    sources: list[dict] = []

    site_df = pd.read_excel(SEAGRASS_PATH, sheet_name="Site level", header=1, engine="openpyxl")
    site_df = site_df.dropna(subset=["Site Name"]).copy()
    site_df["source_id"] = site_df["Source:"].apply(source_id)
    site_df["year_int"] = site_df["Year"].apply(extract_year)
    site_df["lat"] = site_df["Site Name"].map(lambda s: SEAGRASS_COORDS.get(s, (pd.NA, pd.NA))[0])
    site_df["lon"] = site_df["Site Name"].map(lambda s: SEAGRASS_COORDS.get(s, (pd.NA, pd.NA))[1])
    site_df["canonical_region"] = site_df.apply(
        lambda r: canonical_region(r.get("Region"), r.get("lat")),
        axis=1,
    )

    grouped = site_df.groupby("Site Name", sort=True)
    for n, (site_name, group) in enumerate(grouped, start=1):
        first = group.iloc[0]
        lat = first.get("lat")
        lon = first.get("lon")
        source_text = "; ".join(sorted({str(x) for x in group["Source:"].dropna()}))
        sid = source_id(source_text)
        site_id = make_site_id("seagrass", "site", site_name, first.get("Region"), n)
        sites.append(
            {
                "site_id": site_id,
                "ecosystem": "seagrass",
                "inventory_record_type": "true_point_site",
                "source_scale": "site",
                "site_name": clean_text(site_name),
                "region_source": clean_text(first.get("Region")),
                "canonical_region": first.get("canonical_region"),
                "latitude": lat,
                "longitude": lon,
                "coordinate_source": SEAGRASS_COORD_SOURCE,
                "coordinate_status": "present" if pd.notna(lat) and pd.notna(lon) else "missing",
                "species": "Zostera marina",
                "habitat": "Eelgrass / unvegetated comparison",
                "substrate": ", ".join(sorted({str(x) for x in group["Sediment type"].dropna()})),
                "year_raw": years_range(group["year_int"]),
                "year": int(group["year_int"].min()) if group["year_int"].notna().any() else pd.NA,
                "sample_size_n": first_number(group["Sample size (n)"].sum()),
                "depth_m": group["Water depth (m)"].apply(first_number).mean(),
                "depth_range_m": number_range(group["Water depth (m)"].apply(first_number), suffix=" m"),
                "area_measured_km2": pd.NA,
                "area_modeled_km2": pd.NA,
                "carbon_stock_g_m2": group["Sediment C stock (g/m2)"].apply(first_number).mean(),
                "standing_biomass_g_m2": pd.NA,
                "npp_g_m2_yr": pd.NA,
                "sequestration_rate_g_m2_yr": group["Sequestration rate g/m2/yr"].apply(first_number).mean(),
                "source_id": sid,
                "source_short": clean_text(source_text),
                "source_url": SEAGRASS_SOURCE_URL if "Gagnon" in source_text else pd.NA,
                "source_location": "Site level sheet; coordinates transcribed from supplement",
                "notes": "Grouped from seagrass site-level rows; one row per named site.",
                "raw_workbook": SEAGRASS_PATH.name,
                "raw_sheet": "Site level",
                "raw_row_number_excel": pd.NA,
            }
        )

        for idx, row in group.iterrows():
            observations.append(
                {
                    "observation_id": f"obs_{site_id}_{int(row.get('ID')) if pd.notna(row.get('ID')) else idx}",
                    "site_id": site_id,
                    "ecosystem": "seagrass",
                    "inventory_record_type": "true_point_site",
                    "site_name": clean_text(row.get("Site Name")),
                    "canonical_region": row.get("canonical_region"),
                    "year_raw": clean_text(row.get("Year")),
                    "year": extract_year(row.get("Year")),
                    "habitat": clean_text(row.get("Habitat ")),
                    "species": "Zostera marina" if row.get("Habitat ") == "Eelgrass" else pd.NA,
                    "water_depth_m": first_number(row.get("Water depth (m)")),
                    "depth_range_m": pd.NA,
                    "sample_size_n": first_number(row.get("Sample size (n)")),
                    "sediment_or_substrate": clean_text(row.get("Sediment type")),
                    "sediment_c_stock_g_m2": first_number(row.get("Sediment C stock (g/m2)")),
                    "biomass_c_stock_g_m2": first_number(row.get("Biomass C (g/m2)")),
                    "standing_biomass_g_m2": pd.NA,
                    "aboveground_biomass_g_m2": first_number(row.get("Aboveground biomass g m2")),
                    "belowground_biomass_g_m2": first_number(row.get("Belowground biomass g m2")),
                    "temperature_mean_c": first_number(row.get("Temperature mean C")),
                    "salinity_psu": first_number(row.get("Salinity psu")),
                    "wave_exposure_index": first_number(row.get("Wave exposure index")),
                    "source_id": row.get("source_id"),
                    "raw_workbook": SEAGRASS_PATH.name,
                    "raw_sheet": "Site level",
                    "raw_row_number_excel": int(idx) + 3,
                }
            )

    for sheet_name, scale in [("Regional", "regional"), ("National", "national")]:
        df = pd.read_excel(SEAGRASS_PATH, sheet_name=sheet_name, header=1, engine="openpyxl")
        df = df.dropna(how="all").copy()
        for i, row in df.iterrows():
            region = clean_text(row.get("Region"))
            if pd.isna(region):
                continue
            site_id = make_site_id("seagrass", scale, region, region, i)
            canonical = canonical_region(region, None)
            rec_type = f"{scale}_summary"
            sites.append(
                {
                    "site_id": site_id,
                    "ecosystem": "seagrass",
                    "inventory_record_type": rec_type,
                    "source_scale": scale,
                    "site_name": clean_text(region),
                    "region_source": region,
                    "canonical_region": canonical,
                    "latitude": pd.NA,
                    "longitude": pd.NA,
                    "coordinate_source": pd.NA,
                    "coordinate_status": "not_applicable_aggregate",
                    "species": "Zostera marina",
                    "habitat": clean_text(row.get("Dominant Sediment type")),
                    "substrate": clean_text(row.get("Dominant Sediment type") or row.get("Dominant seabed substrate")),
                    "year_raw": clean_text(row.get("Years")),
                    "year": extract_year(row.get("Years")),
                    "sample_size_n": first_number(metric(row, "Sample size n", "Sample size n")),
                    "depth_m": first_number(metric(row, "Water depth mean m", "Depth mean m")),
                    "depth_range_m": pd.NA,
                    "area_measured_km2": first_number(row.get("Area measured km2")),
                    "area_modeled_km2": first_number(row.get("Area modeled km2")),
                    "carbon_stock_g_m2": first_number(metric(row, "Sediment C stock mean g m2", "Sediment C stock mean g m2")),
                    "standing_biomass_g_m2": pd.NA,
                    "npp_g_m2_yr": first_number(metric(row, "NPP g m2 year", "NPP GgC year-1")),
                    "sequestration_rate_g_m2_yr": first_number(metric(row, "Sequestration rate g/m2/yr", "Sequestration rate g m-2 year-1")),
                    "source_id": "src_seagrass_workbook_synthesis",
                    "source_short": "Norway seagrass workbook synthesis",
                    "source_url": SEAGRASS_SOURCE_URL,
                    "source_location": f"{sheet_name} sheet",
                    "notes": clean_text(row.get("Risk acknowledgement ")),
                    "raw_workbook": SEAGRASS_PATH.name,
                    "raw_sheet": sheet_name,
                    "raw_row_number_excel": int(i) + 3,
                }
            )

    source_rows = site_df[["Source:", "source_id"]].drop_duplicates()
    for _, row in source_rows.iterrows():
        sources.append(
            {
                "source_id": row["source_id"],
                "source_short": clean_text(row["Source:"]),
                "source_url": SEAGRASS_SOURCE_URL if "Gagnon" in str(row["Source:"]) else pd.NA,
                "source_location": "Seagrass site-level workbook",
                "ecosystem": "seagrass",
                "raw_workbook": SEAGRASS_PATH.name,
            }
        )
    sources.append(
        {
            "source_id": "src_seagrass_workbook_synthesis",
            "source_short": "Norway seagrass workbook synthesis",
            "source_url": SEAGRASS_SOURCE_URL,
            "source_location": "Regional and National sheets",
            "ecosystem": "seagrass",
            "raw_workbook": SEAGRASS_PATH.name,
        }
    )
    return sites, observations, sources


def years_range(values: pd.Series):
    years = sorted({int(v) for v in values.dropna()})
    if not years:
        return pd.NA
    if len(years) == 1:
        return str(years[0])
    return f"{years[0]}-{years[-1]}"


def number_range(values: pd.Series, suffix: str = ""):
    nums = [float(v) for v in values.dropna()]
    if not nums:
        return pd.NA
    lo = min(nums)
    hi = max(nums)
    if lo == hi:
        return f"{lo:g}{suffix}"
    return f"{lo:g}-{hi:g}{suffix}"


def first_preferred(values: pd.Series):
    vals = [v for v in values if pd.notna(v) and str(v).strip()]
    if not vals:
        return pd.NA
    http_vals = [v for v in vals if str(v).startswith("http")]
    return http_vals[0] if http_vals else vals[0]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    site_rows, obs_rows, source_rows = [], [], []

    for builder in (build_macro_tables, build_seagrass_tables):
        sites, observations, sources = builder()
        site_rows.extend(sites)
        obs_rows.extend(observations)
        source_rows.extend(sources)

    sites_df = pd.DataFrame(site_rows)
    obs_df = pd.DataFrame(obs_rows)
    sources_raw = pd.DataFrame(source_rows)
    sources_df = (
        sources_raw.groupby("source_id", as_index=False)
        .agg(
            source_short=("source_short", first_preferred),
            source_url=("source_url", first_preferred),
            source_location=("source_location", lambda s: "; ".join(sorted({str(v) for v in s.dropna()}))),
            ecosystem=("ecosystem", lambda s: "; ".join(sorted({str(v) for v in s.dropna()}))),
            raw_workbook=("raw_workbook", lambda s: "; ".join(sorted({str(v) for v in s.dropna()}))),
        )
        .sort_values(["ecosystem", "source_short"], na_position="last")
        .reset_index(drop=True)
    )

    sites_df = sites_df.sort_values(
        ["ecosystem", "source_scale", "canonical_region", "site_name"],
        na_position="last",
    ).reset_index(drop=True)
    obs_df = obs_df.sort_values(
        ["ecosystem", "canonical_region", "site_name", "year"],
        na_position="last",
    ).reset_index(drop=True)

    sites_df.to_csv(SITES_OUT, index=False)
    obs_df.to_csv(OBS_OUT, index=False)
    sources_df.to_csv(SOURCES_OUT, index=False)

    with pd.ExcelWriter(XLSX_OUT, engine="openpyxl") as writer:
        sites_df.to_excel(writer, sheet_name="master_sites", index=False)
        obs_df.to_excel(writer, sheet_name="observations", index=False)
        sources_df.to_excel(writer, sheet_name="sources", index=False)

    print(f"Wrote {SITES_OUT} ({len(sites_df)} rows)")
    print(f"Wrote {OBS_OUT} ({len(obs_df)} rows)")
    print(f"Wrote {SOURCES_OUT} ({len(sources_df)} rows)")
    print(f"Wrote {XLSX_OUT}")
    print("\nmaster_sites by ecosystem/type:")
    print(sites_df.groupby(["ecosystem", "inventory_record_type"]).size().to_string())
    print("\ntrue point sites by canonical region:")
    points = sites_df[sites_df["inventory_record_type"] == "true_point_site"]
    print(points.groupby(["ecosystem", "canonical_region"]).size().to_string())


if __name__ == "__main__":
    main()
