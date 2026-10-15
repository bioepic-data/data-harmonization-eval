"""
Harmonization code for dataset index 1 (fold-01 target).

Dataset: ess-dive-beca0be9bb38ece-20250516T122010234
DOI: doi:10.15485/2566877
Title: Soil moisture and temperature from 2019 to 2024 along northeast- and
       southwest-facing hillslopes at the Lower Montane site in the East River
       Watershed, Colorado. Watershed Function SFA.

This is a self-contained, fold-evaluation harmonizer. It reads the staged raw
package files from inputs/raw/<dataset_identifier>/ and writes all deliverables
under output/. It follows the WFSFA soil-moisture target schema and the Python
code conventions in skills/essdive_sm_harmonizer/SKILL.md.

Decision: INCLUDE. The package contains direct, time-stamped sensor observations
of volumetric water content (m3/m3) and, for two stations, soil water potential
(kPa). TEROS12 / 5TE sensors, 30-min to hourly cadence, 2019-2024 -> time series.
"""

from __future__ import annotations

import re
import numpy as np
import pandas as pd
from pathlib import Path
from pyproj import Transformer

# %%
# =============================================================
# Paths / constants
# =============================================================
IDX = 1
DSID = "ess-dive-beca0be9bb38ece-20250516T122010234"
DOI = "doi:10.15485/2566877"

BASE_DIR = Path("inputs/raw") / DSID
OUT_DIR = Path("output")

# Loggers in the East River Watershed (Colorado) report in local standard time.
# The package metadata does not state the timezone explicitly; Mountain Standard
# Time (UTC+7, no DST on these loggers) is assumed, consistent with other East
# River WFSFA soil-moisture exemplars (e.g. dataset 25). Documented in notes.
SOURCE_TZ = "Etc/GMT+7"

DATA_FILES = [
    "ER_SMN10.csv",
    "ER_SMN1B.csv",
    "ER_SMN30.csv",
    "ER_SMN3B.csv",
    "ER_SMN4B.csv",
    "ER_SMN5B.csv",
    "ER_SMS1.csv",
    "ER_SMS2.csv",
    "ER_SMS3.csv",
]
LOC_FILE = "Sensor_Location.csv"

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


# %%
# =============================================================
# Helpers (mirroring common.py conventions)
# =============================================================
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


# Column-name parser.
# Patterns observed:
#   m3_m3_Water_Content_at_10cm        -> VWC, sensor ordinal 0, 10 cm
#   m3_m3_Water_Content_3_at_50cm      -> VWC, sensor ordinal 3, 50 cm
#   m3_m3_VWC_at_40cm / m3_m3_VWC_1_at_30cm -> VWC
#   kPa_Potential_at_40cm / kPa_Potential_1_at_10cm -> water potential
MEAS_RE = re.compile(
    r"^(?:m3_m3_(?:Water_Content|VWC)|kPa_Potential)"
    r"(?:_(?P<ord>\d+))?"
    r"_at_(?P<depth>\d+(?:\.\d+)?)cm$"
)


def classify_column(col: str):
    """Return (var, ordinal, depth_cm) or None if not a target measurement col."""
    m = MEAS_RE.match(col)
    if not m:
        return None
    ordv = int(m.group("ord")) if m.group("ord") is not None else 0
    depth_cm = float(m.group("depth"))
    if col.startswith("kPa_Potential"):
        var = "water_potential_kPa"
    else:
        var = "volumetric_water_content_m3_m3"
    return var, ordv, depth_cm


# %%
# =============================================================
# Dataset 1 harmonization
# =============================================================
def harmonize() -> tuple[pd.DataFrame, pd.DataFrame]:
    frames = []

    for fname in DATA_FILES:
        site_id = Path(fname).stem  # e.g. "ER_SMN10"
        df = pd.read_csv(BASE_DIR / fname, encoding="utf-8")

        meas_cols = {c: classify_column(c) for c in df.columns}
        meas_cols = {c: v for c, v in meas_cols.items() if v is not None}
        if not meas_cols:
            continue

        dt_utc = parse_local_to_utc(df["Time"], "%Y-%m-%d %H:%M:%S", SOURCE_TZ)

        # replicate: ordinal of the physical sensor within site+depth+variable.
        # Enumerate sensors sharing a (variable, depth) and number from 1.
        groups: dict[tuple, list] = {}
        for col, (var, ordv, depth_cm) in meas_cols.items():
            groups.setdefault((var, depth_cm), []).append((ordv, col))
        rep_of_col: dict[str, int] = {}
        for key, items in groups.items():
            for rep, (_ordv, col) in enumerate(sorted(items), start=1):
                rep_of_col[col] = rep

        for col, (var, _ordv, depth_cm) in meas_cols.items():
            vals = pd.to_numeric(df[col], errors="coerce")
            vals = vals.where(vals != -9999)  # missing-value sentinel
            sub = pd.DataFrame(
                {
                    "datetime_UTC": dt_utc,
                    "site_id": site_id,
                    "depth_m": depth_cm / 100.0,
                    "replicate": rep_of_col[col],
                    "is_timeseries": True,
                    var: vals,
                }
            )
            sub = sub[sub[var].notna()]
            frames.append(sub)

    harmonized = pd.concat(frames, ignore_index=True)
    harmonized = ensure_harmonized_cols(harmonized)

    # Location: UTM Zone 13N (EPSG:32613) Easting/Northing -> lat/lon.
    mdf = pd.read_csv(BASE_DIR / LOC_FILE, encoding="utf-8")
    loc_tmp = utm32613_to_latlon(mdf, "Easting", "Northing")
    loc = pd.DataFrame(
        {
            "site_id": loc_tmp["Name"],
            "latitude": loc_tmp["latitude"],
            "longitude": loc_tmp["longitude"],
        }
    )
    loc["source_dataset_id"] = DSID
    loc = add_loc_qc(loc)
    loc = loc.drop_duplicates(subset=["site_id"]).reset_index(drop=True)

    return harmonized, loc


# %%
# =============================================================
# Write outputs
# =============================================================
def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    harmonized, loc = harmonize()

    harmonized = harmonized.sort_values(
        by=["datetime_UTC", "site_id", "depth_m", "replicate"]
    ).reset_index(drop=True)

    harmonized.to_csv(OUT_DIR / f"{DSID}_harmonized.csv", index=False)
    loc[["site_id", "latitude", "longitude", "source_dataset_id", "qc_flag"]].to_csv(
        OUT_DIR / f"{DSID}_location.csv", index=False
    )

    print(f"harmonized rows: {len(harmonized):,}")
    print(f"sites: {harmonized['site_id'].nunique()}  loc rows: {len(loc)}")
    print(harmonized.head())


if __name__ == "__main__":
    main()
