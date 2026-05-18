"""Download and process ERS catch reports (DCA) from Fiskeridir.

Downloads DCA (Detaljert Fangst og aktivitetsmelding) data for Norwegian
fishing vessels and aggregates fishing effort (kW × hours) on a 0.05° grid
covering Norwegian waters.

Replaces the EMODnet ICES-grid trawl layers, which cover the broader North Sea
rather than Norwegian coastal waters.

Outputs:
  data/external/ers/ers_fishing_effort.csv   (lat, lon, effort_kwh, haul_count)
  data/external/ers/ers_manifest.json

Run:
  python scripts/fetch_ers_fishing.py
  python scripts/fetch_ers_fishing.py --years 2019 2020 2021 2022 2023
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "data" / "external" / "ers"

BASE_URL = "https://register.fiskeridir.no/vms-ers/ERS"
DEFAULT_YEARS = list(range(2019, 2024))

# Match build_norway_map.py's NORWAY_BBOX
BBOX_LON_MIN, BBOX_LAT_MIN, BBOX_LON_MAX, BBOX_LAT_MAX = -5.0, 56.5, 35.0, 82.0
GRID_RES = 0.05

LICENSE = "Norwegian Directorate of Fisheries (Fiskeridir) — Norwegian Open Data License (NLOD)"
SOURCE_NAME = "Fiskeridir Electronic Reporting System (ERS) — DCA catch messages"


def _parse_no_float(s: str) -> float | None:
    """Parse Norwegian decimal string (comma separator) to float."""
    try:
        return float(s.strip().replace(",", "."))
    except (ValueError, AttributeError):
        return None


def download_dca(year: int, timeout: int = 180) -> list[dict]:
    """Download and parse DCA (catch report) records for one year."""
    url = f"{BASE_URL}/elektronisk-rapportering-ers-{year}.zip"
    print(f"  fetching {year}... ", end="", flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "mia-capstone-research/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    print(f"{len(data) / 1e6:.1f} MB")

    zf = zipfile.ZipFile(io.BytesIO(data))
    dca_name = next(n for n in zf.namelist() if "fangstmelding-dca" in n)
    with zf.open(dca_name) as f:
        content = f.read().decode("utf-8-sig", errors="replace")

    return list(csv.DictReader(io.StringIO(content), delimiter=";"))


def deduplicate_hauls(rows: list[dict]) -> list[dict]:
    """Keep only active-fishing (FIS) rows, one row per unique haul.

    Each haul appears once per species in the catch; we keep only the first
    occurrence so effort is not double-counted.
    """
    seen: set = set()
    hauls = []
    for r in rows:
        if r.get("Aktivitet (kode)", "").strip() != "FIS":
            continue
        msg_id = r.get("Melding ID", "").strip()
        if msg_id:
            key = msg_id
        else:
            key = (
                r.get("Radiokallesignal (ERS)", ""),
                r.get("Meldingsnummer", ""),
                r.get("Meldingsversjon", ""),
                r.get("Startdato", ""),
                r.get("Startklokkeslett", ""),
            )
        if key not in seen:
            seen.add(key)
            hauls.append(r)
    return hauls


def grid_effort(hauls: list[dict]) -> list[dict]:
    """Aggregate haul effort (kW × hours) onto a regular 0.05° grid."""
    cells: dict[tuple, dict] = {}
    skipped = 0

    for row in hauls:
        lat = _parse_no_float(row.get("Startposisjon bredde", ""))
        lon = _parse_no_float(row.get("Startposisjon lengde", ""))
        if lat is None or lon is None:
            skipped += 1
            continue
        if not (BBOX_LAT_MIN <= lat <= BBOX_LAT_MAX and BBOX_LON_MIN <= lon <= BBOX_LON_MAX):
            skipped += 1
            continue

        kw = _parse_no_float(row.get("Motorkraft", "")) or 0.0
        dur_min = _parse_no_float(row.get("Varighet", "")) or 0.0
        effort = kw * (dur_min / 60.0)  # kW × hours

        cell_lat = round(round(lat / GRID_RES) * GRID_RES, 6)
        cell_lon = round(round(lon / GRID_RES) * GRID_RES, 6)

        key = (cell_lat, cell_lon)
        if key not in cells:
            cells[key] = {"lat": cell_lat, "lon": cell_lon, "effort_kwh": 0.0, "haul_count": 0}
        cells[key]["effort_kwh"] += effort
        cells[key]["haul_count"] += 1

    if skipped:
        print(f"    skipped {skipped:,} hauls (no coordinates or outside bbox)")
    return sorted(cells.values(), key=lambda r: -r["effort_kwh"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", nargs="+", type=int, default=DEFAULT_YEARS,
                        help="Years to include (default: 2019-2023)")
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    all_hauls: list[dict] = []
    for year in sorted(args.years):
        try:
            rows = download_dca(year)
            hauls = deduplicate_hauls(rows)
            print(f"    {len(hauls):,} unique fishing hauls")
            all_hauls.extend(hauls)
        except Exception as exc:
            print(f"  ERROR for {year}: {exc}")

    if not all_hauls:
        raise SystemExit("No hauls loaded — aborting.")

    print(f"\nGridding {len(all_hauls):,} hauls at {GRID_RES}° resolution...")
    cells = grid_effort(all_hauls)
    print(f"  {len(cells):,} grid cells with effort")

    out_csv = args.out_dir / "ers_fishing_effort.csv"
    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["lat", "lon", "effort_kwh", "haul_count"])
        writer.writeheader()
        writer.writerows(cells)
    print(f"  saved: {out_csv}")

    manifest = {
        "source_name": SOURCE_NAME,
        "years": sorted(args.years),
        "grid_resolution_deg": GRID_RES,
        "bbox": [BBOX_LON_MIN, BBOX_LAT_MIN, BBOX_LON_MAX, BBOX_LAT_MAX],
        "n_hauls": len(all_hauls),
        "n_grid_cells": len(cells),
        "license": LICENSE,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    manifest_path = args.out_dir / "ers_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  manifest: {manifest_path}")


if __name__ == "__main__":
    main()
