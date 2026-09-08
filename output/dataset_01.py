"""
Dataset 1 harmonization (fold-01 target).

Dataset: ess-dive-beca0be9bb38ece-20250516T122010234
DOI: doi:10.15485/2566877

Wide-format soil moisture sensor time series from the East River watershed
(Colorado). Each logger file (ER_SM*.csv) has a "Time" column plus wide
measurement columns whose names encode variable, an optional replicate index,
and depth, e.g.:

    m3_m3_Water_Content_at_10cm        -> VWC (m3/m3),  depth 0.10 m
    m3_m3_Water_Content_2_at_35cm      -> VWC (m3/m3),  depth 0.35 m, rep 2
    m3_m3_VWC_1_at_10cm                -> VWC (m3/m3),  depth 0.10 m, rep 1
    kPa_Potential_at_40cm              -> water potential (kPa), depth 0.40 m
    kPa_Potential_1_at_10cm            -> water potential (kPa), depth 0.10 m, rep 1

site_id is the logger name embedded in the filename (== Sensor_Location.csv Name).
Coordinates are UTM Zone 13N (EPSG:32613) in Sensor_Location.csv.

This module follows the SKILL.md conventions and reuses the helper patterns
from data/gold/expert_code/common.py. It is self-contained: because the target
dataset is held out of the mapping JSON in a fold evaluation, file paths are read
directly from inputs/raw/<identifier>/ rather than via a mapping-index lookup.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer

BASE_DIR = Path("inputs/raw")
OUT_DIR = Path("output")

idx = 1
DATASET_ID = "ess-dive-beca0be9bb38ece-20250516T122010234"
DOI = "doi:10.15485/2566877"

DS_DIR = BASE_DIR / DATASET_ID
LOCATION_FILE = "Sensor_Location.csv"

# Logger name -> local timezone. East River, CO -> Mountain Standard Time.
LOCAL_TZ = "America/Denver"

# Wide measurement column pattern:
#   <units>_<variable>[_<rep>]_at_<depth>cm
# units:    m3_m3 (VWC) or kPa (potential)
# variable: Water_Content | VWC | Potential
# rep:      optional integer sensor index
# depth:    integer cm
COL_RE = re.compile(
    r"^(?P<units>m3_m3|kPa)_(?P<var>Water_Content|VWC|Potential)"
    r"(?:_(?P<rep>\d+))?_at_(?P<depth>\d+)cm$"
)


def parse_local_to_utc(series: pd.Series, fmt: str | None, tz: str) -> pd.Series:
    """Parse datetime series from local time to UTC (see common.py)."""
    dt = pd.to_datetime(series, format=fmt, errors="coerce")
    dt = dt.dt.tz_localize(tz, ambiguous="NaT", nonexistent="shift_forward")
    return dt.dt.tz_convert("UTC")


def utm32613_to_latlon(df: pd.DataFrame, e_col: str, n_col: str) -> pd.DataFrame:
    """Convert UTM Zone 13N coordinates to lat/lon (see common.py)."""
    tr = Transformer.from_crs("EPSG:32613", "EPSG:4326", always_xy=True)
    e = pd.to_numeric(df[e_col], errors="coerce").values
    n = pd.to_numeric(df[n_col], errors="coerce").values
    lon, lat = tr.transform(e, n)
    out = df.copy()
    out["longitude"] = lon
    out["latitude"] = lat
    return out


def ensure_harmonized_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Enforce the target column schema and order (see common.py)."""
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
    """Add QC flag for missing location data (see common.py)."""
    if "qc_flag" not in df.columns:
        df["qc_flag"] = np.where(
            df["latitude"].isna() | df["longitude"].isna(), "g2", None
        )
    return df


def harmonize_one_file(path: Path) -> pd.DataFrame:
    """Melt one wide logger file into the long harmonized schema."""
    site_id = path.stem  # e.g. "ER_SMN10"
    df = pd.read_csv(path)

    meas_cols = [c for c in df.columns if COL_RE.match(c)]
    x = df[["Time"] + meas_cols].copy()
    x["datetime_UTC"] = parse_local_to_utc(x["Time"], "%Y-%m-%d %H:%M:%S", LOCAL_TZ)
    x = x.drop(columns=["Time"])

    long = x.melt(
        id_vars=["datetime_UTC"],
        value_vars=meas_cols,
        var_name="name",
        value_name="value",
    )

    parts = long["name"].map(lambda c: COL_RE.match(c).groupdict())
    long["var"] = parts.map(lambda d: d["var"])
    long["depth_m"] = (
        pd.to_numeric(parts.map(lambda d: d["depth"]), errors="coerce") / 100.0
    )
    long["replicate"] = pd.to_numeric(
        parts.map(lambda d: d["rep"]), errors="coerce"
    ).fillna(1).astype(int)

    # Normalize variable to the target measurement column.
    long["target"] = np.where(
        long["var"] == "Potential",
        "water_potential_kPa",
        "volumetric_water_content_m3_m3",
    )

    long["value"] = pd.to_numeric(long["value"], errors="coerce")
    long.loc[long["value"] == -9999, "value"] = np.nan
    long = long[long["value"].notna()].copy()

    wide = (
        long.pivot_table(
            index=["datetime_UTC", "depth_m", "replicate"],
            columns="target",
            values="value",
            aggfunc="first",
        )
        .reset_index()
    )

    wide["site_id"] = site_id
    wide["is_timeseries"] = True
    wide["gravimetric_water_content_gH2O_gs"] = np.nan

    return ensure_harmonized_cols(wide)


def harmonize() -> tuple[pd.DataFrame, pd.DataFrame]:
    data_files = sorted(p for p in DS_DIR.glob("ER_*.csv"))

    frames = [harmonize_one_file(p) for p in data_files]
    harmonized = pd.concat(frames, ignore_index=True)
    harmonized = harmonized.sort_values(
        ["datetime_UTC", "site_id", "depth_m", "replicate"]
    ).reset_index(drop=True)

    mdf = pd.read_csv(DS_DIR / LOCATION_FILE)
    loc_tmp = utm32613_to_latlon(mdf, "Easting", "Northing")
    loc = pd.DataFrame(
        {
            "site_id": loc_tmp["Name"],
            "latitude": loc_tmp["latitude"],
            "longitude": loc_tmp["longitude"],
        }
    )
    loc = loc[loc["site_id"].isin(harmonized["site_id"].unique())].copy()
    loc["source_dataset_id"] = DATASET_ID
    loc = add_loc_qc(loc)

    return harmonized, loc


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    harmonized, loc = harmonize()

    out_csv = OUT_DIR / f"{DATASET_ID}_harmonized.csv"
    harmonized.to_csv(out_csv, index=False)
    print(f"Wrote {out_csv} ({len(harmonized)} rows)")

    loc_csv = OUT_DIR / f"{DATASET_ID}_location_harmonized.csv"
    loc.to_csv(loc_csv, index=False)
    print(f"Wrote {loc_csv} ({len(loc)} rows)")
