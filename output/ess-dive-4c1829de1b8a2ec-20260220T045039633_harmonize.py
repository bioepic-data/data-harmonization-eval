"""
Dataset 3 harmonization.

Dataset: ess-dive-4c1829de1b8a2ec-20260220T045039633
DOI: doi:10.15485/2998779

Soil water potential (matric potential) sensor logger output from the
north-facing hillslope sagebrush site near the East River pumphouse.
Five matric potential sensors are reported in wide format, with site and
depth encoded in the column names:

    SD11-25cm_MP                        -> site SD11, depth 0.25 m
    SD11-60cm_MP_2_Avg                  -> site SD11, depth 0.60 m
    SD1-25cm_MP_3_Avg                   -> site SD1,  depth 0.25 m
    SD1-60cm_MP_4_Avg                   -> site SD1,  depth 0.60 m
    SD1-25cm_sagebrush_rhizo_MP_5_Avg   -> site SD1,  depth 0.25 m (rhizosphere)

Values are soil matric potential in kPa (negative). The logger reports the
dryness-overrange sentinel -7999 and the error codes INF / NAN; all of these
are treated as missing.

This script is standalone (it does not import the expert `common.py` module)
so that it can be run directly inside the fold run workspace. The helper
functions below mirror the conventions in SECTION 6 / SECTION 7 of the
harmonizer skill.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path("inputs/raw")
OUT_DIR = Path("output")

idx = 3
DATASET_ID = "ess-dive-4c1829de1b8a2ec-20260220T045039633"
DOI = "doi:10.15485/2998779"

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

# Matric potential sensor columns -> (site_id, depth_m, replicate)
MP_COLUMNS = {
    "SD11-25cm_MP": ("SD11", 0.25, 1),
    "SD11-60cm_MP_2_Avg": ("SD11", 0.60, 1),
    "SD1-25cm_MP_3_Avg": ("SD1", 0.25, 1),
    "SD1-60cm_MP_4_Avg": ("SD1", 0.60, 1),
    "SD1-25cm_sagebrush_rhizo_MP_5_Avg": ("SD1", 0.25, 2),
}

# Logger sentinels / error codes treated as missing.
SENTINELS = {-7999.0, 7999.0, 9999.0, -9999.0}

# Dryness-overrange threshold (kPa). The MPS-6 / TEROS21 matric potential
# sensors used here saturate at their dry limit and report a dense cluster of
# values between roughly -6000 and -7999 kPa. Valid field readings span
# -1 to about -1000 kPa (tail to ~-2900 kPa) with an empty band between
# -3000 and -6000 kPa, so values at or below -3000 kPa are treated as
# overrange/invalid and set to missing.
OVERRANGE_KPA = -3000.0


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
    ds_dir = BASE_DIR / DATASET_ID
    ddf = pd.read_csv(ds_dir / "Soil_water_potential.csv")
    mdf = pd.read_csv(ds_dir / "locations.csv")

    mp_cols = list(MP_COLUMNS.keys())
    x = ddf[["TIMESTAMP"] + mp_cols].copy()

    # TIMESTAMP is CR1000 logger local time (Mountain Standard Time, no DST
    # offset). Convert from Etc/GMT+7 to UTC.
    dt = pd.to_datetime(x["TIMESTAMP"], format="%Y-%m-%d %H:%M", errors="coerce")
    dt = dt.dt.tz_localize("Etc/GMT+7", ambiguous="NaT", nonexistent="shift_forward")
    x["datetime_UTC"] = dt.dt.tz_convert("UTC")
    x = x.drop(columns=["TIMESTAMP"])

    long = x.melt(
        id_vars=["datetime_UTC"],
        value_vars=mp_cols,
        var_name="source_column",
        value_name="MP",
    )

    long["site_id"] = long["source_column"].map(lambda c: MP_COLUMNS[c][0])
    long["depth_m"] = long["source_column"].map(lambda c: MP_COLUMNS[c][1])
    long["replicate"] = long["source_column"].map(lambda c: MP_COLUMNS[c][2])

    wp = pd.to_numeric(long["MP"], errors="coerce")
    wp = wp.replace(list(SENTINELS), np.nan)
    wp[~np.isfinite(wp)] = np.nan
    wp[wp <= OVERRANGE_KPA] = np.nan
    long["water_potential_kPa"] = wp

    long["is_timeseries"] = True
    long["volumetric_water_content_m3_m3"] = np.nan
    long["gravimetric_water_content_gH2O_gs"] = np.nan

    long = long[long["water_potential_kPa"].notna()].copy()

    harmonized = ensure_harmonized_cols(long)

    # Location resolution: locations.csv provides a single coordinate for the
    # north-facing hillslope sagebrush sampling site. Apply it to every sensor
    # derived site_id (SD1, SD11), which the package describes as that site.
    lat = pd.to_numeric(mdf["Latitude"], errors="coerce").iloc[0]
    lon = pd.to_numeric(mdf["Longitude"], errors="coerce").iloc[0]
    site_ids = sorted(harmonized["site_id"].dropna().unique())
    loc = pd.DataFrame(
        {
            "site_id": site_ids,
            "latitude": lat,
            "longitude": lon,
        }
    )
    loc["source_dataset_id"] = DATASET_ID
    loc = add_loc_qc(loc)
    loc = loc[["site_id", "latitude", "longitude", "source_dataset_id", "qc_flag"]]

    return harmonized, loc


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    harmonized, loc = harmonize()

    harmonized = harmonized.sort_values(
        by=["datetime_UTC", "site_id", "depth_m", "replicate"]
    )
    harmonized.to_csv(OUT_DIR / f"{DATASET_ID}_harmonized.csv", index=False)
    loc.to_csv(OUT_DIR / f"{DATASET_ID}_location.csv", index=False)
    print(f"Wrote {DATASET_ID}_harmonized.csv ({len(harmonized)} rows)")
    print(f"Wrote {DATASET_ID}_location.csv ({len(loc)} rows)")


if __name__ == "__main__":
    main()
