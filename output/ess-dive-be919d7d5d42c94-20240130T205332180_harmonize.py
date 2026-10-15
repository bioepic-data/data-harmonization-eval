"""
Harmonization code for a single fold-evaluation target.

Dataset 17: ess-dive-be919d7d5d42c94-20240130T205332180
DOI: doi:10.15485/2283406
Title: Geophysical and Environmental Monitoring Data, and Subsurface Flow
       Modelling Results for Chicken Bone Meadow, Mt. Snodgrass, Crested Butte, CO

This is a self-contained adaptation of the project's modular expert pattern
(common.py + dataset_NN.py). Because the fold workspace stages raw files
directly under inputs/raw/<dataset_identifier>/ and does not ship the full
pipeline driver, the helpers normally imported from common.py are inlined here
verbatim and the dataset block mirrors the per-file + UTM pattern used by
dataset_01 / dataset_15 / dataset_16.

Follows SKILL.md Sections 1, 6, 7.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer

# -------------------------------------------------------------
# Paths
# -------------------------------------------------------------
BASE_DIR = Path("inputs/raw")
OUT_DIR = Path("output")
idx = 17
DATASET_ID = "ess-dive-be919d7d5d42c94-20240130T205332180"
DOI = "doi:10.15485/2283406"
SM_DIR = BASE_DIR / DATASET_ID / "FieldData" / "Soil_Moisture_Data"
DATA_FILES = ["TMC1.csv", "TMC2.csv", "TMC4.csv", "TMC5.csv", "TMC6.csv"]
LOCATION_FILE = "Locations.csv"


# -------------------------------------------------------------
# Helpers (inlined verbatim from expert common.py)
# -------------------------------------------------------------
def parse_local_to_utc(series: pd.Series, fmt: str | None, tz: str) -> pd.Series:
    dt = pd.to_datetime(series, format=fmt, errors="coerce")
    dt = dt.dt.tz_localize(tz, ambiguous="NaT", nonexistent="shift_forward")
    return dt.dt.tz_convert("UTC")


def utm32613_to_latlon(df: pd.DataFrame, e_col: str, n_col: str) -> pd.DataFrame:
    tr = Transformer.from_crs("EPSG:32613", "EPSG:4326", always_xy=True)
    e = pd.to_numeric(df[e_col], errors="coerce").values
    n = pd.to_numeric(df[n_col], errors="coerce").values
    lon, lat = tr.transform(e, n)
    out = df.copy()
    out["longitude"] = lon
    out["latitude"] = lat
    return out


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
# Dataset 17
# =============================================================
def harmonize() -> tuple[pd.DataFrame, pd.DataFrame]:
    __locations = []

    # Soil-moisture sensor files are wide-format hourly time series.
    # Row 0 of each file is a units row (V/V, degrees_Celsius, mS/cm);
    # skip it so numeric columns parse cleanly.
    ls = [
        pd.read_csv(SM_DIR / f, skiprows=[1], encoding="utf-8")
        for f in DATA_FILES
    ]

    ls_h = []
    for i, d in enumerate(ls):
        x = d.copy()
        # East River / Crested Butte sensor loggers report in fixed MST
        # (Etc/GMT+7); matches expert convention for hourly SFA time series.
        x["datetime_UTC"] = parse_local_to_utc(
            x["DateTime"], "%Y-%m-%d %H:%M:%S", "Etc/GMT+7"
        )

        # Only moisture-content columns map to the target schema.
        # T_* (temperature) and EC_* (electrical conductivity) are dropped.
        mc_cols = [c for c in x.columns if re.match(r"^MC_\d", c)]
        long = x.melt(
            id_vars=["datetime_UTC"],
            value_vars=mc_cols,
            var_name="name",
            value_name="volumetric_water_content_m3_m3",
        )

        # Depth embedded in column name "MC_0.1m" -> 0.1 m (already meters).
        long["depth_m"] = pd.to_numeric(
            long["name"].str.extract(r"MC_(\d+\.?\d*)m")[0], errors="coerce"
        )

        # site_id = filename stem (TMC1, TMC2, ...); matches Locations.csv ID.
        long["site_id"] = re.sub(r"\.csv$", "", DATA_FILES[i])
        long["replicate"] = 1
        long["is_timeseries"] = True

        # MC units are V/V = m3 m-3 already; no conversion required.
        long["volumetric_water_content_m3_m3"] = pd.to_numeric(
            long["volumetric_water_content_m3_m3"], errors="coerce"
        )
        long["gravimetric_water_content_gH2O_gs"] = np.nan
        long["water_potential_kPa"] = np.nan

        long = long[long["volumetric_water_content_m3_m3"].notna()]
        long = long[long["datetime_UTC"].notna()]

        ls_h.append(ensure_harmonized_cols(long))

    harmonized = pd.concat(ls_h, ignore_index=True)

    # -------------------------------------------------------------
    # Location resolution: coordinates in package ancillary file
    # (Locations.csv) in NAD83 / UTM Zone 13N -> reproject to WGS84.
    # Emit one row per data-bearing site_id. qc_flag resolved by add_loc_qc.
    # -------------------------------------------------------------
    mdf = pd.read_csv(BASE_DIR / DATASET_ID / LOCATION_FILE, encoding="utf-8")
    loc_tmp = utm32613_to_latlon(mdf, "Easting", "Northing")
    loc = pd.DataFrame(
        {
            "site_id": loc_tmp["ID"],
            "latitude": loc_tmp["latitude"],
            "longitude": loc_tmp["longitude"],
        }
    )
    # Keep only sites that appear in the harmonized payload.
    loc = loc[loc["site_id"].isin(harmonized["site_id"].dropna().unique())].drop_duplicates()
    loc["source_dataset_id"] = DATASET_ID
    loc = add_loc_qc(loc)
    __locations.append(loc)

    location = pd.concat(__locations, ignore_index=True) if __locations else pd.DataFrame()
    return harmonized, location


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    harmonized, location = harmonize()

    harmonized = harmonized.sort_values(
        by=["datetime_UTC", "site_id", "depth_m", "replicate"]
    )
    harmonized.to_csv(OUT_DIR / f"{DATASET_ID}_harmonized.csv", index=False)

    location = location[
        ["site_id", "latitude", "longitude", "source_dataset_id", "qc_flag"]
    ]
    location.to_csv(OUT_DIR / f"{DATASET_ID}_location.csv", index=False)

    print("harmonized rows:", len(harmonized))
    print("sites:", sorted(harmonized["site_id"].unique()))
    print("depths:", sorted(harmonized["depth_m"].dropna().unique()))
    print(location.to_string(index=False))


if __name__ == "__main__":
    main()
