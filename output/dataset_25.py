"""
Dataset 25 harmonization.

Dataset: ess-dive-e67ab1151ebc525-20230929T190307767
DOI: doi:10.6084/M9.FIGSHARE.7834406.V2

Raw soil CO2, moisture, and temperature data from adjacent mixed-conifer and
aspen forest stands at the Rocky Mountain Biological Laboratory, Gothic,
Colorado (East River Watershed), June 2011 - December 2021. Hourly logger
output from Decagon 5TE soil moisture/temperature probes at 5, 15, and 50 cm
depth in two soil pits (one per forest type).

This module follows the self-contained fold-evaluation conventions: it reads
from inputs/raw/<dataset_identifier>/ and writes to output/. It intentionally
does not import the expert common.py library (not supplied in this workspace),
but mirrors its helper behaviour (parse_local_to_utc, ensure_harmonized_cols,
add_loc_qc).
"""

from __future__ import annotations

from pathlib import Path
import re

import numpy as np
import pandas as pd

DATASET_ID = "ess-dive-e67ab1151ebc525-20230929T190307767"
DOI = "doi:10.6084/M9.FIGSHARE.7834406.V2"
IDX = 25

BASE_DIR = Path("inputs/raw") / DATASET_ID
OUT_DIR = Path("output")

# Shared header order for both payload files (Carbone_conifer.csv carries an
# inline header row; Carbone_aspen.csv is headerless but column-aligned).
COLUMNS = [
    "Year", "Month", "Day", "Hour",
    "CO2-50cm", "CO2-15cm", "CO2-5cm", "CO2-0cm", "CO2-above",
    "T-50cm", "T-15cm", "T-5cm", "T-0cm", "T-above",
    "VWC-50cm", "VWC-15cm", "VWC-5cm",
    "DecagonT-50cm", "DecagonT-15cm", "DecagonT-5cm",
    "EC-50cm", "EC-15cm", "EC-5cm",
    "BatteryVoltage",
]

# Package-level ESS-DIVE metadata reports a single coordinate for both soil
# pits (within 15 m of each other): 38.9592 N, 106.9898 W, Gothic, CO.
SITE_LAT = 38.9592
SITE_LON = -106.9898
LOCAL_TZ = "America/Denver"

HARMONIZED_COLS = [
    "datetime_UTC",
    "site_id",
    "depth_m",
    "replicate",
    "is_timeseries",
    "volumetric_water_content_m3_m3",
    "gravimetric_water_content_gH2O_gs",
    "water_potential_kPa",
]

# File -> site_id mapping (one soil pit per forest type).
FILE_SITES = {
    "Carbone_aspen.csv": "Carbone_aspen",
    "Carbone_conifer.csv": "Carbone_conifer",
}


def parse_local_to_utc(series: pd.Series, tz: str) -> pd.Series:
    dt = pd.to_datetime(series, errors="coerce")
    dt = dt.dt.tz_localize(tz, ambiguous="NaT", nonexistent="shift_forward")
    return dt.dt.tz_convert("UTC")


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


def _read_payload(filename: str) -> pd.DataFrame:
    """Read a payload CSV robustly whether or not it has an inline header."""
    path = BASE_DIR / filename
    probe = pd.read_csv(path, header=None, nrows=1, dtype=str)
    first_cell = str(probe.iloc[0, 0]).strip()
    has_header = first_cell.lower() == "year"
    if has_header:
        df = pd.read_csv(path)
        df.columns = COLUMNS[: len(df.columns)]
    else:
        df = pd.read_csv(path, header=None, names=COLUMNS)
    return df


def harmonize() -> tuple[pd.DataFrame, pd.DataFrame]:
    frames = []
    for filename, site_id in FILE_SITES.items():
        df = _read_payload(filename)

        ts = pd.to_datetime(
            dict(
                year=pd.to_numeric(df["Year"], errors="coerce"),
                month=pd.to_numeric(df["Month"], errors="coerce"),
                day=pd.to_numeric(df["Day"], errors="coerce"),
                hour=pd.to_numeric(df["Hour"], errors="coerce"),
            ),
            errors="coerce",
        )
        df = df.copy()
        df["datetime_UTC"] = parse_local_to_utc(ts, LOCAL_TZ)
        df["site_id"] = site_id

        vwc_cols = [c for c in df.columns if re.match(r"^VWC-\d+cm$", c)]
        long = df.melt(
            id_vars=["datetime_UTC", "site_id"],
            value_vars=vwc_cols,
            var_name="name",
            value_name="volumetric_water_content_m3_m3",
        )
        depth_cm = long["name"].str.extract(r"VWC-(\d+)cm")[0]
        long["depth_m"] = pd.to_numeric(depth_cm, errors="coerce") / 100.0
        long["volumetric_water_content_m3_m3"] = pd.to_numeric(
            long["volumetric_water_content_m3_m3"], errors="coerce"
        )
        long["replicate"] = 1
        long["is_timeseries"] = True
        long["gravimetric_water_content_gH2O_gs"] = np.nan
        long["water_potential_kPa"] = np.nan

        frames.append(ensure_harmonized_cols(long))

    harmonized = pd.concat(frames, ignore_index=True)

    loc = pd.DataFrame(
        {
            "site_id": list(FILE_SITES.values()),
            "latitude": SITE_LAT,
            "longitude": SITE_LON,
        }
    )
    loc["source_dataset_id"] = DATASET_ID
    loc = add_loc_qc(loc)

    return harmonized, loc


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    harmonized, loc = harmonize()

    harmonized = harmonized.sort_values(
        by=["datetime_UTC", "site_id", "depth_m", "replicate"]
    ).reset_index(drop=True)

    harmonized.to_csv(OUT_DIR / f"{DATASET_ID}_harmonized.csv", index=False)

    loc_out = loc[
        ["site_id", "latitude", "longitude", "source_dataset_id", "qc_flag"]
    ]
    loc_out.to_csv(OUT_DIR / f"{DATASET_ID}_location.csv", index=False)

    print(f"Wrote {DATASET_ID}_harmonized.csv ({len(harmonized)} rows)")
    print(f"Wrote {DATASET_ID}_location.csv ({len(loc_out)} rows)")


if __name__ == "__main__":
    main()
