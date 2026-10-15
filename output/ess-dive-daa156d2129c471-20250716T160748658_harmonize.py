"""
Dataset 24 harmonization.

Dataset: ess-dive-daa156d2129c471-20250716T160748658
DOI: doi:10.15485/2462766

Daily soil matric (water) potential from two soil profiles (P1 beneath aspen,
P2 beneath spruce) in the East River Watershed near Gothic, CO. Matric
potential measured with Teros 21 sensors at 15, 30, and 60 cm depths and
reported in kPa (negative). The payload also contains stable-isotope, sap-flow,
and meteorological columns, none of which map to the soil-moisture target
schema; only the matric-potential columns are harmonized.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path("inputs/raw")
OUT_DIR = Path("output")

IDX = 24
DSID = "ess-dive-daa156d2129c471-20250716T160748658"
DATA_FILE = "Iso_MP_Sap_DataDaily_ESSDiveUpload_R1.csv"
LOC_FILE = "Locations.csv"
TZ = "America/Denver"


def ds_path() -> Path:
    return BASE_DIR / DSID


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


def parse_local_to_utc(series: pd.Series, fmt: str | None, tz: str) -> pd.Series:
    dt = pd.to_datetime(series, format=fmt, errors="coerce")
    dt = dt.dt.tz_localize(tz, ambiguous="NaT", nonexistent="shift_forward")
    return dt.dt.tz_convert("UTC")


def harmonize():
    ddf = pd.read_csv(ds_path() / DATA_FILE, sep=";")

    mp_cols = [c for c in ddf.columns if re.fullmatch(r"P\d+_MP_\d+", c)]

    x = ddf[["Timestamp"] + mp_cols].copy()
    x["datetime_UTC"] = parse_local_to_utc(x["Timestamp"], "%Y-%m-%d", TZ)

    long = x.melt(
        id_vars=["datetime_UTC"],
        value_vars=mp_cols,
        var_name="source_variable",
        value_name="water_potential_kPa",
    )

    parts = long["source_variable"].str.extract(r"(?P<site_id>P\d+)_MP_(?P<depth_cm>\d+)")
    long["site_id"] = parts["site_id"]
    long["depth_m"] = pd.to_numeric(parts["depth_cm"], errors="coerce") / 100.0
    long["water_potential_kPa"] = pd.to_numeric(long["water_potential_kPa"], errors="coerce")
    long = long.dropna(subset=["water_potential_kPa"])

    long["replicate"] = 1
    long["is_timeseries"] = True
    long["volumetric_water_content_m3_m3"] = np.nan
    long["gravimetric_water_content_gH2O_gs"] = np.nan

    harmonized = ensure_harmonized_cols(long)
    harmonized = harmonized.sort_values(
        by=["datetime_UTC", "site_id", "depth_m", "replicate"]
    ).reset_index(drop=True)

    mdf = pd.read_csv(ds_path() / LOC_FILE, sep=";")
    loc = mdf.rename(
        columns={"ID": "site_id", "Latitude": "latitude", "Longitude": "longitude"}
    )[["site_id", "latitude", "longitude"]].copy()

    data_sites = pd.DataFrame({"site_id": sorted(harmonized["site_id"].unique())})
    loc = data_sites.merge(loc, on="site_id", how="left")
    loc["latitude"] = pd.to_numeric(loc["latitude"], errors="coerce")
    loc["longitude"] = pd.to_numeric(loc["longitude"], errors="coerce")
    loc["source_dataset_id"] = DSID
    loc["qc_flag"] = np.where(
        loc["latitude"].isna() | loc["longitude"].isna(), "g2", None
    )
    loc = loc[["site_id", "latitude", "longitude", "source_dataset_id", "qc_flag"]]

    return harmonized, loc


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    harmonized, loc = harmonize()
    harmonized.to_csv(OUT_DIR / f"{DSID}_harmonized.csv", index=False)
    loc.to_csv(OUT_DIR / f"{DSID}_location.csv", index=False)
    print("harmonized shape:", harmonized.shape)
    print(harmonized.head().to_string())
    print("location:")
    print(loc.to_string())
