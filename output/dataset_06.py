"""
Dataset 6 harmonization.

Dataset: ess-dive-18e91eb74405882-20241017T173226640
DOI: doi:10.15485/1909712

Snodgrass Mountain (East River Watershed, CO) soil CO2 / moisture / temperature
and micrometeorological time series. Four tripod stations along an elevation
gradient. Soil moisture (VWC) measured at 5, 15, and 50 cm depths in wide format,
with site coordinates embedded in the data payload.

Structurally analogous to exemplar dataset_08 (wide-to-long melt of embedded-depth
VWC columns). Follows the code conventions in skills/essdive_sm_harmonizer/SKILL.md.
"""

from __future__ import annotations

from pathlib import Path
import re

import numpy as np
import pandas as pd

BASE_DIR = Path("inputs/raw")
OUT_DIR = Path("output")

IDX = 6
DATASET_ID = "ess-dive-18e91eb74405882-20241017T173226640"
DATA_FILE = "Snodgrass_ESS.csv"


def harmonize() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Harmonize dataset 6 and return (harmonized_df, location_df)."""
    src = BASE_DIR / DATASET_ID / DATA_FILE

    # Rows 2 and 3 (0-indexed 1,2) are descriptor and units rows, not data.
    df = pd.read_csv(src, skiprows=[1, 2], low_memory=False)

    # Keep only columns needed for the harmonized soil-moisture schema.
    vwc_cols = ["VWC_50cm", "VWC_15cm", "VWC_5cm"]
    keep = ["TIMESTAMP", "site", "latitude", "longitude"] + vwc_cols
    x = df[keep].copy()

    # ---- Timestamp ----
    # The data file's own descriptor row labels TIMESTAMP as date_time "UTC"
    # (units format mm-dd-yyyy hh:mm:ss). Parse as UTC directly; no local->UTC
    # conversion applied. See notes for the metadata timezone discrepancy.
    dt = pd.to_datetime(x["TIMESTAMP"], format="%m/%d/%y %H:%M", errors="coerce")
    x["datetime_UTC"] = dt.dt.tz_localize("UTC")

    x["site_id"] = x["site"].astype(str)

    # ---- Wide-to-long on embedded-depth VWC columns ----
    for c in vwc_cols:
        v = pd.to_numeric(x[c], errors="coerce")
        v = v.where(v != -9999, np.nan)
        x[c] = v

    long = x.melt(
        id_vars=["datetime_UTC", "site_id"],
        value_vars=vwc_cols,
        var_name="source_variable",
        value_name="volumetric_water_content_m3_m3",
    )

    # Depth embedded in column name (e.g. VWC_50cm) -> meters.
    long["depth_m"] = pd.to_numeric(
        long["source_variable"].str.extract(r"(\d+\.?\d*)")[0],
        errors="coerce",
    ) / 100.0

    long["volumetric_water_content_m3_m3"] = pd.to_numeric(
        long["volumetric_water_content_m3_m3"], errors="coerce"
    )
    long["water_potential_kPa"] = np.nan
    long["gravimetric_water_content_gH2O_gs"] = np.nan
    long["replicate"] = 1
    long["is_timeseries"] = True

    harmonized = ensure_harmonized_cols(long)

    # ---- Location: coordinates embedded in the data payload (priority 1) ----
    loc = (
        x[["site_id", "latitude", "longitude"]]
        .copy()
    )
    loc["latitude"] = pd.to_numeric(loc["latitude"], errors="coerce")
    loc["longitude"] = pd.to_numeric(loc["longitude"], errors="coerce")
    # One row per distinct site_id, preferring a row that carries coordinates.
    loc = (
        loc.sort_values(["site_id", "latitude"], na_position="last")
        .groupby("site_id", as_index=False)
        .first()
    )
    loc["source_dataset_id"] = DATASET_ID
    loc = add_loc_qc(loc)
    loc = loc[["site_id", "latitude", "longitude", "source_dataset_id", "qc_flag"]]

    return harmonized, loc


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


if __name__ == "__main__":
    harmonized, loc = harmonize()
    harmonized = harmonized.sort_values(
        ["datetime_UTC", "site_id", "depth_m", "replicate"]
    )
    harmonized["datetime_UTC"] = (
        pd.to_datetime(harmonized["datetime_UTC"], utc=True)
        .dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    harmonized.to_csv(OUT_DIR / f"{DATASET_ID}_harmonized.csv", index=False)
    loc.to_csv(OUT_DIR / f"{DATASET_ID}_location.csv", index=False)
    print(f"harmonized rows: {len(harmonized)}")
    print(f"location rows: {len(loc)}")
    print(loc.to_string())
