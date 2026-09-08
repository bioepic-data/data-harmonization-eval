"""
Standalone runner for dataset 10 in the fold-evaluation workspace.

Reads the staged payload from inputs/raw/<dataset_identifier>/ and writes the
harmonized CSV and location CSV under output/. Mirrors output/dataset_10.py but
is self-contained (does not depend on data/gold/expert_code/common.py, whose
default paths point at a production layout not present in this workspace).
"""

from __future__ import annotations

from pathlib import Path
import re
import numpy as np
import pandas as pd

BASE_DIR = Path("inputs/raw")
OUT_DIR = Path("output")

DATASET_ID = "ess-dive-01092fc392bc46d-20240819T143818677"
IDX = 10
PAYLOAD = "Soil_water_content_Fig4e.csv"

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


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    ddf = pd.read_csv(BASE_DIR / DATASET_ID / PAYLOAD, skiprows=[1], encoding="utf-8-sig")

    x = ddf.copy()
    dt = pd.to_datetime(x["Date"], format="%Y-%m-%d", errors="coerce")
    x["datetime_UTC"] = dt.dt.tz_localize("UTC")
    x = x.drop(columns=["Date"])

    vwc_cols = [c for c in x.columns if re.search(r"vol_water_content", c)]

    long = x.melt(
        id_vars=["datetime_UTC"],
        value_vars=vwc_cols,
        var_name="name",
        value_name="volumetric_water_content_m3_m3",
    )
    long["site_id"] = long["name"].str.extract(r"(PLM\d+)")[0]
    long["volumetric_water_content_m3_m3"] = pd.to_numeric(
        long["volumetric_water_content_m3_m3"], errors="coerce"
    )
    long.loc[long["volumetric_water_content_m3_m3"] == -9999, "volumetric_water_content_m3_m3"] = np.nan
    long = long.dropna(subset=["volumetric_water_content_m3_m3"])

    long["depth_m"] = np.nan
    long["replicate"] = 1
    long["is_timeseries"] = True
    long["water_potential_kPa"] = np.nan
    long["gravimetric_water_content_gH2O_gs"] = np.nan

    harmonized = ensure_harmonized_cols(long)
    harmonized = harmonized.sort_values(
        by=["datetime_UTC", "site_id", "depth_m", "replicate"]
    ).reset_index(drop=True)
    harmonized["datetime_UTC"] = harmonized["datetime_UTC"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    out_file = OUT_DIR / f"{DATASET_ID}_harmonized.csv"
    harmonized.to_csv(out_file, index=False)

    loc = pd.DataFrame(
        {
            "site_id": sorted(long["site_id"].dropna().unique()),
            "latitude": np.nan,
            "longitude": np.nan,
        }
    )
    loc["source_dataset_id"] = DATASET_ID
    loc = add_loc_qc(loc)
    loc.to_csv(OUT_DIR / f"{DATASET_ID}_location.csv", index=False)

    print(f"Wrote {out_file} ({len(harmonized)} rows)")
    print(harmonized.head().to_string())
    print(f"Sites: {sorted(long['site_id'].dropna().unique())}")


if __name__ == "__main__":
    main()
