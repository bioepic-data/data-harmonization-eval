"""
Dataset 26 harmonization.

Dataset: ess-dive-f782da867133296-20230504T211008637996

Discrete soil physical characterization campaign (East River watershed, 2018-2019).
The payload file ER18_soil_physical.csv reports one destructive soil sample per
SampleSiteCode with volumetric water content in percent, along with bulk density
and texture. This is a one-observation-per-site sampling campaign, not a sensor
time series.

Written for the grouped leave-one-cluster-out fold evaluation. Raw inputs are read
from inputs/raw/<dataset_identifier>/ and outputs are written under output/.
Helper functions mirror data/gold/expert_code/common.py; they are reproduced here so
the script is self-contained inside the run workspace.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path("inputs/raw")
OUT_DIR = Path("output")

DATASET_ID = "ess-dive-f782da867133296-20230504T211008637996"
IDX = 26
PAYLOAD_FILE = "ER18_soil_physical.csv"


def ensure_harmonized_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure all harmonized columns are present, in canonical order."""
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
    """Add QC flag for missing location data."""
    if "qc_flag" not in df.columns:
        df["qc_flag"] = np.where(
            df["latitude"].isna() | df["longitude"].isna(), "g2", None
        )
    return df


def parse_local_to_utc(series: pd.Series, fmt: str | None, tz: str) -> pd.Series:
    """Parse datetime series from local time to UTC."""
    dt = pd.to_datetime(series, format=fmt, errors="coerce")
    dt = dt.dt.tz_localize(tz, ambiguous="NaT", nonexistent="shift_forward")
    return dt.dt.tz_convert("UTC")


def harmonize() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Harmonize dataset 26."""
    ddf = pd.read_csv(BASE_DIR / DATASET_ID / PAYLOAD_FILE, encoding="utf-8")

    x = ddf.copy()

    x["datetime_UTC"] = parse_local_to_utc(
        x["Collection date"], "%m/%d/%y", "America/Denver"
    )

    x["site_id"] = x["SampleSiteCode"].astype(str)

    top = pd.to_numeric(x["Top sample depth_cm"], errors="coerce")
    bottom = pd.to_numeric(x["Bottom sample depth_cm"], errors="coerce")
    x["depth_m"] = ((top + bottom) / 2.0) / 100.0

    x["replicate"] = 1
    x["is_timeseries"] = False

    vwc = pd.to_numeric(x["water content %vol"], errors="coerce")
    vwc = vwc.mask(vwc == -9999.0)
    x["volumetric_water_content_m3_m3"] = (vwc / 100.0).round(4)

    x["gravimetric_water_content_gH2O_gs"] = np.nan
    x["water_potential_kPa"] = np.nan

    x = x[x["volumetric_water_content_m3_m3"].notna()].copy()

    x["qc_flag"] = "d1"

    harmonized = ensure_harmonized_cols(x)

    loc = pd.DataFrame(
        {
            "site_id": x["site_id"].unique(),
        }
    )
    loc["latitude"] = np.nan
    loc["longitude"] = np.nan
    loc["source_dataset_id"] = DATASET_ID
    loc = add_loc_qc(loc)

    return harmonized, loc


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    harmonized, loc = harmonize()

    harmonized = harmonized.sort_values(
        by=["datetime_UTC", "site_id", "depth_m", "replicate"]
    )

    out_file = OUT_DIR / f"{DATASET_ID}_harmonized.csv"
    harmonized.to_csv(out_file, index=False)
    loc.to_csv(OUT_DIR / f"{DATASET_ID}_location.csv", index=False)

    print(f"Wrote {out_file} ({len(harmonized)} rows)")
    print(f"Sites: {harmonized['site_id'].nunique()}")
    print(f"Depth (m) values: {sorted(harmonized['depth_m'].dropna().unique())}")


if __name__ == "__main__":
    main()
