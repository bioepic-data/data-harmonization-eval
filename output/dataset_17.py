"""
Dataset 17 harmonization.

Dataset: ess-dive-be919d7d5d42c94-20240130T205332180
DOI: not available in run workspace (no cached ESS-DIVE metadata supplied)

Wide-format hourly soil moisture time series. Each payload file (TMCn.csv)
is one site. Columns encode moisture content (MC), temperature (T), and
electrical conductivity (EC) at four depths (0.1, 0.3, 0.6, 0.8 m). Only
moisture content is harmonized (-> volumetric_water_content_m3_m3). Site
coordinates are provided in Locations.csv as UTM Zone 13N (EPSG:32613) and
are reprojected to WGS84 lat/lon.

Structurally analogous to dataset 1 (per-file site_id, wide-to-long melt with
depth embedded in column names, UTM Zone 13N location file).

Runnable standalone: reads from inputs/raw/<dataset_id>/ and writes harmonized
CSV + location CSV to output/.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer

BASE_DIR = Path("inputs/raw")
OUT_DIR = Path("output")

DATASET_ID = "ess-dive-be919d7d5d42c94-20240130T205332180"
IDX = 17

DATA_SUBDIR = Path("FieldData") / "Soil_Moisture_Data"
DATA_FILES = ["TMC1.csv", "TMC2.csv", "TMC4.csv", "TMC5.csv", "TMC6.csv"]
LOCATION_FILE = "Locations.csv"

LOCAL_TZ = "Etc/GMT+7"  # Mountain Standard Time (no DST); Colorado site, matches exemplar dataset 1

HARMONIZED_COLS = [
    "datetime_UTC",
    "site_id",
    "depth_m",
    "replicate",
    "is_timeseries",
    "interval_min",
    "volumetric_water_content_m3_m3",
    "gravimetric_water_content_gH2O_gs",
    "water_potential_kPa",
]


def parse_local_to_utc(series: pd.Series, fmt: str | None, tz: str) -> pd.Series:
    dt = pd.to_datetime(series, format=fmt, errors="coerce")
    dt = dt.dt.tz_localize(tz, ambiguous="NaT", nonexistent="shift_forward")
    return dt.dt.tz_convert("UTC")


def utm32613_to_latlon(df: pd.DataFrame, e_col: str, n_col: str) -> pd.DataFrame:
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
    ds_dir = BASE_DIR / DATASET_ID

    per_file = []
    for fname in DATA_FILES:
        # Row index 1 is a units row (V/V, degrees_Celsius, mS/cm); skip it.
        d = pd.read_csv(ds_dir / DATA_SUBDIR / fname, skiprows=[1])

        mc_cols = [c for c in d.columns if re.match(r"^MC_", c)]
        x = d[["DateTime"] + mc_cols].copy()

        x["datetime_UTC"] = parse_local_to_utc(
            x["DateTime"], "%Y-%m-%d %H:%M:%S", LOCAL_TZ
        )
        x = x.drop(columns=["DateTime"])

        long = x.melt(
            id_vars=["datetime_UTC"],
            var_name="name",
            value_name="volumetric_water_content_m3_m3",
        )

        # Depth embedded in column name in meters: MC_0.1m -> 0.1
        long["depth_m"] = pd.to_numeric(
            long["name"].str.extract(r"MC_(\d+\.?\d*)m")[0], errors="coerce"
        )

        long["volumetric_water_content_m3_m3"] = pd.to_numeric(
            long["volumetric_water_content_m3_m3"], errors="coerce"
        )
        long.loc[long["volumetric_water_content_m3_m3"] == -9999, "volumetric_water_content_m3_m3"] = np.nan
        long = long.dropna(subset=["volumetric_water_content_m3_m3"])

        long["site_id"] = re.sub(r"\.csv$", "", fname)
        long["replicate"] = 1
        long["is_timeseries"] = True
        long["interval_min"] = 60.0
        long["gravimetric_water_content_gH2O_gs"] = np.nan
        long["water_potential_kPa"] = np.nan

        per_file.append(ensure_harmonized_cols(long))

    harmonized = pd.concat(per_file, ignore_index=True)

    # Locations: keep only the soil moisture sites present in the payload.
    mdf = pd.read_csv(ds_dir / LOCATION_FILE)
    mdf = mdf[mdf["ID"].isin(harmonized["site_id"].unique())].copy()
    loc_tmp = utm32613_to_latlon(mdf, "Easting", "Northing")
    loc = pd.DataFrame(
        {
            "site_id": loc_tmp["ID"],
            "latitude": loc_tmp["latitude"],
            "longitude": loc_tmp["longitude"],
        }
    )
    loc["source_dataset_id"] = DATASET_ID
    loc = add_loc_qc(loc)

    return harmonized, loc


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    harmonized, loc = harmonize()

    harmonized = harmonized.sort_values(
        by=["datetime_UTC", "site_id", "depth_m", "replicate"]
    ).reset_index(drop=True)

    out_csv = OUT_DIR / f"{DATASET_ID}_harmonized.csv"
    harmonized.to_csv(out_csv, index=False)
    print(f"Wrote {out_csv} ({len(harmonized)} rows)")

    loc_csv = OUT_DIR / f"{DATASET_ID}_location_data.csv"
    loc.to_csv(loc_csv, index=False)
    print(f"Wrote {loc_csv} ({len(loc)} rows)")


if __name__ == "__main__":
    main()
