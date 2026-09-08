"""
Dataset 18 harmonization.

Dataset: ess-dive-b924878d23c9dd7-20250214T163427929
Title:   2017 East River Pumphouse Soil Water Content and pH

Discrete soil sampling campaign reporting gravimetric soil water content
(g H2O per gram soil) and soil pH across three depth increments at several
East River and Washington Gulch field sites (2016-2017).

Run as a standalone fold-evaluation script:
    python output/dataset_18.py

Follows the schema and code conventions in
skills/essdive_sm_harmonizer/SKILL.md.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path("inputs/raw")
OUT_DIR = Path("output")

IDX = 18
DATASET_ID = "ess-dive-b924878d23c9dd7-20250214T163427929"
PAYLOAD_FILE = "2017_East_River_Pumphouse_Soil_Water_Content_and_pH__1_.csv"

# Depth increments reported as ranges (cm). "15-May" is an Excel autocorrect
# artifact for the "5-15 cm" increment. "15 cm +" is an open-ended lower
# increment whose depth is approximated by its reported upper bound (15 cm).
DEPTH_MIDPOINT_CM = {
    "0-5 cm": 2.5,
    "5-15 cm": 10.0,
    "15-May": 10.0,
    "15 cm +": 15.0,
}


def clean_coord(series: pd.Series) -> pd.Series:
    """Strip stray non-numeric bytes (e.g. \\xa0, replacement chars) and coerce."""
    cleaned = series.astype(str).str.replace(r"[^0-9.\-]", "", regex=True)
    return pd.to_numeric(cleaned, errors="coerce")


def ensure_harmonized_cols(df: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "datetime_UTC",
        "site_id",
        "depth_m",
        "replicate",
        "is_timeseries",
        "interval_min",
        "volumetric_water_content_m3_m3",
        "gravimetric_water_content_gH2O_gs",
        "water_potential_kPa",
        "qc_flag",
    ]
    for c in cols:
        if c not in df.columns:
            df[c] = np.nan
    return df[cols]


def harmonize() -> tuple[pd.DataFrame, pd.DataFrame]:
    path = BASE_DIR / DATASET_ID / PAYLOAD_FILE
    ddf = pd.read_csv(path, encoding="utf-8", encoding_errors="ignore")

    wc_col = [c for c in ddf.columns if "Water Content" in c][0]

    x = ddf.copy()

    # site_id: Location + Field_Site + Plot (stable, location-traceable identifier)
    x["site_id"] = (
        x["Location"].astype(str)
        + "_"
        + x["Field_Site"].astype(str)
        + "_"
        + x["Plot"].astype(str)
    )

    # datetime: discrete campaign dates (date only, no time-of-day reported).
    # Parse in Mountain Standard Time (fixed UTC-7) and convert to UTC.
    x["datetime_UTC"] = (
        pd.to_datetime(x["Date_Collected"], format="%m/%d/%Y", errors="coerce")
        .dt.tz_localize("Etc/GMT+7")
        .dt.tz_convert("UTC")
    )

    # depth: midpoint of reported depth increment (approximated -> qc_flag d1)
    x["depth_m"] = x["Depth_Increment"].map(DEPTH_MIDPOINT_CM) / 100.0

    # replicate
    x["replicate"] = pd.to_numeric(x["Replicate"], errors="coerce")

    x["is_timeseries"] = False
    x["interval_min"] = np.nan

    # gravimetric water content (source units already g H2O / g soil)
    x["gravimetric_water_content_gH2O_gs"] = pd.to_numeric(x[wc_col], errors="coerce")
    x["volumetric_water_content_m3_m3"] = np.nan
    x["water_potential_kPa"] = np.nan

    # depth increments are ranges -> depth approximated
    x["qc_flag"] = "d1"

    # drop rows with no gravimetric water content measurement
    x = x[x["gravimetric_water_content_gH2O_gs"].notna()].copy()

    harmonized = ensure_harmonized_cols(x)

    # ---- location accumulator ----
    loc_src = ddf.copy()
    loc_src["site_id"] = (
        loc_src["Location"].astype(str)
        + "_"
        + loc_src["Field_Site"].astype(str)
        + "_"
        + loc_src["Plot"].astype(str)
    )
    loc_src["latitude"] = clean_coord(loc_src["Latitude"])
    loc_src["longitude"] = clean_coord(loc_src["Longitude"])

    # median coordinate per site (robust to per-campaign GPS variation and
    # occasional truncated/garbled entries)
    loc = (
        loc_src.groupby("site_id", as_index=False)
        .agg(latitude=("latitude", "median"), longitude=("longitude", "median"))
    )
    loc["source_dataset_id"] = DATASET_ID
    # g2 where coordinates are unresolvable (e.g. Upper_Montane sites)
    loc["qc_flag"] = np.where(
        loc["latitude"].isna() | loc["longitude"].isna(), "g2", None
    )

    return harmonized, loc


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    harmonized, loc = harmonize()

    harmonized = harmonized.sort_values(
        by=["datetime_UTC", "site_id", "depth_m", "replicate"]
    )

    out_data = OUT_DIR / f"{DATASET_ID}_harmonized.csv"
    out_loc = OUT_DIR / f"{DATASET_ID}_location.csv"
    harmonized.to_csv(out_data, index=False)
    loc.to_csv(out_loc, index=False)

    print(f"Wrote {out_data} ({len(harmonized)} rows)")
    print(f"Wrote {out_loc} ({len(loc)} sites; "
          f"{int((loc['qc_flag'] == 'g2').sum())} unresolved)")


if __name__ == "__main__":
    main()
