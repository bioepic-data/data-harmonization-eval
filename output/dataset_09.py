# %%
# =============================================================
# Dataset 9
# =============================================================
# Dataset: ess-dive-460e696d8210ed3-20260309T155937802
# DOI: doi:10.15485/3013006
#
# "Geophysical survey associated with NEON AOP survey, East River, CO 2018"
# Plot-level Time-Domain Reflectometry (TDR) soil moisture campaign.
#
# This is a self-contained fold-evaluation harmonizer. It reproduces the
# conventions of common.py (helper functions / schema) but runs standalone
# so it can read directly from inputs/raw and write to output/.

from __future__ import annotations

from pathlib import Path
import json

import numpy as np
import pandas as pd
from pyproj import Transformer

BASE_DIR = Path("inputs/raw")
OUT_DIR = Path("output")

idx = 9
DATASET_ID = "ess-dive-460e696d8210ed3-20260309T155937802"
DOI = "doi:10.15485/3013006"
PAYLOAD_FILE = "NEON_plot_TDR.csv"


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


def utm32613_to_latlon(df: pd.DataFrame, e_col: str, n_col: str) -> pd.DataFrame:
    tr = Transformer.from_crs("EPSG:32613", "EPSG:4326", always_xy=True)
    e = pd.to_numeric(df[e_col], errors="coerce").values
    n = pd.to_numeric(df[n_col], errors="coerce").values
    lon, lat = tr.transform(e, n)
    out = df.copy()
    out["longitude"] = lon
    out["latitude"] = lat
    return out


def harmonize():
    ddf = pd.read_csv(BASE_DIR / DATASET_ID / PAYLOAD_FILE)

    # --- datetime ---------------------------------------------------------
    # Collection dates are campaign dates (one per plot). No time-of-day is
    # reported; localize the date to the field timezone (America/Denver) and
    # convert to UTC. A few rows have a corrupted "Collection Date" cell
    # (spreadsheet "####" overflow); those coerce to NaT (documented in notes),
    # while their measurements are retained.
    dt_local = pd.to_datetime(ddf["Collection Date"], format="%Y-%m-%d", errors="coerce")
    dt_local = dt_local.dt.tz_localize(
        "America/Denver", ambiguous="NaT", nonexistent="shift_forward"
    )
    datetime_utc = dt_local.dt.tz_convert("UTC")

    base = pd.DataFrame(
        {
            "datetime_UTC": datetime_utc,
            "site_id": ddf["SampleSiteCode"].astype(str),
        }
    )

    # --- volumetric water content (wide -> long on replicate) -------------
    # VWC_1 and VWC_2 are the two readings per plot (the package reports three
    # readings averaged; only two per-reading columns plus avg_VWC are present).
    # Use the per-reading columns as replicates; drop the derived avg_VWC.
    for col, rep in [("VWC_1", 1), ("VWC_2", 2)]:
        base[col] = pd.to_numeric(ddf[col], errors="coerce")
    long = base.melt(
        id_vars=["datetime_UTC", "site_id"],
        value_vars=["VWC_1", "VWC_2"],
        var_name="rep_name",
        value_name="vwc_pct",
    )
    long["replicate"] = long["rep_name"].str.extract(r"_(\d+)$")[0].astype(int)

    # -9999 is the missing-value sentinel.
    long.loc[long["vwc_pct"] == -9999, "vwc_pct"] = np.nan
    long["volumetric_water_content_m3_m3"] = long["vwc_pct"] / 100.0

    # --- constant / metadata columns -------------------------------------
    long["is_timeseries"] = False  # one-time plot sampling campaign
    long["depth_m"] = 0.20  # TDR 20-cm probe length (methods); approximated
    long["gravimetric_water_content_gH2O_gs"] = np.nan
    long["water_potential_kPa"] = np.nan

    harmonized = ensure_harmonized_cols(long)
    # d1: depth approximated from reported probe length / methods.
    harmonized["qc_flag"] = "d1"

    # --- locations (UTM Zone 13N -> WGS84) --------------------------------
    loc_src = ddf[["SampleSiteCode", "Easting", "Northing"]].drop_duplicates(
        subset=["SampleSiteCode"]
    )
    loc_tmp = utm32613_to_latlon(loc_src, "Easting", "Northing")
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


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    harmonized, loc = harmonize()

    harmonized = harmonized[
        [
            "datetime_UTC",
            "site_id",
            "depth_m",
            "replicate",
            "is_timeseries",
            "volumetric_water_content_m3_m3",
            "gravimetric_water_content_gH2O_gs",
            "water_potential_kPa",
            "qc_flag",
        ]
    ].sort_values(by=["datetime_UTC", "site_id", "depth_m", "replicate"])
    harmonized.to_csv(OUT_DIR / f"{DATASET_ID}_harmonized.csv", index=False)

    loc = loc[
        ["site_id", "latitude", "longitude", "source_dataset_id", "qc_flag"]
    ].sort_values(by=["site_id"])
    loc.to_csv(OUT_DIR / f"{DATASET_ID}_location.csv", index=False)

    print(f"Wrote {DATASET_ID}_harmonized.csv ({len(harmonized)} rows)")
    print(f"Wrote {DATASET_ID}_location.csv ({len(loc)} rows)")


if __name__ == "__main__":
    main()
