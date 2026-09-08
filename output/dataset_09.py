"""
Dataset 9 harmonization.

Dataset: ess-dive-460e696d8210ed3-20260309T155937802
DOI: (not available in staged workspace)

Structural twin of dataset 15 (ER TDR survey) and dataset 26 (ER18 plots):
discrete field campaign, VWC reported in percent, UTM Zone 13N coordinates
embedded in the payload, two TDR replicate readings per plot.

Self-contained: reads the staged raw file directly and reimplements the
minimal helper logic from data/gold/expert_code/common.py, because the shared
Context.base_dir in that module points at a directory not present in this fold
workspace.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer


BASE_DIR = Path("inputs/raw")
OUT_DIR = Path("output")

idx = 9
DATASET_ID = "ess-dive-460e696d8210ed3-20260309T155937802"
PAYLOAD_FILE = "NEON_plot_TDR.csv"

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


def utm32613_to_latlon(df: pd.DataFrame, e_col: str, n_col: str) -> pd.DataFrame:
    """Convert UTM Zone 13N coordinates to lat/lon (EPSG:32613 -> EPSG:4326)."""
    tr = Transformer.from_crs("EPSG:32613", "EPSG:4326", always_xy=True)
    e = pd.to_numeric(df[e_col], errors="coerce").values
    n = pd.to_numeric(df[n_col], errors="coerce").values
    lon, lat = tr.transform(e, n)
    out = df.copy()
    out["longitude"] = lon
    out["latitude"] = lat
    return out


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


def harmonize() -> tuple[pd.DataFrame, pd.DataFrame]:
    ddf = pd.read_csv(BASE_DIR / DATASET_ID / PAYLOAD_FILE)

    # Treat sentinel -9999 as missing across measurement columns.
    ddf = ddf.replace(-9999, np.nan)

    x = ddf.copy()

    # Discrete sampling campaign: one collection date per plot.
    x["datetime_UTC"] = pd.to_datetime(
        x["Collection Date"], format="%Y-%m-%d", errors="coerce"
    ).dt.tz_localize("UTC")
    x["site_id"] = x["SampleSiteCode"].astype(str)
    # Near-surface TDR reading; depth not reported in the payload -> NA.
    x["depth_m"] = np.nan
    x["is_timeseries"] = False

    # Wide -> long: VWC_1 and VWC_2 are two replicate TDR readings per plot.
    long = x.melt(
        id_vars=["datetime_UTC", "site_id", "depth_m", "is_timeseries"],
        value_vars=["VWC_1", "VWC_2"],
        var_name="name",
        value_name="volumetric_water_content_m3_m3",
    )
    long["replicate"] = pd.to_numeric(
        long["name"].str.extract(r"_(\d+)$")[0], errors="coerce"
    ).astype("Int64")
    long["volumetric_water_content_m3_m3"] = (
        pd.to_numeric(long["volumetric_water_content_m3_m3"], errors="coerce") / 100.0
    ).round(4)
    long["gravimetric_water_content_gH2O_gs"] = np.nan
    long["water_potential_kPa"] = np.nan

    harmonized = ensure_harmonized_cols(long)

    # Location: UTM Zone 13N -> lat/lon, one coordinate per plot.
    mdf = ddf[["SampleSiteCode", "Easting", "Northing"]].drop_duplicates()
    loc_tmp = utm32613_to_latlon(mdf, "Easting", "Northing")
    loc = pd.DataFrame(
        {
            "site_id": loc_tmp["SampleSiteCode"].astype(str),
            "latitude": loc_tmp["latitude"],
            "longitude": loc_tmp["longitude"],
        }
    )
    loc["source_dataset_id"] = DATASET_ID
    loc = add_loc_qc(loc)

    return harmonized, loc


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
