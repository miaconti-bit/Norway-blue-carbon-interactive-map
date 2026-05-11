"""Canonical Norwegian blue-carbon regions and helpers.

Single source of truth for the four-region scheme used across the project
(Gagnon et al. 2024 / roadmap). Imported by build_norway_map.py and
spatial_colocation_analysis.py — keep classifications consistent by editing
this file, not the call sites.
"""

from __future__ import annotations

import pandas as pd


CANONICAL_REGIONS = ["Barents Sea", "Norwegian Sea", "Oslofjord", "Skagerrak"]

CANONICAL_REGION_COLORS = {
    "Barents Sea":   "#2c7fb8",
    "Norwegian Sea": "#1b9e77",
    "Oslofjord":     "#d95f02",
    "Skagerrak":     "#e7298a",
}

# Approximate geographic centres of each canonical region, placed in open water
# to avoid overlap with site markers when used for region-level bubbles.
REGION_CENTROIDS = {
    "Barents Sea":   (71.0, 27.0),
    "Norwegian Sea": (64.5,  7.5),
    "Oslofjord":     (59.5, 10.6),
    "Skagerrak":     (58.1,  7.8),
}


def canonical_region(region_str: str | None, lat: float | None) -> str:
    """Map a free-text region label and/or latitude onto one of the four
    canonical Norwegian blue-carbon regions.

    Falls back to a latitude-based assignment when the label is missing or
    unrecognised. Returns "Unknown" only when both the label and the latitude
    are unusable.
    """
    s = (region_str or "").lower()
    if any(k in s for k in ("barents", "porsanger", "hammerfest", "northern norway", "bodø")):
        return "Barents Sea"
    if "norwegian sea" in s:
        return "Norwegian Sea"
    if "outer oslofjord" in s or "skagerrak" in s:
        return "Skagerrak"
    if "oslofjord" in s:
        return "Oslofjord"
    if any(k in s for k in (
        "hardanger", "sognef", "mid-norway", "north sea", "southwest norway", "west norway"
    )):
        return "Norwegian Sea"
    if lat is None or pd.isna(lat):
        return "Unknown"
    if lat >= 67:
        return "Barents Sea"
    if lat >= 60:
        return "Norwegian Sea"
    return "Skagerrak"
