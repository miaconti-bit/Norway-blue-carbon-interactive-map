"""Unit tests for geo_utils.clip_to_bbox."""

from __future__ import annotations

import pandas as pd
import pytest

from geo_utils import NORWAY_BBOX, clip_to_bbox


@pytest.fixture
def sample_df():
    return pd.DataFrame(
        {
            "lat": [60.0, 70.0, 50.0, 75.0, 56.6],
            "lon": [10.0, 25.0, 20.0, -10.0, 5.0],
            "label": ["a", "b", "south", "west", "edge"],
        }
    )


def test_returns_input_unchanged_when_bbox_is_none(sample_df):
    out = clip_to_bbox(sample_df, "lat", "lon", None)
    assert len(out) == len(sample_df)


def test_drops_rows_outside_norway_bbox(sample_df):
    out = clip_to_bbox(sample_df, "lat", "lon", NORWAY_BBOX)
    # 'south' is below lat_min=56.5; 'west' is below lon_min=-5.0
    kept = set(out["label"])
    assert "south" not in kept
    assert "west" not in kept
    assert {"a", "b", "edge"}.issubset(kept)


def test_returns_a_copy_not_a_view(sample_df):
    out = clip_to_bbox(sample_df, "lat", "lon", NORWAY_BBOX)
    out["label"] = "mutated"
    # Original should be unchanged
    assert "mutated" not in set(sample_df["label"])


def test_custom_bbox(sample_df):
    tight = {"lat_min": 65.0, "lat_max": 80.0, "lon_min": 0.0, "lon_max": 30.0}
    out = clip_to_bbox(sample_df, "lat", "lon", tight)
    assert set(out["label"]) == {"b"}  # only (70.0, 25.0)
