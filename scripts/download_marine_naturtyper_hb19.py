"""Download Naturbase Marine naturtyper (HB19) polygons.

This pulls official Miljødirektoratet / Naturbase marine nature-type layers
from the public ArcGIS REST service and stores them as derived data.

Default layers:
  - layer 1: naturtype_marin_hb19_tare     (larger kelp forest occurrences)
  - layer 7: naturtype_marin_hb19_alegras  (eelgrass areas)

Outputs:
  - data/external/naturbase_hb19/<layer>.geojson
  - data/external/naturbase_hb19/naturbase_hb19_features.csv
  - data/external/naturbase_hb19/naturbase_hb19_download_manifest.json

Run:
  /opt/anaconda3/envs/ella-capstone/bin/python scripts/download_marine_naturtyper_hb19.py

The raw Excel workbooks in data/ are not modified.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen


REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "data" / "external" / "naturbase_hb19"

SERVICE_URL = (
    "https://kart.miljodirektoratet.no/arcgis/rest/services/"
    "naturtyper_marine_hb19/MapServer"
)

DEFAULT_LAYERS = {
    "tare": {
        "id": 1,
        "arcgis_name": "naturtype_marin_hb19_tare",
        "ecosystem": "macroalgae",
        "inventory_hint": "larger_kelp_forest_occurrence",
    },
    "alegras": {
        "id": 7,
        "arcgis_name": "naturtype_marin_hb19_alegras",
        "ecosystem": "seagrass",
        "inventory_hint": "eelgrass_area",
    },
}

NATURTYPE_LABELS = {
    "I01": "Større tareskogforekomster",
    "I02": "Sterke tidevannsstrømmer",
    "I03": "Fjorder med naturlig lavt oksygeninnhold i bunnvannet",
    "I04": "Spesielt dype fjordområder",
    "I05": "Poller",
    "I06": "Littoralbasseng",
    "I07": "Israndavsetninger",
    "I08": "Bløtbunnsområder i strandsonen",
    "I09": "Korallforekomster",
    "I10": "Løstliggende kalkalgeforekomster",
    "I11": "Ålegrasenger og andre undervannsenger",
    "I12": "Skjellsand",
    "I14": "Større kamskjellforekomster",
    "I15": "Andre viktige forekomster",
}

VALUE_LABELS = {
    "A": "Svært viktig",
    "B": "Viktig",
    "C": "Lokalt viktig",
}


def fetch_json(url: str, params: dict, timeout: int = 120) -> dict:
    full_url = f"{url}?{urlencode(params)}"
    with urlopen(full_url, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        body = response.read().decode(charset)
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            preview = body[:500].replace("\n", " ")
            raise RuntimeError(f"Response was not JSON: {preview}") from exc


def query_layer(layer_id: int, page_size: int = 250, pause_s: float = 0.05) -> list[dict]:
    """Fetch all features from one ArcGIS REST layer as GeoJSON features."""
    layer_url = f"{SERVICE_URL}/{layer_id}/query"
    features: list[dict] = []
    offset = 0
    while True:
        payload = fetch_json(
            layer_url,
            {
                "f": "geojson",
                "where": "1=1",
                "outFields": "*",
                "returnGeometry": "true",
                "outSR": "4326",
                "resultOffset": offset,
                "resultRecordCount": page_size,
            },
        )
        if "error" in payload:
            raise RuntimeError(f"ArcGIS query failed for layer {layer_id}: {payload['error']}")
        batch = payload.get("features", [])
        features.extend(batch)
        print(f"    fetched {len(features)} features from layer {layer_id}", flush=True)
        if len(batch) < page_size:
            break
        offset += page_size
        if pause_s:
            time.sleep(pause_s)
    return features


def geometry_bbox(geometry: dict | None):
    if not geometry:
        return None, None, None, None
    coords = []

    def collect(value):
        if isinstance(value, (list, tuple)) and len(value) >= 2 and all(
            isinstance(x, (int, float)) for x in value[:2]
        ):
            coords.append((float(value[0]), float(value[1])))
            return
        if isinstance(value, (list, tuple)):
            for item in value:
                collect(item)

    collect(geometry.get("coordinates"))
    if not coords:
        return None, None, None, None
    xs = [x for x, _ in coords]
    ys = [y for _, y in coords]
    return min(xs), min(ys), max(xs), max(ys)


def feature_csv_row(feature: dict, layer_key: str, layer_cfg: dict) -> dict:
    props = feature.get("properties") or {}
    min_lon, min_lat, max_lon, max_lat = geometry_bbox(feature.get("geometry"))
    naturtype = props.get("naturtype")
    verdi = props.get("verdi")
    faktaark = props.get("faktaark")
    if faktaark and not str(faktaark).startswith("http"):
        faktaark = f"https://faktaark.naturbase.no/?id={faktaark}"

    return {
        "external_id": props.get("marinNaturtypeId"),
        "layer_key": layer_key,
        "layer_id": layer_cfg["id"],
        "arcgis_layer_name": layer_cfg["arcgis_name"],
        "ecosystem": layer_cfg["ecosystem"],
        "inventory_hint": layer_cfg["inventory_hint"],
        "omraadenavn": props.get("omraadenavn"),
        "naturtype_code": naturtype,
        "naturtype_label": NATURTYPE_LABELS.get(naturtype, ""),
        "utforming": props.get("utforming"),
        "verdi_code": verdi,
        "verdi_label": VALUE_LABELS.get(verdi, ""),
        "kommune": props.get("kommune"),
        "modellert": props.get("modellert"),
        "punkt": props.get("punkt"),
        "registreringsDato": props.get("registreringsDato"),
        "datafangstdato": props.get("datafangstdato"),
        "faktaark": faktaark,
        "area_m2": props.get("SHAPE.STArea()"),
        "length_m": props.get("SHAPE.STLength()"),
        "bbox_min_lon": min_lon,
        "bbox_min_lat": min_lat,
        "bbox_max_lon": max_lon,
        "bbox_max_lat": max_lat,
        "centroid_lon_approx": (min_lon + max_lon) / 2 if min_lon is not None else None,
        "centroid_lat_approx": (min_lat + max_lat) / 2 if min_lat is not None else None,
        "source_name": "Naturbase Marine naturtyper (HB19)",
        "source_url": SERVICE_URL,
        "license": "Norsk lisens for offentlege data (NLOD)",
    }


def write_geojson(path: Path, features: list[dict], layer_key: str, layer_cfg: dict) -> None:
    collection = {
        "type": "FeatureCollection",
        "name": layer_cfg["arcgis_name"],
        "metadata": {
            "source_name": "Naturbase Marine naturtyper (HB19)",
            "source_url": SERVICE_URL,
            "layer_key": layer_key,
            "layer_id": layer_cfg["id"],
            "arcgis_layer_name": layer_cfg["arcgis_name"],
            "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
            "license": "Norsk lisens for offentlege data (NLOD)",
            "outSR": "EPSG:4326",
        },
        "features": features,
    }
    path.write_text(json.dumps(collection, ensure_ascii=False), encoding="utf-8")


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--layers",
        nargs="+",
        choices=sorted(DEFAULT_LAYERS),
        default=sorted(DEFAULT_LAYERS),
        help="Layer keys to download. Defaults to tare and alegras.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=OUT_DIR,
        help="Output directory for GeoJSON, CSV index and manifest.",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=250,
        help="ArcGIS resultRecordCount page size. Lower this if large polygon responses fail.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict] = []
    manifest = {
        "source_name": "Naturbase Marine naturtyper (HB19)",
        "service_url": SERVICE_URL,
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
        "license": "Norsk lisens for offentlege data (NLOD)",
        "layers": [],
    }

    for layer_key in args.layers:
        cfg = DEFAULT_LAYERS[layer_key]
        print(f"Downloading {layer_key} ({cfg['arcgis_name']}, layer {cfg['id']})...", flush=True)
        features = query_layer(cfg["id"], page_size=args.page_size)
        out_geojson = args.out_dir / f"naturbase_hb19_{layer_key}.geojson"
        write_geojson(out_geojson, features, layer_key, cfg)
        rows = [feature_csv_row(feature, layer_key, cfg) for feature in features]
        all_rows.extend(rows)
        manifest["layers"].append(
            {
                "layer_key": layer_key,
                "layer_id": cfg["id"],
                "arcgis_layer_name": cfg["arcgis_name"],
                "feature_count": len(features),
                "geojson_path": str(out_geojson.relative_to(REPO_ROOT)),
            }
        )
        print(f"  wrote {out_geojson} ({len(features)} features)", flush=True)

    csv_path = args.out_dir / "naturbase_hb19_features.csv"
    manifest_path = args.out_dir / "naturbase_hb19_download_manifest.json"
    write_csv(csv_path, all_rows)
    manifest["feature_index_csv"] = str(csv_path.relative_to(REPO_ROOT))
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Wrote {csv_path} ({len(all_rows)} rows)", flush=True)
    print(f"Wrote {manifest_path}", flush=True)


if __name__ == "__main__":
    main()
