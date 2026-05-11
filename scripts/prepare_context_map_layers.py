"""Prepare lightweight context layers for the Norway Folium map.

Currently prepares Miljødirektoratet Verneområder polygons:
  - all marine-relevant protected areas
  - MPA-only subset

Run:
  /opt/anaconda3/envs/ella-capstone/bin/python scripts/prepare_context_map_layers.py
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parent.parent
VERN_DIR = REPO_ROOT / "data" / "external" / "verneomraader"
OUT_DIR = VERN_DIR / "map_layers"

VERN_GEOJSON = VERN_DIR / "verneomraader_all.geojson"
VERN_CSV = VERN_DIR / "verneomraader_features.csv"
VERN_ALL_OUT = OUT_DIR / "verneomraader_marine_map.geojson"
VERN_MPA_OUT = OUT_DIR / "verneomraader_mpa_map.geojson"

# See prepare_hb19_map_layers.py for the rationale on simplifying in metres
# rather than degrees. Protected-area polygons are much larger than habitat
# polygons, so a coarser tolerance is fine.
CRS_WGS84 = "EPSG:4326"
CRS_METERS = "EPSG:32633"
DEFAULT_TOLERANCE_M = 100

KEEP_COLUMNS = [
    "naturvernId",
    "navn",
    "offisieltNavn",
    "faktaark",
    "verneform",
    "kommune",
    "forvaltningsmyndighet",
    "iucn",
    "majorEcosystemType",
    "is_mpa",
    "area_m2",
    "geometry",
]


def simplify_in_meters(gdf: gpd.GeoDataFrame, tolerance_m: float) -> gpd.GeoDataFrame:
    """Reproject to UTM 33N, simplify with a metre-based tolerance, project back."""
    metric = gdf.to_crs(CRS_METERS)
    metric["geometry"] = metric.geometry.simplify(tolerance_m, preserve_topology=True)
    return metric.to_crs(CRS_WGS84)


def prepare_verneomraader(tolerance_m: float = DEFAULT_TOLERANCE_M) -> tuple[int, int]:
    if not VERN_GEOJSON.exists():
        raise FileNotFoundError(f"Missing protected-area GeoJSON: {VERN_GEOJSON}")
    if not VERN_CSV.exists():
        raise FileNotFoundError(f"Missing protected-area CSV: {VERN_CSV}")

    gdf = gpd.read_file(VERN_GEOJSON)
    attrs = pd.read_csv(VERN_CSV)[["naturvernId", "is_mpa", "area_m2"]]
    gdf = gdf.merge(attrs, on="naturvernId", how="left")
    gdf["is_mpa"] = gdf["is_mpa"].fillna(False).astype(bool)

    if gdf.crs is None:
        gdf = gdf.set_crs(CRS_WGS84)
    else:
        gdf = gdf.to_crs(CRS_WGS84)

    keep = [c for c in KEEP_COLUMNS if c in gdf.columns]
    gdf = gdf[keep].copy()
    gdf = simplify_in_meters(gdf, tolerance_m)
    gdf = gdf[~gdf.geometry.is_empty & gdf.geometry.notna()].copy()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    gdf.to_file(VERN_ALL_OUT, driver="GeoJSON")
    mpa = gdf[gdf["is_mpa"]].copy()
    mpa.to_file(VERN_MPA_OUT, driver="GeoJSON")
    return len(gdf), len(mpa)


def main() -> None:
    print(f"Preparing protected areas (tolerance: {DEFAULT_TOLERANCE_M} m in EPSG:32633)...", flush=True)
    all_count, mpa_count = prepare_verneomraader()
    print(f"Wrote {VERN_ALL_OUT} ({all_count} features)")
    print(f"Wrote {VERN_MPA_OUT} ({mpa_count} features)")


if __name__ == "__main__":
    main()
