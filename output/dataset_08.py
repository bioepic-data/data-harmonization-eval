"""
Dataset 8 harmonization.

Dataset: ess-dive-61a0ecd70856892-20230808T205724993
Title:   Slate River OBJ-2 Soil Sensors (SLAC Groundwater Quality SFA)

Fold-evaluation standalone harmonizer. Reads staged raw package files from
inputs/raw/<dataset_identifier>/, harmonizes soil moisture (VWC) and soil
matric potential time series into the WFSFA target schema, and writes the
harmonized CSV plus a location accumulator to output/.

Follows the code conventions in skills/essdive_sm_harmonizer/SKILL.md and the
patterns used by the expert modular harmonizer (data/gold/expert_code).
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path("inputs/raw")
OUT_DIR = Path("output")

idx = 8
DATASET_ID = "ess-dive-61a0ecd70856892-20230808T205724993"

DATA_FILES = [
    "SLT_OBJ2_SoilSensors_2018_data.csv",
    "SLT_OBJ2_SoilSensors_2019_data.csv",
    "SLT_OBJ2_SoilSensors_2020_data.csv",
    "SLT_OBJ2_SoilSensors_2021_data.csv",
]
METHODS_FILES = [
    "SLT_OBJ2_SoilSensors_2018_InstallationMethods.csv",
    "SLT_OBJ2_SoilSensors_2019_InstallationMethods.csv",
    "SLT_OBJ2_SoilSensors_2020_InstallationMethods.csv",
    "SLT_OBJ2_SoilSensors_2021_InstallationMethods.csv",
]

SITE_ID = "Slate River OBJ-2"
# All years report a single, identical station coordinate (WGS84 decimal degrees).
SITE_LAT = 38.90943
SITE_LON = -107.028242


def read_ds_csv(filename: str, **kwargs) -> pd.DataFrame:
    return pd.read_csv(BASE_DIR / DATASET_ID / filename, encoding="utf-8", **kwargs)


def parse_local_to_utc(series: pd.Series, fmt: str | None, tz: str) -> pd.Series:
    dt = pd.to_datetime(series, format=fmt, errors="coerce")
    dt = dt.dt.tz_localize(tz, ambiguous="NaT", nonexistent="shift_forward")
    return dt.dt.tz_convert("UTC")


def ensure_harmonized_cols(df: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "datetime_UTC",
        "site_id",
        "depth_m",
        "replicate",
        "is_timeseries",
        "volumetric_water_content_m3_m3",
        "gravimetric_water_content_gH2O_gs",
        "water_potential_kPa",
    ]
    for c in cols:
        if c not in df.columns:
            df[c] = np.nan
    return df[cols]


def add_loc_qc(df: pd.DataFrame) -> pd.DataFrame:
    if "qc_flag" not in df.columns:
        df["qc_flag"] = np.where(
            df["latitude"].isna() | df["longitude"].isna(), "g2", None
        )
    return df


def harmonize() -> tuple[pd.DataFrame, pd.DataFrame]:
    per_year = []

    for fname in DATA_FILES:
        d = read_ds_csv(fname)

        # Select the two harmonizable measurement families:
        #   SoilMoisture_<depth>cm.m3.m3  -> volumetric_water_content_m3_m3
        #   SoilMatricPot_<depth>cm.kPa   -> water_potential_kPa
        meas_cols = [
            c for c in d.columns
            if re.match(r"^(SoilMoisture|SoilMatricPot)_", str(c))
        ]
        x = d[["DateTime.MST"] + meas_cols].copy()

        # MST is a fixed UTC-7 offset (no daylight saving); Etc/GMT+7 == UTC-7.
        x["datetime_UTC"] = parse_local_to_utc(
            x["DateTime.MST"], "%Y-%m-%d %H:%M:%S", "Etc/GMT+7"
        )
        x = x.drop(columns=["DateTime.MST"])

        long = x.melt(id_vars=["datetime_UTC"], var_name="name", value_name="value")

        # Column form: <VarFamily>_<depth>cm.<units>  e.g. SoilMoisture_82.5cm.m3.m3
        m = long["name"].str.extract(r"^(SoilMoisture|SoilMatricPot)_(\d+\.?\d*)cm")
        long["var_family"] = m[0]
        long["depth_cm"] = m[1]
        long = long.dropna(subset=["depth_cm"])

        long["value"] = pd.to_numeric(long["value"], errors="coerce")
        long.loc[long["value"] == -9999, "value"] = np.nan
        long = long.dropna(subset=["value"])

        long["dest_var"] = np.where(
            long["var_family"] == "SoilMoisture",
            "volumetric_water_content_m3_m3",
            "water_potential_kPa",
        )

        long["depth_m"] = pd.to_numeric(long["depth_cm"], errors="coerce") / 100.0

        # One sensor per depth per variable => single replicate.
        long["replicate"] = 1

        wide = (
            long.pivot_table(
                index=["datetime_UTC", "depth_m", "replicate"],
                columns="dest_var",
                values="value",
                aggfunc="first",
            )
            .reset_index()
        )

        wide["site_id"] = SITE_ID
        wide["is_timeseries"] = True
        wide["gravimetric_water_content_gH2O_gs"] = np.nan

        per_year.append(ensure_harmonized_cols(wide))

    harmonized = pd.concat(per_year, ignore_index=True)
    harmonized = harmonized.sort_values(
        ["datetime_UTC", "site_id", "depth_m", "replicate"]
    ).reset_index(drop=True)

    loc = pd.DataFrame(
        {
            "site_id": [SITE_ID],
            "latitude": [SITE_LAT],
            "longitude": [SITE_LON],
        }
    )
    loc["source_dataset_id"] = DATASET_ID
    loc = add_loc_qc(loc)

    return harmonized, loc


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    harmonized_df, loc_df = harmonize()

    out_file = OUT_DIR / f"{DATASET_ID}_harmonized.csv"
    harmonized_df.to_csv(out_file, index=False)
    loc_df.to_csv(OUT_DIR / f"{DATASET_ID}_location.csv", index=False)

    print(f"Wrote {out_file}  ({len(harmonized_df)} rows)")
    print(harmonized_df.head().to_string())
    print("\nDepths (m):", sorted(harmonized_df["depth_m"].dropna().unique().tolist()))
    print("VWC non-null:", harmonized_df["volumetric_water_content_m3_m3"].notna().sum())
    print("WP  non-null:", harmonized_df["water_potential_kPa"].notna().sum())
    print("datetime range:", harmonized_df["datetime_UTC"].min(), "->", harmonized_df["datetime_UTC"].max())
