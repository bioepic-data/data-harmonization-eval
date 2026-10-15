"""
Harmonization code for target dataset (fold-02, canonical index 2).

Dataset: ess-dive-9fd65df885a8e87-20250715T064942543
DOI: doi:10.15485/1646477
Title: Soil moisture and temperature data along the northeast facing hillslope
       at the Lower Montane site in the East River Watershed, Colorado.

Self-contained for the fold run environment: raw package files are staged under
inputs/raw/<dataset_identifier>/ and all deliverables are written under output/.
Conventions follow skills/essdive_sm_harmonizer/SKILL.md SECTION 6 / 7.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

# %%
# =============================================================
# Dataset 2
# =============================================================
idx = 2
DATASET_ID = "ess-dive-9fd65df885a8e87-20250715T064942543"

BASE_DIR = Path("inputs/raw")
OUT_DIR = Path("output")
DS_DIR = BASE_DIR / DATASET_ID

OUT_DIR.mkdir(parents=True, exist_ok=True)

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


def ensure_harmonized_cols(df: pd.DataFrame) -> pd.DataFrame:
    for c in HARMONIZED_COLS:
        if c not in df.columns:
            df[c] = np.nan
    return df[HARMONIZED_COLS]


def add_loc_qc(df: pd.DataFrame) -> pd.DataFrame:
    if "qc_flag" not in df.columns:
        missing = df["latitude"].isna() | df["longitude"].isna()
        df["qc_flag"] = np.where(missing, "g2", None).astype(object)
    return df


def parse_local_to_utc(series: pd.Series, fmt: str, tz: str) -> pd.Series:
    dt = pd.to_datetime(series, format=fmt, errors="coerce")
    dt = dt.dt.tz_localize(tz, ambiguous="NaT", nonexistent="shift_forward")
    return dt.dt.tz_convert("UTC")


# ESS-DIVE site IDs use a hyphen (ER-SMN1); payload files use an underscore
# (ER_SMN1.csv). Map filename stem -> canonical site_id from SM_loc.csv.
PAYLOAD_FILES = ["ER_SMN1.csv", "ER_SMN3.csv", "ER_SMN4.csv", "ER_SMN5.csv"]
LOC_FILE = "SM_loc.csv"

harmonized_parts: list[pd.DataFrame] = []

for fname in PAYLOAD_FILES:
    ddf = pd.read_csv(DS_DIR / fname)

    site_stem = Path(fname).stem            # e.g. "ER_SMN1"
    site_id = site_stem.replace("_", "-")   # -> "ER-SMN1" (matches SM_loc.csv)

    # Identify the moisture columns and the depth embedded in each name.
    moisture_cols = [c for c in ddf.columns if c.startswith("Moisture")]

    x = ddf[["DateTime"] + moisture_cols].copy()
    x["datetime_UTC"] = parse_local_to_utc(
        x["DateTime"], "%m/%d/%Y %I:%M:%S %p", "Etc/GMT+7"
    )
    x = x.drop(columns=["DateTime"])

    long = x.melt(
        id_vars=["datetime_UTC"],
        value_vars=moisture_cols,
        var_name="source_variable",
        value_name="volumetric_water_content_m3_m3",
    )

    # Depth encoded in the column name, e.g. "Moisture_m3/m3_10cm" -> 10 cm.
    long["depth_m"] = (
        pd.to_numeric(
            long["source_variable"].str.extract(r"_(\d+\.?\d*)cm")[0],
            errors="coerce",
        )
        / 100.0
    )

    long["volumetric_water_content_m3_m3"] = pd.to_numeric(
        long["volumetric_water_content_m3_m3"], errors="coerce"
    )
    # -9999 is the package's no-data sentinel.
    long.loc[long["volumetric_water_content_m3_m3"] == -9999, "volumetric_water_content_m3_m3"] = np.nan

    long["site_id"] = site_id
    long["replicate"] = int(1)
    long["is_timeseries"] = True
    long["gravimetric_water_content_gH2O_gs"] = np.nan
    long["water_potential_kPa"] = np.nan

    harmonized_parts.append(ensure_harmonized_cols(long))

df_harmonized = pd.concat(harmonized_parts, ignore_index=True)
df_harmonized = df_harmonized.sort_values(
    ["datetime_UTC", "site_id", "depth_m", "replicate"]
).reset_index(drop=True)

df_harmonized.to_csv(OUT_DIR / f"{DATASET_ID}_harmonized.csv", index=False)
print(f"Wrote {DATASET_ID}_harmonized.csv  ({len(df_harmonized)} rows)")


# -------------------------------------------------------------
# Location resolution
# -------------------------------------------------------------
# SM_loc.csv carries decimal-degree Lat/Lon directly (priority 2: package
# ancillary file). No qc flag needed because coordinates are resolved from the
# package itself. One row per distinct site_id present in the harmonized data.
mdf = pd.read_csv(DS_DIR / LOC_FILE)
mdf.columns = [c.strip() for c in mdf.columns]

loc = mdf.rename(
    columns={"Name": "site_id", "Lat": "latitude", "Lon": "longitude"}
)[["site_id", "latitude", "longitude"]].copy()
loc["site_id"] = loc["site_id"].astype(str).str.strip()

sites_present = pd.DataFrame({"site_id": sorted(df_harmonized["site_id"].unique())})
loc = sites_present.merge(loc, on="site_id", how="left")
loc["latitude"] = pd.to_numeric(loc["latitude"], errors="coerce")
loc["longitude"] = pd.to_numeric(loc["longitude"], errors="coerce")
loc["source_dataset_id"] = DATASET_ID
loc = add_loc_qc(loc)

loc = loc[["site_id", "latitude", "longitude", "source_dataset_id", "qc_flag"]]
loc.to_csv(OUT_DIR / f"{DATASET_ID}_location.csv", index=False)
print(f"Wrote {DATASET_ID}_location.csv  ({len(loc)} rows)")
