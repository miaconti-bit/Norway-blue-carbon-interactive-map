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


def prepare_verneomraader(tolerance: float = 0.001) -> tuple[int, int]:
    if not VERN_GEOJSON.exists():
        raise FileNotFoundError(f"Missing protected-area GeoJSON: {VERN_GEOJSON}")
    if not VERN_CSV.exists():
        raise FileNotFoundError(f"Missing protected-area CSV: {VERN_CSV}")

    gdf = gpd.read_file(VERN_GEOJSON)
    attrs = pd.read_csv(VERN_CSV)[["naturvernId", "is_mpa", "area_m2"]]
    gdf = gdf.merge(attrs, on="naturvernId", how="left")
    gdf["is_mpa"] = gdf["is_mpa"].fillna(False).astype(bool)

    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    else:
        gdf = gdf.to_crs("EPSG:4326")

    keep = [c for c in KEEP_COLUMNS if c in gdf.columns]
    gdf = gdf[keep].copy()
    gdf["geometry"] = gdf.geometry.simplify(tolerance, preserve_topology=True)
    gdf = gdf[~gdf.geometry.is_empty & gdf.geometry.notna()].copy()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    gdf.to_file(VERN_ALL_OUT, driver="GeoJSON")
    mpa = gdf[gdf["is_mpa"]].copy()
    mpa.to_file(VERN_MPA_OUT, driver="GeoJSON")
    return len(gdf), len(mpa)


def main() -> None:
    all_count, mpa_count = prepare_verneomraader()
    print(f"Wrote {VERN_ALL_OUT} ({all_count} features)")
    print(f"Wrote {VERN_MPA_OUT} ({mpa_count} features)")


if __name__ == "__main__":
    main()
