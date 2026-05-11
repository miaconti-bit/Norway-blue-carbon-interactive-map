"""Pure parsing helpers used when loading site/coordinate data.

Kept free of folium/geopandas imports so they are cheap to unit-test.
"""

from __future__ import annotations

import re
import unicodedata

import pandas as pd


def dms_to_dd(value) -> float | None:
    """Parse a degrees/minutes/seconds string with a hemisphere letter into
    decimal degrees.

    Handles the unicode quote variants (’ ’ ″ etc.) used in the macroalgae
    workbook. Returns None for missing values or strings that don't match
    the expected DMS pattern.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = unicodedata.normalize("NFKC", str(value)).strip()
    s = (
        s.replace("’", "'").replace("‘", "'")
        .replace("”", '"').replace("“", '"')
        .replace("′", "'").replace("″", '"')
    )
    s = s.replace("''", '"')
    m = re.search(
        r"([0-9]+(?:\.[0-9]+)?)°\s*([0-9]+(?:\.[0-9]+)?)?'?\s*([0-9]+(?:\.[0-9]+)?)?\"?\s*([NSEW])",
        s,
    )
    if not m:
        return None
    deg = float(m.group(1))
    minutes = float(m.group(2) or 0)
    seconds = float(m.group(3) or 0)
    hemi = m.group(4)
    dd = deg + minutes / 60 + seconds / 3600
    return -dd if hemi in ("S", "W") else round(dd, 6)


def extract_year(value) -> int | None:
    """Pull the first 4-digit year (19xx or 20xx) out of a free-text cell."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    m = re.search(r"(19|20)\d{2}", str(value))
    return int(m.group(0)) if m else None


def parse_point_wkt(geom_str) -> tuple[float, float]:
    """Extract (lat, lon) from a WKT POINT string like 'POINT (lon lat)'.

    Returns (NaN, NaN) for missing or malformed values; callers that care
    can check via math.isnan or pandas.isna.
    """
    if not geom_str or not isinstance(geom_str, str):
        return (float("nan"), float("nan"))
    m = re.match(r"POINT\s*\(\s*([-\d.]+)\s+([-\d.]+)\s*\)", geom_str.strip())
    if not m:
        return (float("nan"), float("nan"))
    return float(m.group(2)), float(m.group(1))  # lat = y, lon = x


def first_number(value) -> float | None:
    """Return the first numeric token in a free-text cell.

    Handles values like '~30', '4000*', '5–10 m'. Returns None if no
    numeric token is found.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    m = re.search(r"[-+]?\d+(?:\.\d+)?", str(value))
    return float(m.group(0)) if m else None
