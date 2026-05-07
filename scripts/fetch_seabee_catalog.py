"""Catalog SeaBee GeoNode datasets relevant to Norwegian blue carbon ecosystems.

Paginates the SeaBee GeoNode API and filters datasets whose titles or abstracts
mention seagrass, eelgrass, kelp, macroalgae, or coastal habitat terms.
Downloads vector dataset GeoJSON where public download links are available.
Raster datasets (orthophotos, DEMs) are cataloged only — they are too large
for bulk download and require case-by-case selection.

Outputs:
  - data/external/seabee/seabee_full_catalog.csv       (all datasets, metadata only)
  - data/external/seabee/seabee_relevant_catalog.csv   (filtered to blue-carbon terms)
  - data/external/seabee/<name>.geojson                (vector datasets where available)
  - data/external/seabee/seabee_manifest.json

Run:
  source .venv/bin/activate
  python scripts/fetch_seabee_catalog.py
  python scripts/fetch_seabee_catalog.py --download-vectors  # also fetch GeoJSON for vectors
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
import urllib.error

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "data" / "external" / "seabee"

API_BASE = "https://geonode.seabee.sigma2.no/api/v2"
PAGE_SIZE = 100
SOURCE_NAME = "SeaBee GeoNode"
LICENSE = "SeaBee — check individual dataset licenses"

# Title/abstract terms that indicate blue-carbon relevance
RELEVANT_TERMS = {
    "seagrass", "eelgrass", "ålegras", "ålegraseng",
    "kelp", "tare", "macroalgae", "makroalge",
    "zostera", "saccharina", "laminaria",
}


def fetch_page(offset: int, limit: int = PAGE_SIZE, timeout: int = 30) -> dict:
    params = urlencode({"limit": limit, "offset": offset})
    url = f"{API_BASE}/datasets/?{params}"
    req = Request(url, headers={"User-Agent": "mia-capstone-research/1.0"})
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def fetch_all_datasets(pause_s: float = 0.2) -> list[dict]:
    datasets: list[dict] = []
    offset = 0
    total = None
    while True:
        page = fetch_page(offset)
        if total is None:
            total = page.get("total", 0)
            print(f"  Total datasets: {total}")
        batch = page.get("datasets", [])
        if not batch:
            break
        datasets.extend(batch)
        print(f"  Fetched {len(datasets)}/{total}", end="\r")
        offset += len(batch)
        if offset >= total:
            break
        time.sleep(pause_s)
    print()
    return datasets


def is_relevant(dataset: dict) -> bool:
    text = " ".join([
        dataset.get("title", ""),
        dataset.get("abstract", ""),
        " ".join(dataset.get("keywords", []) or []),
    ]).lower()
    return any(term in text for term in RELEVANT_TERMS)


def dataset_to_row(d: dict) -> dict:
    bbox = d.get("bbox_polygon", {}).get("coordinates", [[[]]])[0]
    lons = [c[0] for c in bbox if len(c) >= 2]
    lats = [c[1] for c in bbox if len(c) >= 2]
    return {
        "pk": d.get("pk"),
        "title": d.get("title"),
        "subtype": d.get("subtype"),
        "abstract": (d.get("abstract") or "")[:300],
        "keywords": "; ".join(d.get("keywords") or []),
        "date": d.get("date"),
        "owner": d.get("owner", {}).get("username") if isinstance(d.get("owner"), dict) else d.get("owner"),
        "bbox_lon_min": min(lons) if lons else None,
        "bbox_lat_min": min(lats) if lats else None,
        "bbox_lon_max": max(lons) if lons else None,
        "bbox_lat_max": max(lats) if lats else None,
        "detail_url": d.get("detail_url"),
        "download_url": d.get("download_url"),
        "ows_url": d.get("ows_url"),
    }


def fetch_vector_geojson(dataset: dict, out_dir: Path) -> str | None:
    download_url = dataset.get("download_url")
    if not download_url or dataset.get("subtype") == "raster":
        return None
    slug = dataset.get("title", "unknown")[:60].replace("/", "_").replace(" ", "_")
    out_path = out_dir / f"{slug}.geojson"
    if out_path.exists():
        return str(out_path.relative_to(REPO_ROOT))
    try:
        # GeoNode vector export: append /wfs endpoint or use download link
        wfs_url = f"{API_BASE}/datasets/{dataset.get('pk')}/geojson"
        req = Request(wfs_url, headers={"User-Agent": "mia-capstone-research/1.0"})
        with urlopen(req, timeout=60) as resp:
            body = resp.read()
        out_path.write_bytes(body)
        return str(out_path.relative_to(REPO_ROOT))
    except urllib.error.HTTPError as e:
        print(f"    Could not download {slug}: HTTP {e.code}")
        return None
    except Exception as e:
        print(f"    Could not download {slug}: {e}")
        return None


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
        "--download-vectors",
        action="store_true",
        help="Also attempt to download GeoJSON for relevant vector datasets.",
    )
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    print("Fetching SeaBee GeoNode catalog...")
    datasets = fetch_all_datasets()

    all_rows = [dataset_to_row(d) for d in datasets]
    relevant = [d for d in datasets if is_relevant(d)]
    relevant_rows = [dataset_to_row(d) for d in relevant]

    full_csv = args.out_dir / "seabee_full_catalog.csv"
    rel_csv = args.out_dir / "seabee_relevant_catalog.csv"
    write_csv(full_csv, all_rows)
    write_csv(rel_csv, relevant_rows)
    print(f"  {len(datasets)} total datasets → {full_csv}")
    print(f"  {len(relevant)} relevant datasets → {rel_csv}")

    downloaded: list[dict] = []
    if args.download_vectors:
        vectors = [d for d in relevant if d.get("subtype") == "vector"]
        print(f"  Attempting vector download for {len(vectors)} relevant vector datasets...")
        for d in vectors:
            path = fetch_vector_geojson(d, args.out_dir)
            if path:
                downloaded.append({"title": d.get("title"), "path": path})
                time.sleep(0.3)

    manifest = {
        "source_name": SOURCE_NAME,
        "api_base": API_BASE,
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
        "license": LICENSE,
        "total_datasets": len(datasets),
        "relevant_datasets": len(relevant),
        "relevant_terms": sorted(RELEVANT_TERMS),
        "downloaded_vectors": downloaded,
        "outputs": {
            "full_catalog": str(full_csv.relative_to(REPO_ROOT)),
            "relevant_catalog": str(rel_csv.relative_to(REPO_ROOT)),
        },
        "note": (
            "SeaBee GeoNode search param does not filter server-side; "
            "relevance filtering applied client-side on title/abstract/keywords. "
            "Raster datasets (drone orthophotos) are cataloged only."
        ),
    }
    manifest_path = args.out_dir / "seabee_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  wrote {manifest_path}")


if __name__ == "__main__":
    main()
