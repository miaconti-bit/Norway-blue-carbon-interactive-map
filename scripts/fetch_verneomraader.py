"""Download Norwegian protected areas (Verneområder) from Miljødirektoratet ArcGIS REST.

Fetches national parks, nature reserves, marine protected areas, and Ramsar sites.
Filters to marine/coastal categories relevant to the blue-carbon inventory.

Outputs:
  - data/external/verneomraader/verneomraader_all.geojson
  - data/external/verneomraader/verneomraader_features.csv
  - data/external/verneomraader/verneomraader_manifest.json

Run:
  source .venv/bin/activate
  python scripts/fetch_verneomraader.py
  python scripts/fetch_verneomraader.py --marine-only  # coastal/marine categories only
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
OUT_DIR = REPO_ROOT / "data" / "external" / "verneomraader"

SERVICE_URL = (
    "https://kart.miljodirektoratet.no/arcgis/rest/services/"
    "vern/MapServer"
)
LAYER_ID = 0  # Verneområder polygon layer

# majorEcosystemType values that indicate marine or coastal relevance
MARINE_ECOSYSTEM_TYPES = {"Marin", "MarinOgTerrestrisk"}

# verneform values for true MPAs (used for is_marine_relevant flag in CSV)
MARINE_VERNEFORM = {"MarintVerneomraade", "Nasjonalpark", "NasjonalparkSvalbard"}

LICENSE = "Norsk lisens for offentlege data (NLOD)"
SOURCE_NAME = "Miljødirektoratet Verneområder"


def fetch_json(url: str, params: dict, timeout: int = 120) -> dict:
    data = urlencode(params).encode("utf-8")
    req = Request(
        url,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        body = resp.read().decode(charset)
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Non-JSON response: {body[:400]}") from exc


def chunks(lst: list, size: int):
    for i in range(0, len(lst), size):
        yield lst[i : i + size]


def query_layer(layer_id: int, where: str = "1=1", chunk_size: int = 500, pause_s: float = 0.15) -> list[dict]:
    layer_url = f"{SERVICE_URL}/{layer_id}/query"
    id_resp = fetch_json(layer_url, {"f": "json", "where": where, "returnIdsOnly": "true"})
    if "error" in id_resp:
        raise RuntimeError(f"ID query failed: {id_resp['error']}")
    object_ids = sorted(int(v) for v in id_resp.get("objectIds") or [])
    if not object_ids:
        return []

    features: list[dict] = []
    for chunk in chunks(object_ids, chunk_size):
        payload = fetch_json(
            layer_url,
            {
                "f": "geojson",
                "objectIds": ",".join(str(v) for v in chunk),
                "outFields": "*",
                "returnGeometry": "true",
                "outSR": "4326",
            },
        )
        if "error" in payload:
            raise RuntimeError(f"Feature query failed: {payload['error']}")
        features.extend(payload.get("features", []))
        time.sleep(pause_s)
    return features


def geometry_centroid(geometry: dict | None) -> tuple[float | None, float | None]:
    if not geometry:
        return None, None
    coords: list[tuple[float, float]] = []

    def collect(v):
        if isinstance(v, (list, tuple)) and len(v) >= 2 and all(isinstance(x, (int, float)) for x in v[:2]):
            coords.append((float(v[0]), float(v[1])))
            return
        if isinstance(v, (list, tuple)):
            for item in v:
                collect(item)

    collect(geometry.get("coordinates"))
    if not coords:
        return None, None
    return sum(x for x, _ in coords) / len(coords), sum(y for _, y in coords) / len(coords)


def feature_to_row(feature: dict) -> dict:
    props = feature.get("properties") or {}
    lon, lat = geometry_centroid(feature.get("geometry"))
    verneform = props.get("verneform", "")
    ecosystem_type = props.get("majorEcosystemType", "")
    return {
        "objectid": props.get("OBJECTID"),
        "naturvernId": props.get("naturvernId"),
        "navn": props.get("navn"),
        "offisieltNavn": props.get("offisieltNavn"),
        "verneform": verneform,
        "majorEcosystemType": ecosystem_type,
        "iucn": props.get("iucn"),
        "vernedato_epoch_ms": props.get("vernedato"),
        "kommune": props.get("kommune"),
        "forvaltningsmyndighet": props.get("forvaltningsmyndighet"),
        "faktaark": props.get("faktaark"),
        "area_m2": props.get("SHAPE.STArea()"),
        "is_mpa": verneform == "MarintVerneomraade",
        "is_marine_relevant": ecosystem_type in MARINE_ECOSYSTEM_TYPES,
        "centroid_lon": lon,
        "centroid_lat": lat,
        "source_name": SOURCE_NAME,
        "license": LICENSE,
    }


def write_geojson(path: Path, features: list[dict]) -> None:
    collection = {
        "type": "FeatureCollection",
        "metadata": {
            "source_name": SOURCE_NAME,
            "service_url": SERVICE_URL,
            "layer_id": LAYER_ID,
            "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
            "license": LICENSE,
            "outSR": "EPSG:4326",
        },
        "features": features,
    }
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
    parser.add_argument(
        "--marine-only",
        action="store_true",
        help="Only download marine/coastal verneform categories (MAR, RAM, NP).",
    )
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--chunk-size", type=int, default=500)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    where = "1=1"
    if args.marine_only:
        types = ",".join(f"'{t}'" for t in sorted(MARINE_ECOSYSTEM_TYPES))
        where = f"majorEcosystemType IN ({types})"
        print(f"Filtering to marine ecosystem types: {where}")

    print(f"Querying layer {LAYER_ID} ({SOURCE_NAME})...")
    features = query_layer(LAYER_ID, where=where, chunk_size=args.chunk_size)
    print(f"  {len(features)} features retrieved")

    geojson_path = args.out_dir / "verneomraader_all.geojson"
    csv_path = args.out_dir / "verneomraader_features.csv"
    manifest_path = args.out_dir / "verneomraader_manifest.json"

    write_geojson(geojson_path, features)
    rows = [feature_to_row(f) for f in features]
    write_csv(csv_path, rows)

    marine_count = sum(1 for r in rows if r["is_marine_relevant"])
    mpa_count = sum(1 for r in rows if r["is_mpa"])
    manifest = {
        "source_name": SOURCE_NAME,
        "service_url": SERVICE_URL,
        "layer_id": LAYER_ID,
        "where_clause": where,
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
        "license": LICENSE,
        "feature_count": len(features),
        "marine_relevant_count": marine_count,
        "mpa_count": mpa_count,
        "outputs": {
            "geojson": str(geojson_path.relative_to(REPO_ROOT)),
            "csv": str(csv_path.relative_to(REPO_ROOT)),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"  {marine_count} marine/coastal features (Marin + MarinOgTerrestrisk)")
    print(f"  {mpa_count} true MPAs (MarintVerneomraade)")
    print(f"  wrote {geojson_path}")
    print(f"  wrote {csv_path}")
    print(f"  wrote {manifest_path}")


if __name__ == "__main__":
    main()
