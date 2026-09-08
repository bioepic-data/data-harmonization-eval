"""
Dataset 15 harmonization.

Dataset: ess-dive-987726ef1235abc-20230504T210342929747
Payload: TDR_survey_ER_20190701.csv

A discrete TDR (Time Domain Reflectometry) soil-moisture survey in the East
River watershed (CO). Each surveyed point reports three replicate volumetric
water-content readings (%). Coordinates are UTM Zone 13N (EPSG:32613) embedded
in the payload file. The survey date (2019-07-01) is embedded in the filename;
there is no per-record timestamp, so this is treated as a discrete campaign
(is_timeseries = False). Depth is not reported for the surface TDR probe and is
populated with NA (documented as a limitation).

Analogous expert exemplar: dataset 9 (NEON plot TDR survey with VWC_i
replicates and UTM coordinates in the payload).

This block mirrors the modular expert-code conventions (common.py helpers) but
is written to run standalone inside the fold workspace, reading raw inputs from
inputs/raw/<dataset_identifier>/ and writing deliverables under output/.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer


BASE_DIR = Path("inputs/raw")
OUT_DIR = Path("output")

IDX = 15
DATASET_ID = "ess-dive-987726ef1235abc-20230504T210342929747"
PAYLOAD_FILE = "TDR_survey_ER_20190701.csv"

# Survey date parsed from the payload filename (YYYYMMDD -> 2019-07-01).
# No time-of-day is reported; the field campaign is treated as a single date.
SURVEY_DATE = "2019-07-01"
SURVEY_TZ = "America/Denver"

HARMONIZED_COLS = [
    "datetime_UTC",
    "site_id",
    "depth_m",
    "replicate",
    "is_timeseries",
    "interval_min",
    "volumetric_water_content_m3_m3",
    "gravimetric_water_content_gH2O_gs",
    "water_potential_kPa",
]

VWC_COLS = ["TDR_SM(VWC%)_1", "TDR_SM(VWC%)_2", "TDR_SM(VWC%)_3"]


def utm32613_to_latlon(df: pd.DataFrame, e_col: str, n_col: str) -> pd.DataFrame:
    """Convert UTM Zone 13N (EPSG:32613) coordinates to lat/lon (EPSG:4326)."""
    tr = Transformer.from_crs("EPSG:32613", "EPSG:4326", always_xy=True)
    e = pd.to_numeric(df[e_col], errors="coerce").values
    n = pd.to_numeric(df[n_col], errors="coerce").values
    lon, lat = tr.transform(e, n)
    out = df.copy()
    out["longitude"] = lon
    out["latitude"] = lat
    return out


def ensure_harmonized_cols(df: pd.DataFrame) -> pd.DataFrame:
    for c in HARMONIZED_COLS:
        if c not in df.columns:
            df[c] = np.nan
    return df[HARMONIZED_COLS]


def add_loc_qc(df: pd.DataFrame) -> pd.DataFrame:
    if "qc_flag" not in df.columns:
        df["qc_flag"] = np.where(
            df["latitude"].isna() | df["longitude"].isna(), "g2", None
        )
    return df


def harmonize() -> tuple[pd.DataFrame, pd.DataFrame]:
    ddf = pd.read_csv(BASE_DIR / DATASET_ID / PAYLOAD_FILE)

    x = ddf.copy()

    # Point-level identifier (e.g., ss01, TDR001) serves as site_id, analogous
    # to SampleSiteCode in dataset 9.
    x["site_id"] = x["GPS_id"].astype(str)

    # Single campaign date from the filename; no per-record timestamp.
    x["datetime_UTC"] = (
        pd.Timestamp(SURVEY_DATE)
        .tz_localize(SURVEY_TZ)
        .tz_convert("UTC")
    )
    x["is_timeseries"] = False
    x["interval_min"] = np.nan

    # Depth not reported for the surface TDR probe.
    x["depth_m"] = np.nan
    x["water_potential_kPa"] = np.nan
    x["gravimetric_water_content_gH2O_gs"] = np.nan

    long = x.melt(
        id_vars=[
            "site_id",
            "datetime_UTC",
            "depth_m",
            "is_timeseries",
            "interval_min",
            "water_potential_kPa",
            "gravimetric_water_content_gH2O_gs",
        ],
        value_vars=VWC_COLS,
        var_name="tmp",
        value_name="VWC",
    )
    long["replicate"] = long["tmp"].str.extract(r"_(\d+)$")[0].astype(int)

    long["VWC"] = pd.to_numeric(long["VWC"], errors="coerce")
    long.loc[long["VWC"] == -9999.0, "VWC"] = np.nan
    long = long[long["VWC"].notna()].copy()

    # % VWC -> m3/m3
    long["volumetric_water_content_m3_m3"] = (long["VWC"] / 100.0).round(4)

    harmonized = ensure_harmonized_cols(long)

    # Location table: UTM Zone 13N -> lat/lon, one row per surveyed point.
    loc_tmp = utm32613_to_latlon(ddf, "Easting_m", "Northing_m")
    loc = pd.DataFrame(
        {
            "site_id": loc_tmp["GPS_id"].astype(str),
            "latitude": loc_tmp["latitude"],
            "longitude": loc_tmp["longitude"],
        }
    )
    loc["source_dataset_id"] = DATASET_ID
    loc = loc.drop_duplicates(subset=["site_id"]).reset_index(drop=True)
    loc = add_loc_qc(loc)

    return harmonized, loc


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    harmonized, loc = harmonize()

    harmonized = harmonized.sort_values(
        by=["datetime_UTC", "site_id", "depth_m", "replicate"],
        na_position="last",
    ).reset_index(drop=True)

    out_csv = OUT_DIR / f"{DATASET_ID}_harmonized.csv"
    harmonized.to_csv(out_csv, index=False)
    print(f"Wrote {out_csv} ({len(harmonized)} rows)")

    loc_csv = OUT_DIR / f"{DATASET_ID}_location.csv"
    loc.to_csv(loc_csv, index=False)
    print(f"Wrote {loc_csv} ({len(loc)} sites)")


if __name__ == "__main__":
    main()
