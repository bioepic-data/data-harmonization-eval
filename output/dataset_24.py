"""
Dataset 24 harmonization.

Dataset: ess-dive-daa156d2129c471-20250716T160748658

Soil matric potential (MP) time series from two isotope-monitoring profiles
(P1, P2) at the RMBL/East River aspen-conifer site. Only the matric-potential
columns are harmonized; water isotope, sap flow, and meteorology columns are
not soil moisture observations and are excluded.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path("inputs/raw")
OUT_DIR = Path("output")

DATASET_ID = "ess-dive-daa156d2129c471-20250716T160748658"
DATA_FILE = "Iso_MP_Sap_DataDaily_ESSDiveUpload_R1.csv"
LOC_FILE = "Locations.csv"

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
        df["qc_flag"] = np.where(
            df["latitude"].isna() | df["longitude"].isna(), "g2", None
        )
    return df


def harmonize():
    ds_dir = BASE_DIR / DATASET_ID

    df = pd.read_csv(ds_dir / DATA_FILE, sep=";")
    mdf = pd.read_csv(ds_dir / LOC_FILE, sep=";")

    x = df.copy()
    # Timestamps are daily dates (no time component); no explicit timezone in
    # package. Interpret local (Mountain, Etc/GMT+7, no DST) and convert to UTC.
    dt = pd.to_datetime(x["Timestamp"], format="%Y-%m-%d", errors="coerce")
    dt = dt.dt.tz_localize("Etc/GMT+7", ambiguous="NaT", nonexistent="shift_forward")
    x["datetime_UTC"] = dt.dt.tz_convert("UTC")

    # Matric potential columns are named P<site>_MP_<depth_cm>.
    mp_cols = [c for c in x.columns if re.match(r"^P\d+_MP_\d+", c)]
    for c in mp_cols:
        x[c] = pd.to_numeric(x[c], errors="coerce")

    long = x.melt(
        id_vars=["datetime_UTC"],
        value_vars=mp_cols,
        var_name="name",
        value_name="water_potential_kPa",
    )

    parts = long["name"].str.extract(r"^(P\d+)_MP_(\d+)$")
    long["site_id"] = parts[0]
    long["depth_m"] = pd.to_numeric(parts[1], errors="coerce") / 100.0

    long["is_timeseries"] = True
    long["volumetric_water_content_m3_m3"] = np.nan
    long["gravimetric_water_content_gH2O_gs"] = np.nan
    long["replicate"] = 1

    long = long[long["water_potential_kPa"].notna()].copy()
    long = long.sort_values(["datetime_UTC", "site_id", "depth_m", "replicate"])

    harmonized = ensure_harmonized_cols(long)

    loc = mdf.rename(
        columns={"ID": "site_id", "Latitude": "latitude", "Longitude": "longitude"}
    )[["site_id", "latitude", "longitude"]].copy()
    loc = loc[loc["site_id"].isin(harmonized["site_id"].dropna().unique())]
    loc["source_dataset_id"] = DATASET_ID
    loc = add_loc_qc(loc)

    return harmonized, loc


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    harmonized, loc = harmonize()

    harmonized.to_csv(OUT_DIR / f"{DATASET_ID}_harmonized.csv", index=False)
    loc.to_csv(OUT_DIR / f"{DATASET_ID}_location.csv", index=False)

    print(f"Wrote {len(harmonized)} harmonized rows for {DATASET_ID}")
    print("Sites:", sorted(harmonized["site_id"].dropna().unique()))
    print("Depths (m):", sorted(harmonized["depth_m"].dropna().unique()))
    print(harmonized.head())


if __name__ == "__main__":
    main()
