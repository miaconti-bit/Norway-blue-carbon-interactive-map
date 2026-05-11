"""Prepare lightweight Naturbase HB19 layers for the Folium map.

The official kelp GeoJSON is large enough to make a self-contained HTML map
unwieldy. This script preserves the full downloaded files under data/external
and writes simplified, property-trimmed GeoJSON layers for map display.

Run:
  /opt/anaconda3/envs/ella-capstone/bin/python scripts/prepare_hb19_map_layers.py
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd


REPO_ROOT = Path(__file__).resolve().parent.parent
HB19_DIR = REPO_ROOT / "data" / "external" / "naturbase_hb19"
OUT_DIR = HB19_DIR / "map_layers"

# Project to UTM 33N before simplification so the tolerance has uniform
# meaning across the full Norwegian latitude range. Simplifying in degrees
# stretches non-uniformly: at 70°N a degree of longitude is ~38 km vs. ~111 km
# at the equator, so a degree-based tolerance over-simplifies small features
# in the longitudinal direction. Matches the CRS used by
# spatial_colocation_analysis.py.
CRS_WGS84 = "EPSG:4326"
CRS_METERS = "EPSG:32633"

# Per-layer simplification tolerance in metres. Eelgrass meadows are smaller
# and benefit from a tighter tolerance; kelp polygons are larger and tolerate
# more aggressive simplification.
TOLERANCE_M = {
    "alegras": 30,
    "tare": 75,
}

INPUTS = {
    "alegras": HB19_DIR / "naturbase_hb19_alegras.geojson",
    "tare": HB19_DIR / "naturbase_hb19_tare.geojson",
}

OUTPUTS = {
    "alegras": OUT_DIR / "naturbase_hb19_alegras_map.geojson",
    "tare": OUT_DIR / "naturbase_hb19_tare_map.geojson",
}

KEEP_COLUMNS = [
    "marinNaturtypeId",
    "omraadenavn",
    "naturtype",
    "verdi",
    "utforming",
    "kommune",
    "modellert",
    "faktaark",
    "SHAPE.STArea()",
    "geometry",
]

VALUE_LABELS = {
    "A": "Svært viktig",
    "B": "Viktig",
    "C": "Lokalt viktig",
}

NATURTYPE_LABELS = {
    "I01": "Større tareskogforekomster",
    "I11": "Ålegrasenger og andre undervannsenger",
}


def simplify_in_meters(gdf: gpd.GeoDataFrame, tolerance_m: float) -> gpd.GeoDataFrame:
    """Reproject to UTM 33N, simplify with a metre-based tolerance, project back."""
    metric = gdf.to_crs(CRS_METERS)
    metric["geometry"] = metric.geometry.simplify(tolerance_m, preserve_topology=True)
    return metric.to_crs(CRS_WGS84)


def prepare_layer(key: str, tolerance_m: float) -> int:
    src = INPUTS[key]
    dst = OUTPUTS[key]
    if not src.exists():
        raise FileNotFoundError(f"Missing HB19 input: {src}")

    gdf = gpd.read_file(src)
    keep = [c for c in KEEP_COLUMNS if c in gdf.columns]
    gdf = gdf[keep].copy()
    if gdf.crs is None:
        gdf = gdf.set_crs(CRS_WGS84)
    else:
        gdf = gdf.to_crs(CRS_WGS84)

    gdf["verdi_label"] = gdf["verdi"].map(VALUE_LABELS).fillna("")
    gdf["naturtype_label"] = gdf["naturtype"].map(NATURTYPE_LABELS).fillna("")
    gdf["area_m2"] = gdf["SHAPE.STArea()"] if "SHAPE.STArea()" in gdf.columns else None
    if "SHAPE.STArea()" in gdf.columns:
        gdf = gdf.drop(columns=["SHAPE.STArea()"])

    gdf = simplify_in_meters(gdf, tolerance_m)
    gdf = gdf[~gdf.geometry.is_empty & gdf.geometry.notna()].copy()

    dst.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(dst, driver="GeoJSON")
    return len(gdf)


def main() -> None:
    counts = {}
    for key in ("alegras", "tare"):
        tol = TOLERANCE_M[key]
        print(f"Preparing {key} (tolerance: {tol} m in EPSG:32633)...", flush=True)
        counts[key] = prepare_layer(key, tolerance_m=tol)
        print(f"  wrote {OUTPUTS[key]} ({counts[key]} features)", flush=True)


if __name__ == "__main__":
    main()
