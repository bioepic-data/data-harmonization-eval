"""
Dataset 4 harmonization.

Dataset: ess-dive-6c7085e9c544cc6-20250424T164534831
DOI: doi:10.15485/2561511

Johnsen/Bi (2025) DAE manuscript data package. Daily meteorological,
vegetation, and soil data (df_data.csv) with a row-aligned location/time
file (df_meta.csv). Only the soil moisture variables are harmonized:
  - swc: soil water content -> volumetric_water_content_m3_m3 (already m3/m3)
  - swp: soil water potential -> water_potential_kPa (already kPa, negative)

Each df_data.csv row corresponds positionally to the same row in
df_meta.csv (site, datetime). swc/swp are depth-weighted averages across
four sensor depths, so no single depth_m can be assigned (left as NaN).

Site coordinates are resolved from the package-level ESS-DIVE
spatialCoverage metadata record.
"""

from __future__ import annotations

from pathlib import Path
import re
import numpy as np
import pandas as pd

BASE_DIR = Path("inputs/raw")
OUT_DIR = Path("output")

idx = 4
DATASET_ID = "ess-dive-6c7085e9c544cc6-20250424T164534831"
PKG_SUBDIR = "Johnsen_Bi_2025_DAE_Manuscript_Data_Package"


def ds_path(dataset_id: str) -> Path:
    return BASE_DIR / dataset_id / PKG_SUBDIR


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


def add_loc_qc(df: pd.DataFrame, default_flag) -> pd.DataFrame:
    if "qc_flag" not in df.columns:
        df["qc_flag"] = np.where(
            df["latitude"].isna() | df["longitude"].isna(), "g2", default_flag
        )
    return df


# Coordinates from the package ESS-DIVE spatialCoverage record
# (Source 3 in the location resolution priority order; native package
# metadata, so qc_flag is left null for resolved sites).
SITE_COORDS = {
    "ph1": (38.92, -106.95),
    "ph2": (38.922583, -106.947288),
    "sg5": (38.92625, -106.98),
    "tb": (37.878607, -122.241423),
}


def harmonize():
    dpath = ds_path(DATASET_ID)
    ddf = pd.read_csv(dpath / "df_data.csv")
    mdf = pd.read_csv(dpath / "df_meta.csv")

    if len(ddf) != len(mdf):
        raise ValueError(
            f"Row count mismatch: df_data.csv={len(ddf)} df_meta.csv={len(mdf)}"
        )

    x = pd.DataFrame(index=ddf.index)

    # df_meta.csv carries only a calendar date (no time component / tz);
    # treat the day as midnight UTC.
    x["datetime_UTC"] = parse_date_to_utc(mdf["datetime"])
    x["site_id"] = mdf["site"].astype(str)

    # swc/swp are depth-weighted integrated values across four sensor
    # depths; no single representative depth can be assigned.
    x["depth_m"] = np.nan
    x["replicate"] = 1
    x["is_timeseries"] = True

    # swc is soil water content already expressed in m3 m-3.
    x["volumetric_water_content_m3_m3"] = pd.to_numeric(ddf["swc"], errors="coerce")
    x.loc[x["volumetric_water_content_m3_m3"] == -9999, "volumetric_water_content_m3_m3"] = np.nan

    x["gravimetric_water_content_gH2O_gs"] = np.nan

    # swp is soil water potential already expressed in kPa (negative).
    x["water_potential_kPa"] = pd.to_numeric(ddf["swp"], errors="coerce")
    x.loc[x["water_potential_kPa"] == -9999, "water_potential_kPa"] = np.nan

    harmonized = ensure_harmonized_cols(x)

    # Location: one row per distinct site_id, coordinates from package metadata.
    sites = harmonized["site_id"].dropna().unique().tolist()
    loc = pd.DataFrame(
        {
            "site_id": sites,
            "latitude": [SITE_COORDS.get(s, (np.nan, np.nan))[0] for s in sites],
            "longitude": [SITE_COORDS.get(s, (np.nan, np.nan))[1] for s in sites],
        }
    )
    loc["source_dataset_id"] = DATASET_ID
    loc = add_loc_qc(loc, default_flag=None)
    loc = loc[["site_id", "latitude", "longitude", "source_dataset_id", "qc_flag"]]

    return harmonized, loc


def parse_date_to_utc(series: pd.Series) -> pd.Series:
    dt = pd.to_datetime(series, format="%Y-%m-%d", errors="coerce")
    dt = dt.dt.tz_localize("UTC")
    return dt


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    harmonized, loc = harmonize()

    harmonized = harmonized.sort_values(
        by=["datetime_UTC", "site_id", "depth_m", "replicate"]
    )
    harmonized.to_csv(OUT_DIR / f"{DATASET_ID}_harmonized.csv", index=False)
    loc.to_csv(OUT_DIR / f"{DATASET_ID}_location.csv", index=False)
    print(f"Wrote {DATASET_ID}_harmonized.csv ({len(harmonized)} rows)")
    print(f"Wrote {DATASET_ID}_location.csv ({len(loc)} rows)")
