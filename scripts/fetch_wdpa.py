"""Download Norwegian protected areas from the World Database on Protected Areas (WDPA).

Uses the Protected Planet API (free registration at https://www.protectedplanet.net/en/api).
Set WDPA_API_KEY in your environment before running.

Fetches all WDPA records for Norway (ISO3=NOR) as GeoJSON, then merges point
and polygon records into a single CSV for proximity analysis against inventory sites.

Outputs:
  - data/external/wdpa/wdpa_nor_polygons.geojson
  - data/external/wdpa/wdpa_nor_points.geojson
  - data/external/wdpa/wdpa_nor_combined.csv
  - data/external/wdpa/wdpa_manifest.json

Auth setup:
  1. Register at https://www.protectedplanet.net/en/api
  2. export WDPA_API_KEY=<your key>
  3. source .venv/bin/activate && python scripts/fetch_wdpa.py

Run:
  source .venv/bin/activate
  WDPA_API_KEY=your_key python scripts/fetch_wdpa.py
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "data" / "external" / "wdpa"

API_BASE = "https://api.protectedplanet.net/v3"
COUNTRY_ISO3 = "NOR"
SOURCE_NAME = "World Database on Protected Areas (WDPA)"
LICENSE = "WDPA — free for non-commercial research with attribution (IUCN / UNEP-WCMC)"


def get_api_key() -> str:
    key = os.environ.get("WDPA_API_KEY", "").strip()
    if not key:
        raise SystemExit(
            "WDPA_API_KEY not set.\n"
            "Register at https://www.protectedplanet.net/en/api then:\n"
            "  export WDPA_API_KEY=<your key>"
        )
    return key


def fetch_json(url: str, timeout: int = 120) -> dict:
    req = Request(url, headers={"User-Agent": "mia-capstone-research/1.0"})
    with urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        body = resp.read().decode(charset)
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Non-JSON response from {url}: {body[:400]}") from exc


def fetch_all_pages(api_key: str, geometry_type: str, pause_s: float = 0.5) -> list[dict]:
    """Fetch all WDPA records for Norway for a given geometry type (polygon or point)."""
    records: list[dict] = []
    page = 1
    while True:
        params = urlencode({
            "token": api_key,
            "country": COUNTRY_ISO3,
            "with_geometry": "true",
            "geometry_type": geometry_type,
            "page": page,
            "per_page": 50,
        })
        url = f"{API_BASE}/protected_areas?{params}"
        data = fetch_json(url)
        batch = data.get("protected_areas") or []
        if not batch:
            break
        records.extend(batch)
        print(f"  {geometry_type} page {page}: {len(batch)} records ({len(records)} total)")
        page += 1
        time.sleep(pause_s)
    return records


def record_to_geojson_feature(record: dict) -> dict:
    geom = record.get("geojson") or record.get("geometry") or None
    props = {k: v for k, v in record.items() if k not in ("geojson", "geometry")}
    return {"type": "Feature", "geometry": geom, "properties": props}


def record_to_csv_row(record: dict, geometry_type: str) -> dict:
    geom = record.get("geojson") or {}
    lon, lat = None, None
    if geom.get("type") == "Point":
        coords = geom.get("coordinates", [])
        if len(coords) >= 2:
            lon, lat = coords[0], coords[1]
    return {
        "wdpa_id": record.get("wdpa_id"),
        "name": record.get("name"),
        "iucn_category": record.get("iucn_category", {}).get("name") if isinstance(record.get("iucn_category"), dict) else record.get("iucn_category"),
        "designation": record.get("designation", {}).get("name") if isinstance(record.get("designation"), dict) else record.get("designation"),
        "designation_type": record.get("designation_type"),
        "marine": record.get("marine"),
        "status": record.get("status"),
        "status_year": record.get("status_year"),
        "reported_area": record.get("reported_area"),
        "management_authority": record.get("management_authority", {}).get("name") if isinstance(record.get("management_authority"), dict) else None,
        "geometry_type": geometry_type,
        "centroid_lon": lon,
        "centroid_lat": lat,
        "source_name": SOURCE_NAME,
    }


def write_geojson(path: Path, features: list[dict], meta: dict) -> None:
    collection = {"type": "FeatureCollection", "metadata": meta, "features": features}
    path.write_text(json.dumps(collection, ensure_ascii=False), encoding="utf-8")


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    api_key = get_api_key()

    all_rows: list[dict] = []
    manifest: dict = {
        "source_name": SOURCE_NAME,
        "country": COUNTRY_ISO3,
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
        "license": LICENSE,
        "datasets": [],
    }

    for gtype in ("polygon", "point"):
        print(f"Fetching WDPA {gtype} records for {COUNTRY_ISO3}...")
        records = fetch_all_pages(api_key, gtype)
        features = [record_to_geojson_feature(r) for r in records]
        rows = [record_to_csv_row(r, gtype) for r in records]
        all_rows.extend(rows)

        meta = {
            "source_name": SOURCE_NAME,
            "country": COUNTRY_ISO3,
            "geometry_type": gtype,
            "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
            "license": LICENSE,
        }
        geojson_path = args.out_dir / f"wdpa_nor_{gtype}s.geojson"
        write_geojson(geojson_path, features, meta)
        print(f"  wrote {geojson_path} ({len(features)} features)")
        manifest["datasets"].append({"geometry_type": gtype, "count": len(records), "geojson": str(geojson_path.relative_to(REPO_ROOT))})

    csv_path = args.out_dir / "wdpa_nor_combined.csv"
    write_csv(csv_path, all_rows)
    manifest["combined_csv"] = str(csv_path.relative_to(REPO_ROOT))
    manifest["total_records"] = len(all_rows)

    manifest_path = args.out_dir / "wdpa_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  wrote {csv_path} ({len(all_rows)} total records)")
    print(f"  wrote {manifest_path}")


if __name__ == "__main__":
    main()
