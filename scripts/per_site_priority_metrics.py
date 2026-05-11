"""Compute per-site risk and co-benefit composites.

For each study site point, count pressures (dredging, akvakultur, platforms)
within a 5 km radius using haversine distance. Co-benefit pulls regional MPA %
and habitat extent from spatial_analysis/regional_colocation_summary.csv.

Pure pandas/numpy — no geopandas required, since pressure inputs are point
CSVs and protection metrics are already aggregated by region.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = REPO_ROOT / "data" / "processed" / "per_site_priority_metrics.csv"

DREDGING_PATH = REPO_ROOT / "data" / "external" / "emodnet" / "emodnet_dredging.csv"
AKVAKULTUR_PATH = REPO_ROOT / "data" / "external" / "akvakultur" / "akvakultur_marine_sites.csv"
PLATFORMS_PATH = REPO_ROOT / "data" / "external" / "emodnet" / "emodnet_platforms.csv"
MASTER_SITES_PATH = REPO_ROOT / "data" / "processed" / "norway_blue_carbon_master_sites.csv"
REGIONAL_SUMMARY_PATH = REPO_ROOT / "data" / "processed" / "spatial_analysis" / "regional_colocation_summary.csv"

BUFFER_KM = 5.0
EARTH_R_KM = 6371.0


def haversine_km(lat1: np.ndarray, lon1: np.ndarray, lat2: np.ndarray, lon2: np.ndarray) -> np.ndarray:
    """Vectorised great-circle distance in km. lat1/lon1 broadcast over lat2/lon2."""
    lat1r = np.deg2rad(lat1)
    lat2r = np.deg2rad(lat2)
    dlat = lat2r - lat1r
    dlon = np.deg2rad(lon2 - lon1)
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1r) * np.cos(lat2r) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_R_KM * np.arcsin(np.sqrt(a))


def count_within_buffer(
    site_lats: np.ndarray,
    site_lons: np.ndarray,
    point_lats: np.ndarray,
    point_lons: np.ndarray,
    radius_km: float,
) -> np.ndarray:
    """Return per-site count of points within radius_km."""
    if point_lats.size == 0:
        return np.zeros(site_lats.size, dtype=int)
    counts = np.zeros(site_lats.size, dtype=int)
    for i in range(site_lats.size):
        d = haversine_km(site_lats[i], site_lons[i], point_lats, point_lons)
        counts[i] = int((d <= radius_km).sum())
    return counts


def load_pressure_points(path: Path) -> tuple[np.ndarray, np.ndarray]:
    if not path.exists():
        return np.array([]), np.array([])
    df = pd.read_csv(path)
    df = df.dropna(subset=["lat_dd", "lon_dd"])
    return df["lat_dd"].to_numpy(dtype=float), df["lon_dd"].to_numpy(dtype=float)


def z_within(s: pd.Series) -> pd.Series:
    sd = s.std(ddof=0)
    if sd == 0 or pd.isna(sd):
        return pd.Series(0.0, index=s.index)
    return (s - s.mean()) / sd


def main() -> None:
    sites = pd.read_csv(MASTER_SITES_PATH)
    sites = sites[
        (sites["source_scale"] == "site")
        & sites["latitude"].notna()
        & sites["longitude"].notna()
    ].copy().reset_index(drop=True)

    site_lat = sites["latitude"].to_numpy(dtype=float)
    site_lon = sites["longitude"].to_numpy(dtype=float)

    dredge_lat, dredge_lon = load_pressure_points(DREDGING_PATH)
    akva_lat, akva_lon = load_pressure_points(AKVAKULTUR_PATH)
    plat_lat, plat_lon = load_pressure_points(PLATFORMS_PATH)

    sites["dredging_5km_n"] = count_within_buffer(site_lat, site_lon, dredge_lat, dredge_lon, BUFFER_KM)
    sites["akvakultur_5km_n"] = count_within_buffer(site_lat, site_lon, akva_lat, akva_lon, BUFFER_KM)
    sites["platforms_5km_n"] = count_within_buffer(site_lat, site_lon, plat_lat, plat_lon, BUFFER_KM)

    # Nearby other study sites (use same lat/lon arrays, exclude self)
    nearby = np.zeros(len(sites), dtype=int)
    for i in range(len(sites)):
        d = haversine_km(site_lat[i], site_lon[i], site_lat, site_lon)
        nearby[i] = int((d <= BUFFER_KM).sum() - 1)
    sites["studies_within_5km_n"] = nearby

    # Regional context (% MPA, habitat km2) — fall back to ecosystem mean if NaN
    reg = pd.read_csv(REGIONAL_SUMMARY_PATH)
    reg = reg[["ecosystem", "canonical_region", "percent_habitat_in_mpa", "habitat_area_km2"]]

    # Map Oslofjord into Skagerrak (regional summary used 3-region cut)
    sites["join_region"] = sites["canonical_region"].replace({"Oslofjord": "Skagerrak"})
    merged = sites.merge(
        reg, left_on=["ecosystem", "join_region"], right_on=["ecosystem", "canonical_region"],
        how="left", suffixes=("", "_reg"),
    )
    merged["percent_habitat_in_mpa"] = merged["percent_habitat_in_mpa"].fillna(
        merged.groupby("ecosystem")["percent_habitat_in_mpa"].transform("mean")
    )
    merged["habitat_area_km2"] = merged["habitat_area_km2"].fillna(
        merged.groupby("ecosystem")["habitat_area_km2"].transform("mean")
    )

    out_cols = [
        "site_id", "site_name", "ecosystem", "canonical_region", "source_short",
        "latitude", "longitude", "carbon_stock_g_m2", "year",
        "dredging_5km_n", "akvakultur_5km_n", "platforms_5km_n",
        "studies_within_5km_n",
        "percent_habitat_in_mpa", "habitat_area_km2",
    ]
    out = merged[out_cols].copy()

    # Composite z-scores within ecosystem (equal weights)
    risk_components = ["dredging_5km_n", "akvakultur_5km_n", "platforms_5km_n"]
    cobenefit_components = ["percent_habitat_in_mpa", "studies_within_5km_n", "habitat_area_km2"]

    out["risk_z"] = 0.0
    out["cobenefit_z"] = 0.0
    for eco, idx in out.groupby("ecosystem").groups.items():
        sub = out.loc[idx]
        risk_sum = sum(z_within(sub[c]) for c in risk_components)
        out.loc[idx, "risk_z"] = (risk_sum / len(risk_components)).values

        # log habitat area to dampen outliers
        log_area = np.log1p(sub["habitat_area_km2"].fillna(0))
        cb_sum = (
            z_within(sub["percent_habitat_in_mpa"])
            + z_within(sub["studies_within_5km_n"])
            + z_within(pd.Series(log_area.values, index=sub.index))
        )
        out.loc[idx, "cobenefit_z"] = (cb_sum / len(cobenefit_components)).values

    out.to_csv(OUT_PATH, index=False)
    print(f"wrote: {OUT_PATH}")
    print(f"sites total: {len(out)}")
    print(out.groupby("ecosystem").size())
    print()
    print("preview:")
    print(out[["site_name", "ecosystem", "canonical_region", "carbon_stock_g_m2",
               "dredging_5km_n", "akvakultur_5km_n", "platforms_5km_n",
               "risk_z", "cobenefit_z"]].to_string(index=False))


if __name__ == "__main__":
    main()
