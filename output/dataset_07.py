"""
Dataset 7 harmonization.

Dataset: ess-dive-38e901ec3d7bd24-20230504T211548257225

Fold-evaluation harmonization block for the held-out target dataset (index 7).

The staged package contains two files:
  - BM_Merged_T_VWC_0616_1018.csv : long-format hourly soil sensor output with an
    explicit "Volumetric Water Content" column (already in m3 m-3), an explicit
    "Depth (cm)" column, and a "date.time" timestamp. This is the measurement
    payload. There is no site column: the whole file is a single site ("BM").
  - BM_EGM_Well_CO2.csv : soil-CO2 (EGM well) measurements. This is NOT a soil
    moisture payload, but it is the only file in the package carrying the site
    coordinates (Location="BM", Latitude, Longitude), so it is used as the
    location source only.

Because this is a fold evaluation and dataset 7 is not present in the held-out-free
mapping JSON, files are read directly from inputs/raw/<dataset_identifier>/ rather
than via ctx.map_json[idx]. The transformation otherwise follows the SKILL.md
conventions and the long-format VWC exemplars (datasets 5 and 23).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path("inputs/raw")
OUT_DIR = Path("output")

DATASET_ID = "ess-dive-38e901ec3d7bd24-20230504T211548257225"
IDX = 7

DATA_FILE = "BM_Merged_T_VWC_0616_1018.csv"
LOC_FILE = "BM_EGM_Well_CO2.csv"


def parse_local_to_utc(series: pd.Series, fmt: str | None, tz: str) -> pd.Series:
    """Parse datetime series from local time to UTC (mirrors common.parse_local_to_utc)."""
    dt = pd.to_datetime(series, format=fmt, errors="coerce")
    dt = dt.dt.tz_localize(tz, ambiguous="NaT", nonexistent="shift_forward")
    return dt.dt.tz_convert("UTC")


def ensure_harmonized_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Enforce the harmonized column schema (mirrors common.ensure_harmonized_cols)."""
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
    """Add QC flag for missing location data (mirrors common.add_loc_qc)."""
    if "qc_flag" not in df.columns:
        df["qc_flag"] = np.where(
            df["latitude"].isna() | df["longitude"].isna(), "g2", None
        )
    return df


def harmonize():
    """Harmonize dataset 7."""
    ds_dir = BASE_DIR / DATASET_ID

    # %%
    # =============================================================
    # Dataset 7
    # =============================================================
    ddf = pd.read_csv(ds_dir / DATA_FILE)
    mdf = pd.read_csv(ds_dir / LOC_FILE, encoding="latin-1")

    x = ddf.copy()

    # Timestamps are local mountain time (Gunnison County, CO, ~-107 deg E).
    # Follow the exemplar convention of fixed-offset MST (Etc/GMT+7).
    x["datetime_UTC"] = parse_local_to_utc(x["date.time"], "%m/%d/%y %H:%M", "Etc/GMT+7")

    # Single site in the payload; the site identifier comes from the package
    # location file ("Location" == "BM").
    x["site_id"] = "BM"

    # Explicit depth column, in cm -> m.
    x["depth_m"] = pd.to_numeric(x["Depth (cm)"], errors="coerce") / 100.0

    # VWC already reported as a fraction (m3 m-3); no unit conversion needed.
    x["volumetric_water_content_m3_m3"] = pd.to_numeric(
        x["Volumetric Water Content"], errors="coerce"
    )
    x.loc[x["volumetric_water_content_m3_m3"] == -9999, "volumetric_water_content_m3_m3"] = np.nan

    x["water_potential_kPa"] = np.nan
    x["gravimetric_water_content_gH2O_gs"] = np.nan

    x["is_timeseries"] = True
    x["replicate"] = (
        x.groupby(["datetime_UTC", "site_id", "depth_m"]).cumcount().astype(int) + 1
    )

    x = x.sort_values(["site_id", "depth_m", "replicate", "datetime_UTC"])

    df_harmonized = ensure_harmonized_cols(x)

    # Location: coordinates from the (non-payload) CO2 file, keyed by site_id.
    # Column headers carry a degree symbol that varies by encoding, so match by
    # prefix rather than an exact literal.
    rename_map = {"Location": "site_id"}
    for c in mdf.columns:
        if c.startswith("Latitude"):
            rename_map[c] = "latitude"
        elif c.startswith("Longitude"):
            rename_map[c] = "longitude"
    loc = mdf.rename(columns=rename_map)
    loc = loc[["site_id", "latitude", "longitude"]].drop_duplicates(subset=["site_id"]).copy()
    loc = loc[loc["site_id"].isin(df_harmonized["site_id"].dropna().unique())]
    loc["source_dataset_id"] = DATASET_ID
    loc = add_loc_qc(loc)

    return df_harmonized, loc


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    harmonized, location = harmonize()

    out_data = harmonized.sort_values(
        by=["datetime_UTC", "site_id", "depth_m", "replicate"]
    )
    out_data.to_csv(OUT_DIR / f"{DATASET_ID}_harmonized.csv", index=False)
    location.to_csv(OUT_DIR / f"{DATASET_ID}_location.csv", index=False)

    print(f"Wrote {DATASET_ID}_harmonized.csv ({len(out_data)} rows)")
    print(f"Wrote {DATASET_ID}_location.csv ({len(location)} rows)")
