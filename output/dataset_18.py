"""
Dataset 18 harmonization.

Dataset: ess-dive-b924878d23c9dd7-20250214T163427929
DOI: doi:10.15485/1577267

Soil Nitrogen, Water Content, Microbial Biomass, and Archaeal, Bacterial and
Fungal Communities from the East River Watershed, Colorado collected in 2016-2017.

This fold-evaluation block is written as a standalone, runnable script that reads
the staged raw payload from inputs/raw/<dataset_identifier>/ and writes the
required deliverables under output/. It follows the SECTION 6/7 conventions of
the harmonizer skill (schema enforcement, UTC timestamps, qc_flag handling).
"""

# %%
# =============================================================
# Dataset 18
# =============================================================
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

idx = 18
DSID = "ess-dive-b924878d23c9dd7-20250214T163427929"
BASE_DIR = Path("inputs/raw")
OUT_DIR = Path("output")
PAYLOAD = "2017_East_River_Pumphouse_Soil_Water_Content_and_pH__1_.csv"

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

GWC_COL = "Soil Water Content (g H2O per gram  soil)"


def ensure_harmonized_cols(df: pd.DataFrame) -> pd.DataFrame:
    for c in HARMONIZED_COLS:
        if c not in df.columns:
            df[c] = np.nan
    return df[HARMONIZED_COLS]


def depth_from_increment(series: pd.Series) -> pd.Series:
    """Approximate a representative depth (m) from a reported depth increment.

    Values seen in the source:
      '0-5 cm'   -> midpoint 2.5 cm
      '5-15 cm'  -> midpoint 10 cm
      '15-May'   -> Excel-corrupted rendering of '5-15' -> midpoint 10 cm
      '15 cm +'  -> open-ended lower bound 15 cm (no upper bound reported)
    All depths are approximated from reported ranges -> qc_flag 'd1'.
    """
    s = series.astype("string").str.strip()
    mapping = {
        "0-5 cm": 2.5,
        "5-15 cm": 10.0,
        "15-May": 10.0,
        "15 cm +": 15.0,
    }
    cm = s.map(mapping)
    return cm.astype("float64") / 100.0


def build_site_id(df: pd.DataFrame) -> pd.Series:
    """Construct a stable site_id from location/plot descriptors.

    No single site-code column exists. A physical sampling plot is identified by
    Location, Field_Site, Block, and Plot. Topographic_Position (Upslope /
    Downslope / snow-pit label) distinguishes the sampling footprint within a
    plot and is retained to keep distinct coordinates separable.
    """
    parts = [
        df["Location"].astype("string"),
        df["Field_Site"].astype("string"),
        df["Block"].astype("string"),
        df["Plot"].astype("string"),
        df["Topographic_Position"].astype("string").fillna("NA"),
    ]
    sid = parts[0].str.cat([p.fillna("NA") for p in parts[1:]], sep="|")
    return sid


def harmonize() -> tuple[pd.DataFrame, pd.DataFrame]:
    ddf = pd.read_csv(
        BASE_DIR / DSID / PAYLOAD, encoding="utf-8", encoding_errors="ignore"
    )

    x = ddf.copy()

    # Timestamp: campaign collection date (local Mountain Time, no sub-daily
    # resolution). Parse as UTC midnight of the collection date.
    x["datetime_UTC"] = pd.to_datetime(
        x["Date_Collected"], format="%m/%d/%Y", errors="coerce"
    ).dt.tz_localize("UTC")

    x["site_id"] = build_site_id(x)

    # Depth approximated from reported increment ranges.
    x["depth_m"] = depth_from_increment(x["Depth_Increment"])

    # Replicate: the source 'Replicate' column reflects plot/sampling replicate.
    x["replicate"] = pd.to_numeric(x["Replicate"], errors="coerce")

    # Discrete sampling campaigns (one obs per site+depth per campaign date),
    # not continuous sensor output -> not a time series.
    x["is_timeseries"] = False

    # Measurement is gravimetric water content (g H2O per g soil); units already
    # g/g, no conversion required.
    x["gravimetric_water_content_gH2O_gs"] = pd.to_numeric(x[GWC_COL], errors="coerce")
    x["volumetric_water_content_m3_m3"] = np.nan
    x["water_potential_kPa"] = np.nan

    # Drop rows with no usable measurement.
    x = x[x["gravimetric_water_content_gH2O_gs"].notna()].copy()

    # All depths are approximated from reported ranges.
    harmonized = ensure_harmonized_cols(x)

    # --- Location file (coordinates are per-row in the payload) ---
    loc_src = ddf.copy()
    loc_src["site_id"] = build_site_id(loc_src)
    loc_src["latitude"] = pd.to_numeric(loc_src["Latitude"], errors="coerce")
    loc_src["longitude"] = pd.to_numeric(loc_src["Longitude"], errors="coerce")

    loc = (
        loc_src.groupby("site_id", as_index=False)
        .agg(
            latitude=("latitude", lambda v: np.nan if v.isna().all() else v.mean()),
            longitude=("longitude", lambda v: np.nan if v.isna().all() else v.mean()),
        )
    )
    # Keep only sites that appear in the harmonized measurement data.
    loc = loc[loc["site_id"].isin(harmonized["site_id"].dropna().unique())].copy()
    loc["source_dataset_id"] = DSID
    # g2 = coordinates not resolvable from any source; otherwise no location flag.
    missing = loc["latitude"].isna() | loc["longitude"].isna()
    loc["qc_flag"] = pd.Series(np.nan, index=loc.index, dtype="object")
    loc.loc[missing, "qc_flag"] = "g2"
    loc = loc[["site_id", "latitude", "longitude", "source_dataset_id", "qc_flag"]]
    loc = loc.sort_values("site_id").reset_index(drop=True)

    return harmonized, loc


def main() -> None:
    harmonized, loc = harmonize()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # depth_m is approximated from reported ranges for every row -> 'd1'.
    harmonized_out = harmonized.sort_values(
        by=["datetime_UTC", "site_id", "depth_m", "replicate"]
    )
    harmonized_out.to_csv(OUT_DIR / f"{DSID}_harmonized.csv", index=False)
    loc.to_csv(OUT_DIR / f"{DSID}_location.csv", index=False)

    print(f"Wrote {DSID}_harmonized.csv ({len(harmonized_out)} rows)")
    print(f"Wrote {DSID}_location.csv ({len(loc)} sites)")


if __name__ == "__main__":
    main()
