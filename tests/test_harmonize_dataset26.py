"""Unit tests for the dataset 26 expert harmonizer (dataset_26.py).

Tests use synthetic data that mirrors the real ESS-DIVE package structure:
  - payload: ER18_soil_physical.csv (Collection date, SampleSiteCode,
      Top sample depth_cm, Bottom sample depth_cm, water content %vol)
  - location metadata: from the reference dataset (index 0), keyed on
      Location_ID -> Latitude/Longitude
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

HARMONIZE_SM = Path("data/gold/expert_code/harmonize_sm")
needs_pkg = pytest.mark.skipif(
    not HARMONIZE_SM.exists(), reason="expert harmonizer package not present"
)


def _make_ctx(payload_df: pd.DataFrame, loc_df: pd.DataFrame, idx: int = 26, ref_idx: int = 0):
    """Return a minimal Context-like namespace backed by synthetic DataFrames."""
    mapping = [
        {"index": ref_idx, "dataset_identifier": "ess-dive_ref"},
        {"index": idx, "dataset_identifier": f"ess-dive_ds{idx}"},
    ]

    def dsid(i):
        return mapping[i]["dataset_identifier"]

    def read_ds_csv(i, filename, **kwargs):
        if i == idx:
            return payload_df.copy()
        if i == ref_idx:
            return loc_df.copy()
        raise KeyError(f"unexpected dataset index {i}")

    return SimpleNamespace(
        map_json=mapping,
        ref_idx=ref_idx,
        dsid=dsid,
        read_ds_csv=read_ds_csv,
    )


def _make_payload():
    return pd.DataFrame(
        {
            "Collection date": ["01/15/21", "03/22/21", "06/10/21"],
            "SampleSiteCode": ["SITE_A", "SITE_B", "SITE_A"],
            "Top sample depth_cm": [0, 5, 10],
            "Bottom sample depth_cm": [10, 15, 20],
            "water content %vol": [30.0, 45.5, 22.0],
        }
    )


def _make_loc():
    return pd.DataFrame(
        {
            "Location_ID": ["SITE_A", "SITE_B", "SITE_C"],
            "Latitude": [38.85, 38.90, 38.95],
            "Longitude": [-106.50, -106.55, -106.60],
        }
    )


@needs_pkg
def test_harmonize_returns_dataset_result():
    sys.path.insert(0, str(HARMONIZE_SM.resolve()))
    from dataset_26 import harmonize
    from common import DatasetResult

    ctx = _make_ctx(_make_payload(), _make_loc())
    result = harmonize(ctx)
    assert isinstance(result, DatasetResult)


@needs_pkg
def test_harmonize_output_columns():
    sys.path.insert(0, str(HARMONIZE_SM.resolve()))
    from dataset_26 import harmonize

    ctx = _make_ctx(_make_payload(), _make_loc())
    result = harmonize(ctx)
    expected_cols = {
        "datetime_UTC",
        "site_id",
        "depth_m",
        "replicate",
        "is_timeseries",
        "interval_min",
        "volumetric_water_content_m3_m3",
        "gravimetric_water_content_gH2O_gs",
        "water_potential_kPa",
    }
    assert expected_cols.issubset(set(result.harmonized.columns))


@needs_pkg
def test_harmonize_row_count_matches_payload():
    sys.path.insert(0, str(HARMONIZE_SM.resolve()))
    from dataset_26 import harmonize

    payload = _make_payload()
    ctx = _make_ctx(payload, _make_loc())
    result = harmonize(ctx)
    assert len(result.harmonized) == len(payload)


@needs_pkg
def test_harmonize_datetime_is_utc():
    sys.path.insert(0, str(HARMONIZE_SM.resolve()))
    from dataset_26 import harmonize

    ctx = _make_ctx(_make_payload(), _make_loc())
    result = harmonize(ctx)
    dt = result.harmonized["datetime_UTC"]
    assert dt.dtype == "datetime64[ns, UTC]" or str(dt.dtype).endswith("UTC")


@needs_pkg
def test_harmonize_datetime_correct_value():
    """01/15/21 in America/Denver (UTC-7 in January) -> 2021-01-15 07:00 UTC."""
    sys.path.insert(0, str(HARMONIZE_SM.resolve()))
    from dataset_26 import harmonize

    ctx = _make_ctx(_make_payload(), _make_loc())
    result = harmonize(ctx)
    first_dt = result.harmonized["datetime_UTC"].iloc[0]
    assert first_dt.year == 2021
    assert first_dt.month == 1
    assert first_dt.day == 15


@needs_pkg
def test_harmonize_site_id_renamed():
    sys.path.insert(0, str(HARMONIZE_SM.resolve()))
    from dataset_26 import harmonize

    ctx = _make_ctx(_make_payload(), _make_loc())
    result = harmonize(ctx)
    assert list(result.harmonized["site_id"]) == ["SITE_A", "SITE_B", "SITE_A"]


@needs_pkg
def test_harmonize_depth_midpoint_and_unit_conversion():
    """depth_m = (top + bottom) / 2 / 100.

    Row 0: (0 + 10) / 2 / 100 = 0.05 m
    Row 1: (5 + 15) / 2 / 100 = 0.10 m
    Row 2: (10 + 20) / 2 / 100 = 0.15 m
    """
    sys.path.insert(0, str(HARMONIZE_SM.resolve()))
    from dataset_26 import harmonize

    ctx = _make_ctx(_make_payload(), _make_loc())
    result = harmonize(ctx)
    depths = result.harmonized["depth_m"].tolist()
    assert depths == pytest.approx([0.05, 0.10, 0.15])


@needs_pkg
def test_harmonize_replicate_is_1():
    sys.path.insert(0, str(HARMONIZE_SM.resolve()))
    from dataset_26 import harmonize

    ctx = _make_ctx(_make_payload(), _make_loc())
    result = harmonize(ctx)
    assert (result.harmonized["replicate"] == 1).all()


@needs_pkg
def test_harmonize_is_timeseries_false():
    sys.path.insert(0, str(HARMONIZE_SM.resolve()))
    from dataset_26 import harmonize

    ctx = _make_ctx(_make_payload(), _make_loc())
    result = harmonize(ctx)
    assert (result.harmonized["is_timeseries"] == False).all()  # noqa: E712


@needs_pkg
def test_harmonize_interval_min_is_nan():
    sys.path.insert(0, str(HARMONIZE_SM.resolve()))
    from dataset_26 import harmonize

    ctx = _make_ctx(_make_payload(), _make_loc())
    result = harmonize(ctx)
    assert result.harmonized["interval_min"].isna().all()


@needs_pkg
def test_harmonize_vwc_divided_by_100():
    """water content %vol divided by 100 -> m3/m3."""
    sys.path.insert(0, str(HARMONIZE_SM.resolve()))
    from dataset_26 import harmonize

    ctx = _make_ctx(_make_payload(), _make_loc())
    result = harmonize(ctx)
    vwc = result.harmonized["volumetric_water_content_m3_m3"].tolist()
    assert vwc == pytest.approx([0.30, 0.455, 0.22])


@needs_pkg
def test_harmonize_gwc_and_swp_are_nan():
    sys.path.insert(0, str(HARMONIZE_SM.resolve()))
    from dataset_26 import harmonize

    ctx = _make_ctx(_make_payload(), _make_loc())
    result = harmonize(ctx)
    assert result.harmonized["gravimetric_water_content_gH2O_gs"].isna().all()
    assert result.harmonized["water_potential_kPa"].isna().all()


@needs_pkg
def test_harmonize_dataset_id():
    sys.path.insert(0, str(HARMONIZE_SM.resolve()))
    from dataset_26 import harmonize

    ctx = _make_ctx(_make_payload(), _make_loc())
    result = harmonize(ctx)
    assert result.dataset_id == "ess-dive_ds26"


@needs_pkg
def test_harmonize_locations_non_empty():
    sys.path.insert(0, str(HARMONIZE_SM.resolve()))
    from dataset_26 import harmonize

    ctx = _make_ctx(_make_payload(), _make_loc())
    result = harmonize(ctx)
    assert len(result.locations) == 1
    loc_df = result.locations[0]
    assert isinstance(loc_df, pd.DataFrame)
    assert set(["site_id", "latitude", "longitude"]).issubset(loc_df.columns)


@needs_pkg
def test_harmonize_location_lookup_filters_to_present_sites():
    """Only sites that appear in the payload should be in the location frame."""
    sys.path.insert(0, str(HARMONIZE_SM.resolve()))
    from dataset_26 import harmonize

    ctx = _make_ctx(_make_payload(), _make_loc())
    result = harmonize(ctx)
    loc_df = result.locations[0]
    assert set(loc_df["site_id"]) == {"SITE_A", "SITE_B"}
    assert "SITE_C" not in loc_df["site_id"].values


@needs_pkg
def test_harmonize_location_lat_lon_values():
    sys.path.insert(0, str(HARMONIZE_SM.resolve()))
    from dataset_26 import harmonize

    ctx = _make_ctx(_make_payload(), _make_loc())
    result = harmonize(ctx)
    loc_df = result.locations[0].set_index("site_id")
    assert loc_df.loc["SITE_A", "latitude"] == pytest.approx(38.85)
    assert loc_df.loc["SITE_A", "longitude"] == pytest.approx(-106.50)
    assert loc_df.loc["SITE_B", "latitude"] == pytest.approx(38.90)
    assert loc_df.loc["SITE_B", "longitude"] == pytest.approx(-106.55)


@needs_pkg
def test_harmonize_location_source_dataset_id_set():
    sys.path.insert(0, str(HARMONIZE_SM.resolve()))
    from dataset_26 import harmonize

    ctx = _make_ctx(_make_payload(), _make_loc())
    result = harmonize(ctx)
    loc_df = result.locations[0]
    assert (loc_df["source_dataset_id"] == "ess-dive_ds26").all()


@needs_pkg
def test_harmonize_vwc_non_numeric_coerced_to_nan():
    """Non-numeric water content values should be coerced to NaN."""
    sys.path.insert(0, str(HARMONIZE_SM.resolve()))
    from dataset_26 import harmonize

    payload = _make_payload()
    payload.loc[1, "water content %vol"] = "n/a"
    ctx = _make_ctx(payload, _make_loc())
    result = harmonize(ctx)
    assert pd.isna(result.harmonized["volumetric_water_content_m3_m3"].iloc[1])


@needs_pkg
def test_harmonize_depth_non_numeric_coerced_to_nan():
    """Non-numeric depth values should be coerced to NaN."""
    sys.path.insert(0, str(HARMONIZE_SM.resolve()))
    from dataset_26 import harmonize

    payload = _make_payload()
    payload.loc[0, "Top sample depth_cm"] = "unknown"
    ctx = _make_ctx(payload, _make_loc())
    result = harmonize(ctx)
    assert pd.isna(result.harmonized["depth_m"].iloc[0])
