"""
Dataset 2 harmonization.

Dataset: ess-dive-9fd65df885a8e87-20250715T064942543

Self-contained harmonization script for a single fold evaluation.
Follows the WFSFA soil moisture harmonization skill conventions
(SECTION 6 / SECTION 7) and mirrors the modular expert pattern
(common.py helpers + per-dataset harmonize block).

Structurally analogous to expert dataset 17 (ess-dive-be919d7d5d42c94):
multiple per-site wide-format CSVs with soil-moisture depths embedded in
column names, site_id parsed from the source filename, and a separate
location metadata file.
"""

from __future__ import annotations

from pathlib import Path
import re

import numpy as np
import pandas as pd
from pyproj import Transformer


BASE_DIR = Path("inputs/raw")
OUT_DIR = Path("output")

DATASET_ID = "ess-dive-9fd65df885a8e87-20250715T064942543"
IDX = 2

DATA_FILES = ["ER_SMN1.csv", "ER_SMN3.csv", "ER_SMN4.csv", "ER_SMN5.csv"]
LOC_FILE = "SM_loc.csv"


# ---------------------------------------------------------------
# Helpers (mirrors common.py conventions)
# ---------------------------------------------------------------
def ds_path() -> Path:
    return BASE_DIR / DATASET_ID


def read_ds_csv(filename: str, **kwargs) -> pd.DataFrame:
    return pd.read_csv(ds_path() / filename, **kwargs)


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


# %%
# =============================================================
# Dataset 2
# =============================================================
def harmonize() -> tuple[pd.DataFrame, pd.DataFrame]:
    __harmonized_parts = []

    for fname in DATA_FILES:
        d = read_ds_csv(fname)

        # site_id parsed from source filename, normalized to the hyphenated
        # form used in the location metadata file (ER_SMN1 -> ER-SMN1).
        stem = Path(fname).stem
        site_id = stem.replace("_", "-", 1) if stem.startswith("ER_") else stem

        x = d.copy()
        x["datetime_UTC"] = parse_local_to_utc(
            x["DateTime"], "%m/%d/%Y %I:%M:%S %p", "America/Denver"
        )
        x["site_id"] = site_id

        mc_cols = [c for c in x.columns if c.startswith("Moisture")]
        long = x.melt(
            id_vars=["datetime_UTC", "site_id"],
            value_vars=mc_cols,
            var_name="name",
            value_name="value",
        )

        # Depth embedded in column name, e.g. 'Moisture_m3/m3_50cm' -> 0.50 m.
        long["depth_m"] = (
            pd.to_numeric(long["name"].str.extract(r"_(\d+\.?\d*)cm$")[0], errors="coerce")
            / 100.0
        )

        long["volumetric_water_content_m3_m3"] = pd.to_numeric(
            long["value"], errors="coerce"
        )
        # Source uses -9999 as the missing-value sentinel.
        long.loc[long["volumetric_water_content_m3_m3"] == -9999.0,
                 "volumetric_water_content_m3_m3"] = np.nan
        long = long[long["volumetric_water_content_m3_m3"].notna()].copy()

        long["replicate"] = 1
        long["is_timeseries"] = True
        long["water_potential_kPa"] = np.nan
        long["gravimetric_water_content_gH2O_gs"] = np.nan

        __harmonized_parts.append(ensure_harmonized_cols(long))

    harmonized = pd.concat(__harmonized_parts, ignore_index=True)
    harmonized = harmonized.sort_values(
        ["datetime_UTC", "site_id", "depth_m", "replicate"]
    ).reset_index(drop=True)

    # ---- Location: lat/lon provided directly in SM_loc.csv ----
    mdf = read_ds_csv(LOC_FILE)
    mdf.columns = [c.strip() for c in mdf.columns]
    loc = pd.DataFrame(
        {
            "site_id": mdf["Name"].astype(str).str.strip(),
            "latitude": pd.to_numeric(mdf["Lat"], errors="coerce"),
            "longitude": pd.to_numeric(mdf["Lon"], errors="coerce"),
        }
    )
    loc["source_dataset_id"] = DATASET_ID
    loc = add_loc_qc(loc)
    # Retain only sites present in the harmonized payload.
    loc = loc[loc["site_id"].isin(harmonized["site_id"].unique())].reset_index(drop=True)

    return harmonized, loc


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    harmonized, loc = harmonize()

    out_csv = OUT_DIR / f"{DATASET_ID}_harmonized.csv"
    harmonized.to_csv(out_csv, index=False)
    loc.to_csv(OUT_DIR / f"{DATASET_ID}_location.csv", index=False)

    print(f"Wrote {out_csv} ({len(harmonized)} rows)")
    print(harmonized.head())
    print("\nSites:", sorted(harmonized['site_id'].unique()))
    print("Depths:", sorted(harmonized['depth_m'].dropna().unique()))
    print("VWC range:", harmonized['volumetric_water_content_m3_m3'].min(),
          harmonized['volumetric_water_content_m3_m3'].max())
    print("\nLocations:\n", loc.to_string())
