# %%
# =============================================================
# Dataset 8
# =============================================================
# Dataset: ess-dive-61a0ecd70856892-20230808T205724993
# DOI: doi:10.15485/1958210
#
# Standalone harmonization script for the fold evaluation run
# environment. Reads staged raw inputs from inputs/raw/<id>/ and
# writes deliverables to output/. Follows the wfsfa_sm_harmonization
# skill Section 6 conventions; helper functions are inlined so the
# script runs without the modular expert `common.py` (whose paths
# differ from this run environment).
from __future__ import annotations

from pathlib import Path
import re

import numpy as np
import pandas as pd

BASE_DIR = Path("inputs/raw")
OUT_DIR = Path("output")

idx = 8
DSID = "ess-dive-61a0ecd70856892-20230808T205724993"


# -------------------------------------------------------------
# Inlined helpers (mirror common.py behaviour)
# -------------------------------------------------------------
def ds_path(dataset_id: str) -> Path:
    return BASE_DIR / dataset_id


def read_ds_csv(dataset_id: str, filename: str, **kwargs) -> pd.DataFrame:
    return pd.read_csv(ds_path(dataset_id) / filename, encoding="utf-8", **kwargs)


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


# -------------------------------------------------------------
# Harmonization
# -------------------------------------------------------------
# One monitoring station (Slate River OBJ2). Four yearly wide-format
# sensor files share a common schema: depth is embedded in the column
# name (e.g. SoilMoisture_40cm.m3.m3, SoilMatricPot_79cm.kPa) and the
# site identity is implicit (one site for the whole package).
DATA_FILES = [
    "SLT_OBJ2_SoilSensors_2018_data.csv",
    "SLT_OBJ2_SoilSensors_2019_data.csv",
    "SLT_OBJ2_SoilSensors_2020_data.csv",
    "SLT_OBJ2_SoilSensors_2021_data.csv",
]
META_FILES = [
    "SLT_OBJ2_SoilSensors_2018_InstallationMethods.csv",
    "SLT_OBJ2_SoilSensors_2019_InstallationMethods.csv",
    "SLT_OBJ2_SoilSensors_2020_InstallationMethods.csv",
    "SLT_OBJ2_SoilSensors_2021_InstallationMethods.csv",
]

SITE_ID = "SLT_OBJ2"
SENTINEL = -9999

harmonized_parts = []
for fname in DATA_FILES:
    d = read_ds_csv(DSID, fname)

    # Keep only VWC (SoilMoisture_*cm.m3.m3) and matric potential
    # (SoilMatricPot_*cm.kPa) columns alongside the timestamp.
    sm_cols = [c for c in d.columns if re.match(r"SoilMoisture_.*\.m3\.m3$", c)]
    wp_cols = [c for c in d.columns if re.match(r"SoilMatricPot_.*\.kPa$", c)]
    keep = ["DateTime.MST"] + sm_cols + wp_cols
    x = d[keep].copy()

    # DateTime.MST is local Mountain Standard Time (no DST), i.e. UTC-7.
    x["datetime_UTC"] = parse_local_to_utc(x["DateTime.MST"], "%Y-%m-%d %H:%M:%S", "Etc/GMT+7")
    x = x.drop(columns=["DateTime.MST"])

    long = x.melt(id_vars=["datetime_UTC"], var_name="name", value_name="value")

    # Variable type and depth parsed from the column name.
    long["dest_var"] = np.where(
        long["name"].str.startswith("SoilMoisture_"),
        "volumetric_water_content_m3_m3",
        np.where(
            long["name"].str.startswith("SoilMatricPot_"),
            "water_potential_kPa",
            "",
        ),
    )
    long = long[long["dest_var"] != ""]

    long["depth_m"] = pd.to_numeric(
        long["name"].str.extract(r"_(\d+\.?\d*)cm")[0], errors="coerce"
    ) / 100.0

    long["value"] = pd.to_numeric(long["value"], errors="coerce")
    long.loc[long["value"] == SENTINEL, "value"] = np.nan
    long = long.dropna(subset=["value"])

    # A single sensor per depth/variable (no replicate encoding in source).
    long["replicate"] = long.groupby(
        ["datetime_UTC", "depth_m", "dest_var"]
    ).cumcount() + 1

    wide = long.pivot_table(
        index=["datetime_UTC", "depth_m", "replicate"],
        columns="dest_var",
        values="value",
        aggfunc="first",
    ).reset_index()

    wide["site_id"] = SITE_ID
    wide["replicate"] = wide["replicate"].astype(int)
    wide["is_timeseries"] = True
    wide["gravimetric_water_content_gH2O_gs"] = np.nan

    harmonized_parts.append(ensure_harmonized_cols(wide))

df_harmonized = pd.concat(harmonized_parts, ignore_index=True)
df_harmonized = df_harmonized.sort_values(
    by=["datetime_UTC", "site_id", "depth_m", "replicate"]
).reset_index(drop=True)

# -------------------------------------------------------------
# Location: coordinates supplied in the InstallationMethods files
# (identical across all rows/years) and confirmed by the package
# spatialCoverage record. A single site -> single row.
# -------------------------------------------------------------
mdf = read_ds_csv(DSID, META_FILES[0])
lat = pd.to_numeric(mdf["Latitude"], errors="coerce").dropna().unique()
lon = pd.to_numeric(mdf["Longitude"], errors="coerce").dropna().unique()

loc = pd.DataFrame(
    {
        "site_id": [SITE_ID],
        "latitude": [lat[0] if len(lat) else np.nan],
        "longitude": [lon[0] if len(lon) else np.nan],
    }
)
loc["source_dataset_id"] = DSID
loc = add_loc_qc(loc)
loc = loc[["site_id", "latitude", "longitude", "source_dataset_id", "qc_flag"]]


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df_harmonized.to_csv(OUT_DIR / f"{DSID}_harmonized.csv", index=False)
    loc.to_csv(OUT_DIR / f"{DSID}_location.csv", index=False)
    print(f"Wrote {DSID}_harmonized.csv ({len(df_harmonized)} rows)")
    print(f"Wrote {DSID}_location.csv ({len(loc)} rows)")
