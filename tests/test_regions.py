"""Unit tests for the canonical region scheme.

The function is shared by build_norway_map.py and
spatial_colocation_analysis.py — these tests pin down the contract so
the two consumers can never silently drift again.
"""

from __future__ import annotations

import math

from regions import (
    CANONICAL_REGION_COLORS,
    CANONICAL_REGIONS,
    REGION_CENTROIDS,
    canonical_region,
)


class TestRegionsConfig:
    def test_canonical_regions_in_expected_order(self):
        assert CANONICAL_REGIONS == [
            "Barents Sea",
            "Norwegian Sea",
            "Oslofjord",
            "Skagerrak",
        ]

    def test_every_region_has_a_color(self):
        for r in CANONICAL_REGIONS:
            assert r in CANONICAL_REGION_COLORS
            assert CANONICAL_REGION_COLORS[r].startswith("#")

    def test_every_region_has_a_centroid(self):
        for r in CANONICAL_REGIONS:
            assert r in REGION_CENTROIDS
            lat, lon = REGION_CENTROIDS[r]
            assert 56.0 <= lat <= 82.0  # plausibly inside Norwegian waters
            assert -5.0 <= lon <= 35.0


class TestRegionLabelMatching:
    def test_barents_keywords(self):
        assert canonical_region("Barents Sea coast", None) == "Barents Sea"
        assert canonical_region("Porsanger fjord", None) == "Barents Sea"
        assert canonical_region("Hammerfest", None) == "Barents Sea"
        assert canonical_region("Northern Norway", None) == "Barents Sea"
        assert canonical_region("Bodø", None) == "Barents Sea"

    def test_norwegian_sea_keywords(self):
        assert canonical_region("Norwegian Sea", None) == "Norwegian Sea"
        assert canonical_region("Hardangerfjord", None) == "Norwegian Sea"
        assert canonical_region("Sognefjord", None) == "Norwegian Sea"
        assert canonical_region("Mid-Norway", None) == "Norwegian Sea"
        assert canonical_region("North Sea", None) == "Norwegian Sea"

    def test_skagerrak_keywords(self):
        assert canonical_region("Skagerrak", None) == "Skagerrak"
        assert canonical_region("Outer Oslofjord", None) == "Skagerrak"

    def test_oslofjord_distinct_from_outer(self):
        assert canonical_region("Oslofjord", None) == "Oslofjord"
        assert canonical_region("Inner Oslofjord", None) == "Oslofjord"
        # 'Outer Oslofjord' is treated as Skagerrak per the roadmap scheme
        assert canonical_region("Outer Oslofjord", None) == "Skagerrak"


class TestRegionLatitudeFallback:
    def test_lat_above_67_is_barents(self):
        assert canonical_region(None, 70.0) == "Barents Sea"
        assert canonical_region(None, 67.0) == "Barents Sea"

    def test_lat_60_to_67_is_norwegian_sea(self):
        assert canonical_region(None, 65.0) == "Norwegian Sea"
        assert canonical_region(None, 60.0) == "Norwegian Sea"

    def test_lat_below_60_is_skagerrak(self):
        assert canonical_region(None, 58.0) == "Skagerrak"

    def test_unknown_when_no_label_no_lat(self):
        assert canonical_region(None, None) == "Unknown"

    def test_unknown_when_label_unrecognised_and_lat_is_nan(self):
        # Regression guard: the previous build_norway_map.py copy of this
        # function only checked `lat is None` and would crash or misclassify
        # on NaN. The unified version handles both.
        assert canonical_region("definitely not a known region", float("nan")) == "Unknown"
        assert canonical_region(None, math.nan) == "Unknown"

    def test_label_takes_precedence_over_lat(self):
        # Hardanger is at ~60°N geographically; if both label and lat say
        # 'Skagerrak', the label wins.
        assert canonical_region("Hardanger", 58.0) == "Norwegian Sea"
