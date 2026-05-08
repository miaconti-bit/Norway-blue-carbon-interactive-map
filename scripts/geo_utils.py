"""Small geometry helpers shared across the map-building scripts."""

from __future__ import annotations

import pandas as pd


# Bounding box for Norwegian waters (mainland + Svalbard + EEZ).
NORWAY_BBOX = {"lat_min": 56.5, "lat_max": 82.0, "lon_min": -5.0, "lon_max": 35.0}


def clip_to_bbox(
    df: pd.DataFrame,
    lat_col: str,
    lon_col: str,
    bbox: dict | None,
) -> pd.DataFrame:
    """Return rows of df whose lat/lon fall inside the given bbox.

    bbox dict keys: lat_min, lat_max, lon_min, lon_max. If bbox is None the
    DataFrame is returned unchanged. Returns a copy so callers can safely
    mutate the result.
    """
    if bbox is None:
        return df
    return df[
        (df[lat_col] >= bbox["lat_min"]) & (df[lat_col] <= bbox["lat_max"]) &
        (df[lon_col] >= bbox["lon_min"]) & (df[lon_col] <= bbox["lon_max"])
    ].copy()
