"""Unit tests for mia_map.parsers.

These functions are pure and deterministic — they're the cheapest part of
the pipeline to test, and they catch the kind of upstream-data drift
(unicode quote variants, free-text year columns, malformed WKT) that
would otherwise silently corrupt downstream maps.
"""

from __future__ import annotations

import math

import pytest

from mia_map.parsers import dms_to_dd, extract_year, first_number, parse_point_wkt


class TestDmsToDd:
    def test_returns_none_for_missing(self):
        assert dms_to_dd(None) is None
        assert dms_to_dd(float("nan")) is None
        assert dms_to_dd("") is None
        assert dms_to_dd("not a coordinate") is None

    def test_north_hemisphere(self):
        # 58° 24' 14.6" N == 58.4040555... ≈ 58.404056
        assert dms_to_dd("58° 24' 14.6\" N") == pytest.approx(58.404056, abs=1e-5)

    def test_south_hemisphere_is_negative(self):
        assert dms_to_dd("33° 30' 0\" S") == pytest.approx(-33.5, abs=1e-5)

    def test_handles_unicode_prime_quotes(self):
        # The kelp workbook uses the prime / double-prime forms ′ ″
        a = dms_to_dd("58° 24′ 14.6″ N")
        b = dms_to_dd("58° 24' 14.6\" N")
        assert a == pytest.approx(b, abs=1e-6)

    def test_handles_typewriter_double_apostrophe(self):
        # '' is sometimes used in place of " for seconds
        a = dms_to_dd("58° 24' 14.6'' N")
        b = dms_to_dd("58° 24' 14.6\" N")
        assert a == pytest.approx(b, abs=1e-6)

    def test_decimal_minutes_only(self):
        # When seconds are omitted, parser should still work
        result = dms_to_dd("58° 24.243' N")
        assert result == pytest.approx(58 + 24.243 / 60, abs=1e-5)


class TestExtractYear:
    def test_finds_year_in_free_text(self):
        assert extract_year("Sampled in 2023") == 2023
        assert extract_year("Gagnon et al. 2024") == 2024
        assert extract_year("1998-2001 survey") == 1998  # picks the first

    def test_returns_none_for_no_year(self):
        assert extract_year("no date here") is None
        assert extract_year("") is None
        assert extract_year(None) is None
        assert extract_year(float("nan")) is None

    def test_only_19xx_or_20xx(self):
        # 1899 should not match (not 19xx); 2000–2099 should match
        assert extract_year("year 1899") is None
        assert extract_year("year 1900") == 1900
        assert extract_year("year 2099") == 2099


class TestParsePointWkt:
    def test_parses_simple_point(self):
        lat, lon = parse_point_wkt("POINT (10.5 60.2)")
        assert lat == 60.2
        assert lon == 10.5

    def test_parses_negative(self):
        lat, lon = parse_point_wkt("POINT (-3.2 56.1)")
        assert lat == 56.1
        assert lon == -3.2

    def test_returns_nan_for_missing(self):
        for bad in (None, "", "not a point", "POLYGON ((...))"):
            lat, lon = parse_point_wkt(bad)
            assert math.isnan(lat)
            assert math.isnan(lon)


class TestFirstNumber:
    def test_extracts_simple_number(self):
        assert first_number("30") == 30.0
        assert first_number("30.5") == 30.5

    def test_handles_approximations(self):
        assert first_number("~30") == 30.0
        assert first_number("4000*") == 4000.0
        assert first_number("5–10 m") == 5.0  # picks the first number

    def test_negative(self):
        assert first_number("-12.3 m") == -12.3

    def test_returns_none_for_no_number(self):
        assert first_number("no numbers here") is None
        assert first_number(None) is None
        assert first_number("") is None
        assert first_number(float("nan")) is None
