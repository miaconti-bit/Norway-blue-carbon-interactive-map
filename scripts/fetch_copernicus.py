"""Download Norwegian shelf SST reanalysis from Copernicus Marine Service (CMEMS).

Downloads the NWSHELF_MULTIYEAR_PHY_004_009 product (NW European shelf reanalysis)
and computes a simple marine heatwave (MHW) frequency summary per canonical region.
MHW detection uses the Hobday et al. 2016 climatology approach: days exceeding the
90th-percentile threshold for a given calendar day.

Requires the copernicusmarine Python client and a free CMEMS account.

Auth setup:
  1. Register at https://marine.copernicus.eu/
  2. pip install copernicusmarine  (add to .venv if missing)
  3. copernicusmarine login  (stores credentials in ~/.copernicusmarine)

Outputs:
  - data/external/copernicus/nwshelf_sst_norway.nc     (raw NetCDF subset)
  - data/external/copernicus/mhw_summary_regional.csv  (MHW frequency per region/year)
  - data/external/copernicus/copernicus_manifest.json

Run:
  source .venv/bin/activate
  pip install copernicusmarine  # first time only — flag to CJ if missing
  copernicusmarine login         # first time only
  python scripts/fetch_copernicus.py
  python scripts/fetch_copernicus.py --start-year 2000 --end-year 2023
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "data" / "external" / "copernicus"

# Norwegian shelf bounding box
NORWAY_LON_MIN = 4.0
NORWAY_LON_MAX = 31.0
NORWAY_LAT_MIN = 57.0
NORWAY_LAT_MAX = 72.0

# CMEMS NW European shelf reanalysis — daily SST at surface
DATASET_ID = "cmems_mod_nws_phy-t_my_7km-2D_P1D-m"
VARIABLE = "thetao"

SOURCE_NAME = "Copernicus Marine Service — NW European Shelf Reanalysis"
LICENSE = "Copernicus Marine Service — free for any purpose with attribution"


def check_imports() -> None:
    missing = []
    try:
        import copernicusmarine  # noqa: F401
    except ImportError:
        missing.append("copernicusmarine")
    try:
        import xarray  # noqa: F401
    except ImportError:
        missing.append("xarray")
    try:
        import numpy  # noqa: F401
    except ImportError:
        missing.append("numpy")
    if missing:
        raise SystemExit(
            f"Missing packages: {', '.join(missing)}\n"
            "Install with: pip install " + " ".join(missing) + "\n"
            "(Flag to CJ if adding to .venv is needed.)"
        )


def download_sst(out_path: Path, start_year: int, end_year: int) -> None:
    import copernicusmarine

    print(f"Downloading SST {start_year}–{end_year} from CMEMS ({DATASET_ID})...")
    copernicusmarine.subset(
        dataset_id=DATASET_ID,
        variables=[VARIABLE],
        minimum_longitude=NORWAY_LON_MIN,
        maximum_longitude=NORWAY_LON_MAX,
        minimum_latitude=NORWAY_LAT_MIN,
        maximum_latitude=NORWAY_LAT_MAX,
        start_datetime=f"{start_year}-01-01T00:00:00",
        end_datetime=f"{end_year}-12-31T00:00:00",
        minimum_depth=0,
        maximum_depth=1,
        output_filename=str(out_path),
        force_download=True,
    )
    print(f"  wrote {out_path}")


def compute_mhw_summary(nc_path: Path, out_csv: Path) -> None:
    """Compute annual MHW frequency (days above 90th-percentile climatology) per grid cell,
    then average over four canonical Norwegian regions."""
    import numpy as np
    import xarray as xr
    import csv

    print("Computing MHW frequency...")
    ds = xr.open_dataset(nc_path)
    sst = ds[VARIABLE].squeeze()  # drop depth dim if present

    # Climatological 90th percentile per calendar day-of-year
    clim_p90 = sst.groupby("time.dayofyear").quantile(0.90, dim="time")
    anom = sst.groupby("time.dayofyear") - clim_p90
    mhw_mask = anom > 0  # days exceeding local 90th percentile

    # Annual MHW frequency (fraction of days)
    annual_freq = mhw_mask.groupby("time.year").mean(dim="time")

    # Canonical region bounding boxes [lon_min, lat_min, lon_max, lat_max]
    regions = {
        "Barents Sea": (14.0, 69.0, 31.0, 72.0),
        "Norwegian Sea": (4.0, 62.0, 14.0, 69.0),
        "Oslofjord": (10.0, 59.0, 11.5, 60.0),
        "Skagerrak": (7.5, 57.0, 11.0, 59.0),
    }

    rows = []
    lon = annual_freq.longitude if "longitude" in annual_freq.coords else annual_freq.lon
    lat = annual_freq.latitude if "latitude" in annual_freq.coords else annual_freq.lat

    for year in annual_freq.year.values:
        yr_slice = annual_freq.sel(year=year)
        for region, (lon_min, lat_min, lon_max, lat_max) in regions.items():
            subset = yr_slice.where(
                (lon >= lon_min) & (lon <= lon_max) &
                (lat >= lat_min) & (lat <= lat_max),
                drop=True,
            )
            if subset.size == 0:
                continue
            rows.append({
                "year": int(year),
                "region": region,
                "mhw_freq_mean": float(np.nanmean(subset.values)),
                "mhw_freq_max": float(np.nanmax(subset.values)),
                "mhw_freq_min": float(np.nanmin(subset.values)),
                "n_grid_cells": int(np.sum(~np.isnan(subset.values))),
            })

    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"  wrote {out_csv} ({len(rows)} region-year rows)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year", type=int, default=1993)
    parser.add_argument("--end-year", type=int, default=2022)
    parser.add_argument("--skip-download", action="store_true", help="Skip download; reprocess existing NC file.")
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    check_imports()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    nc_path = args.out_dir / "nwshelf_sst_norway.nc"
    csv_path = args.out_dir / "mhw_summary_regional.csv"
    manifest_path = args.out_dir / "copernicus_manifest.json"

    if not args.skip_download:
        download_sst(nc_path, args.start_year, args.end_year)
    elif not nc_path.exists():
        raise SystemExit(f"--skip-download set but {nc_path} does not exist.")

    compute_mhw_summary(nc_path, csv_path)

    manifest = {
        "source_name": SOURCE_NAME,
        "dataset_id": DATASET_ID,
        "variable": VARIABLE,
        "start_year": args.start_year,
        "end_year": args.end_year,
        "bbox": [NORWAY_LON_MIN, NORWAY_LAT_MIN, NORWAY_LON_MAX, NORWAY_LAT_MAX],
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
        "license": LICENSE,
        "mhw_method": "Hobday et al. 2016 — days exceeding 90th-percentile climatology per calendar day",
        "outputs": {
            "netcdf": str(nc_path.relative_to(REPO_ROOT)),
            "mhw_summary_csv": str(csv_path.relative_to(REPO_ROOT)),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  wrote {manifest_path}")


if __name__ == "__main__":
    main()
