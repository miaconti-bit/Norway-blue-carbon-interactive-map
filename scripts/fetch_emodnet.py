"""Download EMODnet Human Activities layers via the GeoServer WFS endpoint.

Fetches point/polygon datasets for Norwegian waters:
  - platforms     : oil and gas offshore platforms (pressure proxy)
  - dredging      : dredging activity areas
  - windfarms     : offshore wind farms

The vessel density map is a GeoTIFF raster; see candidate_sources.csv notes.

Outputs:
  - data/external/emodnet/emodnet_<layer>.geojson
  - data/external/emodnet/emodnet_<layer>.csv
  - data/external/emodnet/emodnet_manifest.json

Run:
  source .venv/bin/activate
  python scripts/fetch_emodnet.py
  python scripts/fetch_emodnet.py --layers platforms  # single layer
  python scripts/fetch_emodnet.py --bbox 4 57 31 72   # Norwegian waters (default)
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "data" / "external" / "emodnet"

WFS_BASE = "https://ows.emodnet-humanactivities.eu/geoserver/emodnet/ows"

LAYERS = {
    "platforms": {
        "wfs_name": "emodnet:platforms",
        "description": "Oil and gas offshore platforms",
    },
    "dredging": {
        "wfs_name": "emodnet:dredging",
        "description": "Dredging activity areas",
    },
    "windfarms": {
        "wfs_name": "emodnet:windfarms",
        "description": "Offshore wind farms (points)",
    },
}

# Norwegian waters bounding box (lon_min, lat_min, lon_max, lat_max) in EPSG:4326
NORWAY_BBOX = (4.0, 57.0, 31.0, 72.0)
LICENSE = "EMODnet Human Activities — free for non-commercial use with attribution"
SOURCE_NAME = "EMODnet Human Activities WFS"


def fetch_wfs_geojson(layer_name: str, bbox: tuple[float, float, float, float], timeout: int = 120) -> dict:
    lon_min, lat_min, lon_max, lat_max = bbox
    # WFS 2.0.0 + GeoServer: BBOX order lon_min,lat_min,lon_max,lat_max
    bbox_str = f"{lon_min},{lat_min},{lon_max},{lat_max},EPSG:4326"
    params = urlencode({
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": layer_name,
        "outputFormat": "application/json",
        "BBOX": bbox_str,
        "srsName": "EPSG:4326",
    })
    url = f"{WFS_BASE}?{params}"
    req = Request(url, headers={"User-Agent": "mia-capstone-research/1.0"})
    with urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        body = resp.read().decode(charset)
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Non-JSON WFS response for {layer_name}: {body[:400]}") from exc


def geojson_to_csv_rows(geojson: dict) -> list[dict]:
    rows = []
    for feature in geojson.get("features") or []:
        props = dict(feature.get("properties") or {})
        geom = feature.get("geometry") or {}
        if geom.get("type") == "Point":
            coords = geom.get("coordinates", [])
            props["lon_dd"] = coords[0] if len(coords) > 0 else None
            props["lat_dd"] = coords[1] if len(coords) > 1 else None
        rows.append(props)
    return rows


def write_geojson(path: Path, data: dict, metadata: dict) -> None:
    data["metadata"] = metadata
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bbox",
        nargs=4,
        type=float,
        metavar=("LON_MIN", "LAT_MIN", "LON_MAX", "LAT_MAX"),
        default=list(NORWAY_BBOX),
        help="Bounding box for spatial filter. Default: Norwegian waters.",
    )
    parser.add_argument(
        "--layers",
        nargs="+",
        choices=sorted(LAYERS),
        default=sorted(LAYERS),
    )
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    bbox = tuple(args.bbox)

    manifest = {
        "source_name": SOURCE_NAME,
        "wfs_version": "2.0.0",
        "wfs_base": WFS_BASE,
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
        "license": LICENSE,
        "bbox": bbox,
        "layers": [],
    }

    for key in args.layers:
        cfg = LAYERS[key]
        print(f"Fetching {cfg['description']} ({cfg['wfs_name']})...")
        geojson = fetch_wfs_geojson(cfg["wfs_name"], bbox=bbox)
        n = len(geojson.get("features") or [])
        print(f"  {n} features")

        meta = {
            "source_name": SOURCE_NAME,
            "wfs_layer": cfg["wfs_name"],
            "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
            "license": LICENSE,
            "bbox": bbox,
        }
        geojson_path = args.out_dir / f"emodnet_{key}.geojson"
        csv_path = args.out_dir / f"emodnet_{key}.csv"

        write_geojson(geojson_path, geojson, meta)
        rows = geojson_to_csv_rows(geojson)
        write_csv(csv_path, rows)

        print(f"  wrote {geojson_path}")
        print(f"  wrote {csv_path}")
        manifest["layers"].append({
            "key": key,
            "wfs_layer": cfg["wfs_name"],
            "feature_count": n,
            "geojson": str(geojson_path.relative_to(REPO_ROOT)),
            "csv": str(csv_path.relative_to(REPO_ROOT)),
        })
        time.sleep(0.5)

    manifest_path = args.out_dir / "emodnet_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  wrote {manifest_path}")


if __name__ == "__main__":
    main()
