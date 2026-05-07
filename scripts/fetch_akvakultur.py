"""Download the Norwegian Aquaculture Register (Akvakulturregisteret) from Fiskeridirektoratet.

Downloads the full open-data CSV of active aquaculture facilities with coordinates.
Filters to marine cage sites (laks, ørret, regnbueørret, torsk) relevant as
nutrient-loading and physical-disturbance pressure proxies near inventory sites.

Outputs:
  - data/external/akvakultur/akvakulturregisteret_raw.csv
  - data/external/akvakultur/akvakultur_marine_sites.csv
  - data/external/akvakultur/akvakultur_manifest.json

Run:
  source .venv/bin/activate
  python scripts/fetch_akvakultur.py
  python scripts/fetch_akvakultur.py --all-types  # skip marine-cage filter
"""

from __future__ import annotations

import argparse
import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen, Request

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "data" / "external" / "akvakultur"

# Fiskeridirektoratet public API — daily dump, semicolon-delimited, UTF-8
# Row 1 is a metadata header; row 2 is the column header; data from row 3.
DOWNLOAD_URL = "https://api.fiskeridir.no/pub-aqua/api/v1/dump/new-legacy-csv-file"
SOURCE_NAME = "Fiskeridirektoratet Akvakulturregisteret"
LICENSE = "Norsk lisens for offentlege data (NLOD)"

# Art (species) codes for marine finfish cage aquaculture
MARINE_CAGE_ART = {
    "Laks",
    "Ørret",
    "Regnbueørret",
    "Torsk",
    "Kveite",
    "Sei",
}

# Tillatelsestype codes that correspond to active marine cage sites
MARINE_TILLATELSE = {
    "MATFISK_LAKS",
    "MATFISK_REGNBUEORRET",
    "SETTEFISK",
    "SLAKTEMERD",
}


def fetch_csv(url: str, timeout: int = 120) -> list[dict]:
    req = Request(url, headers={"User-Agent": "mia-capstone-research/1.0"})
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    # Row 1 is a metadata banner; skip it so DictReader picks up row 2 as header
    text = raw.decode("utf-8-sig")
    lines = text.splitlines(keepends=True)
    data_text = "".join(lines[1:])  # drop the metadata row
    reader = csv.DictReader(io.StringIO(data_text), delimiter=";")
    return list(reader)


def is_marine_cage(row: dict) -> bool:
    # VANNMILJØ = "Saltvann" identifies marine sites; ART is species
    vannmiljo = row.get("VANNMILJØ", "") or ""
    art = row.get("ART", "") or ""
    return "saltvann" in vannmiljo.lower() and any(s.lower() in art.lower() for s in MARINE_CAGE_ART)


def clean_coord(val: str | None) -> float | None:
    if not val:
        return None
    val = val.replace(",", ".").strip()
    try:
        return float(val)
    except ValueError:
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
        "--all-types",
        action="store_true",
        help="Write all facility types, not just marine cage species.",
    )
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Downloading {SOURCE_NAME}...")
    rows = fetch_csv(DOWNLOAD_URL)
    print(f"  {len(rows)} total records")

    raw_path = args.out_dir / "akvakulturregisteret_raw.csv"
    write_csv(raw_path, rows)
    print(f"  wrote {raw_path}")

    if not args.all_types:
        filtered = [r for r in rows if is_marine_cage(r)]
    else:
        filtered = rows

    # Coordinate columns are N_GEOWGS84 (lat) and Ø_GEOWGS84 (lon)
    for row in filtered:
        row["lat_dd"] = clean_coord(row.get("N_GEOWGS84"))
        row["lon_dd"] = clean_coord(row.get("Ø_GEOWGS84"))

    marine_path = args.out_dir / "akvakultur_marine_sites.csv"
    write_csv(marine_path, filtered)
    print(f"  {len(filtered)} marine cage records → {marine_path}")

    manifest = {
        "source_name": SOURCE_NAME,
        "download_url": DOWNLOAD_URL,
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
        "license": LICENSE,
        "total_records": len(rows),
        "marine_cage_records": len(filtered),
        "outputs": {
            "raw_csv": str(raw_path.relative_to(REPO_ROOT)),
            "marine_csv": str(marine_path.relative_to(REPO_ROOT)),
        },
        "note": "Coordinate columns normalized from comma to period decimal; lat_dd/lon_dd added.",
    }
    manifest_path = args.out_dir / "akvakultur_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  wrote {manifest_path}")


if __name__ == "__main__":
    main()
