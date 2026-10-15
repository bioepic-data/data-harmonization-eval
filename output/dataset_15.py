"""
Dataset 15 harmonization.

Dataset: ess-dive-987726ef1235abc-20230504T210342929747
DOI: doi:10.15485/1648526
Title: Time-domain reflectometer survey across the East River Watershed, Colorado

This module follows the modular expert-code pattern (common.py + dataset_NN.py).
It also runs standalone to emit the fold-evaluation deliverables under output/.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer

IDX = 15
DSID = "ess-dive-987726ef1235abc-20230504T210342929747"
DOI = "doi:10.15485/1648526"
PAYLOAD_FILE = "TDR_survey_ER_20190701.csv"

BASE_DIR = Path("inputs/raw")
OUT_DIR = Path("output")

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


def utm26913_to_latlon(df: pd.DataFrame, e_col: str, n_col: str) -> pd.DataFrame:
    # Metadata specifies EPSG:26913 (NAD83 / UTM zone 13N).
    tr = Transformer.from_crs("EPSG:26913", "EPSG:4326", always_xy=True)
    e = pd.to_numeric(df[e_col], errors="coerce").values
    n = pd.to_numeric(df[n_col], errors="coerce").values
    lon, lat = tr.transform(e, n)
    out = df.copy()
    out["longitude"] = lon
    out["latitude"] = lat
    return out


def harmonize(df_raw: pd.DataFrame):
    x = df_raw.copy()

    # site_id = GPS_id (stable per-point RTK-GPS identifier; unique per survey point).
    x["site_id"] = x["GPS_id"].astype(str)

    vwc_cols = ["TDR_SM(VWC%)_1", "TDR_SM(VWC%)_2", "TDR_SM(VWC%)_3"]
    for c in vwc_cols:
        x[c] = pd.to_numeric(x[c], errors="coerce")

    long = x.melt(
        id_vars=["site_id"],
        value_vars=vwc_cols,
        var_name="tmp",
        value_name="VWC",
    )
    long["replicate"] = long["tmp"].str.extract(r"_(\d+)$")[0].astype(int)
    long = long[long["VWC"].notna()].copy()

    # No per-row timestamp in payload; survey campaign (early July 2019) only.
    long["datetime_UTC"] = np.nan
    # Depth reported in package metadata as 25 cm (fixed probe length).
    long["depth_m"] = 0.25
    long["is_timeseries"] = False
    long["volumetric_water_content_m3_m3"] = long["VWC"] / 100.0
    long["gravimetric_water_content_gH2O_gs"] = np.nan
    long["water_potential_kPa"] = np.nan

    harmonized = ensure_harmonized_cols(long)
    harmonized = harmonized.sort_values(
        ["site_id", "depth_m", "replicate"]
    ).reset_index(drop=True)

    # Location: coordinates in the payload itself (UTM EPSG:26913).
    loc_src = x[["site_id", "Easting_m", "Northing_m"]].drop_duplicates(subset=["site_id"])
    loc_tmp = utm26913_to_latlon(loc_src, "Easting_m", "Northing_m")
    loc = pd.DataFrame(
        {
            "site_id": loc_tmp["site_id"].values,
            "latitude": loc_tmp["latitude"].values,
            "longitude": loc_tmp["longitude"].values,
        }
    )
    loc["source_dataset_id"] = DSID
    loc = add_loc_qc(loc)
    loc = loc[["site_id", "latitude", "longitude", "source_dataset_id", "qc_flag"]]
    loc = loc.sort_values("site_id").reset_index(drop=True)

    return harmonized, loc


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df_raw = pd.read_csv(BASE_DIR / DSID / PAYLOAD_FILE)
    harmonized, loc = harmonize(df_raw)

    harmonized.to_csv(OUT_DIR / f"{DSID}_harmonized.csv", index=False)
    loc.to_csv(OUT_DIR / f"{DSID}_location.csv", index=False)
    print(f"Wrote {DSID}_harmonized.csv ({len(harmonized)} rows)")
    print(f"Wrote {DSID}_location.csv ({len(loc)} rows)")


if __name__ == "__main__":
    main()
