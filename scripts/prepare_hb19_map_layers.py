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


def prepare_layer(key: str, tolerance: float) -> int:
    src = INPUTS[key]
    dst = OUTPUTS[key]
    if not src.exists():
        raise FileNotFoundError(f"Missing HB19 input: {src}")

    gdf = gpd.read_file(src)
    keep = [c for c in KEEP_COLUMNS if c in gdf.columns]
    gdf = gdf[keep].copy()
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    else:
        gdf = gdf.to_crs("EPSG:4326")

    gdf["verdi_label"] = gdf["verdi"].map(VALUE_LABELS).fillna("")
    gdf["naturtype_label"] = gdf["naturtype"].map(NATURTYPE_LABELS).fillna("")
    gdf["area_m2"] = gdf["SHAPE.STArea()"] if "SHAPE.STArea()" in gdf.columns else None
    if "SHAPE.STArea()" in gdf.columns:
        gdf = gdf.drop(columns=["SHAPE.STArea()"])

    # Use a small tolerance in decimal degrees. This keeps visual coast-scale
    # placement while shrinking the self-contained Folium HTML substantially.
    gdf["geometry"] = gdf.geometry.simplify(tolerance, preserve_topology=True)
    gdf = gdf[~gdf.geometry.is_empty & gdf.geometry.notna()].copy()

    dst.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(dst, driver="GeoJSON")
    return len(gdf)


def main() -> None:
    counts = {}
    for key in ("alegras", "tare"):
        print(f"Preparing {key}...", flush=True)
        counts[key] = prepare_layer(key, tolerance=0.001)
        print(f"  wrote {OUTPUTS[key]} ({counts[key]} features)", flush=True)


if __name__ == "__main__":
    main()
