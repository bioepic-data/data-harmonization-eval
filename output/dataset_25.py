"""
Dataset 25 harmonization.

Dataset: ess-dive-e67ab1151ebc525-20230929T190307767
DOI: (not available in run workspace)

Self-contained harmonization script for the fold-19 target dataset.

Package payload files:
  - Carbone_conifer.csv : header present, 24 columns
  - Carbone_aspen.csv   : NO header row, identical 24-column layout

Both files are hourly profile records with columns:
  Year, Month, Day, Hour,
  CO2-50cm, CO2-15cm, CO2-5cm, CO2-0cm, CO2-above,
  T-50cm, T-15cm, T-5cm, T-0cm, T-above,
  VWC-50cm, VWC-15cm, VWC-5cm,
  DecagonT-50cm, DecagonT-15cm, DecagonT-5cm,
  EC-50cm, EC-15cm, EC-5cm,
  BatteryVoltage

Soil moisture payload: VWC-50cm, VWC-15cm, VWC-5cm (volumetric water
content, already reported in m3/m3 -- observed values ~0.05-0.30).

No location metadata file is present in the package, no cached ESS-DIVE
metadata directory exists, and no approved location registry in the
workspace resolves these Carbone aspen/conifer sites. Coordinates are
therefore left as NaN with qc_flag = "g2".
"""

from __future__ import annotations
from pathlib import Path
import re
import numpy as np
import pandas as pd

BASE_DIR = Path("inputs/raw")
OUT_DIR = Path("output")

idx = 25
DATASET_ID = "ess-dive-e67ab1151ebc525-20230929T190307767"

COLUMN_NAMES = [
    "Year", "Month", "Day", "Hour",
    "CO2-50cm", "CO2-15cm", "CO2-5cm", "CO2-0cm", "CO2-above",
    "T-50cm", "T-15cm", "T-5cm", "T-0cm", "T-above",
    "VWC-50cm", "VWC-15cm", "VWC-5cm",
    "DecagonT-50cm", "DecagonT-15cm", "DecagonT-5cm",
    "EC-50cm", "EC-15cm", "EC-5cm",
    "BatteryVoltage",
]

VWC_COLS = ["VWC-50cm", "VWC-15cm", "VWC-5cm"]

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

# (filename, site_id, has_header)
PAYLOAD_FILES = [
    ("Carbone_conifer.csv", "Carbone_conifer", True),
    ("Carbone_aspen.csv", "Carbone_aspen", False),
]


def ensure_harmonized_cols(df: pd.DataFrame) -> pd.DataFrame:
    for c in HARMONIZED_COLS:
        if c not in df.columns:
            df[c] = np.nan
    return df[HARMONIZED_COLS]


def harmonize_one(filename: str, site_id: str, has_header: bool) -> pd.DataFrame:
    path = BASE_DIR / DATASET_ID / filename
    if has_header:
        d = pd.read_csv(path)
    else:
        d = pd.read_csv(path, header=None, names=COLUMN_NAMES)

    # Local time built from split Year/Month/Day/Hour columns, converted to UTC.
    # Sites are in the western US (Sierra Nevada); in the absence of package
    # metadata a fixed standard-time offset (Etc/GMT+7, i.e. UTC-7, no DST) is
    # used, consistent with the exemplar western-US datasets.
    dt_local = pd.to_datetime(
        dict(
            year=pd.to_numeric(d["Year"], errors="coerce"),
            month=pd.to_numeric(d["Month"], errors="coerce"),
            day=pd.to_numeric(d["Day"], errors="coerce"),
            hour=pd.to_numeric(d["Hour"], errors="coerce"),
        ),
        errors="coerce",
    )
    dt_local = dt_local.dt.tz_localize(
        "Etc/GMT+7", ambiguous="NaT", nonexistent="shift_forward"
    )
    d = d.copy()
    d["datetime_UTC"] = dt_local.dt.tz_convert("UTC")

    long = d.melt(
        id_vars=["datetime_UTC"],
        value_vars=VWC_COLS,
        var_name="name",
        value_name="value",
    )
    long["depth_m"] = (
        pd.to_numeric(long["name"].str.extract(r"(\d+\.?\d*)cm")[0], errors="coerce")
        / 100.0
    )
    long["value"] = pd.to_numeric(long["value"], errors="coerce")
    long.loc[long["value"] == -9999, "value"] = np.nan
    long = long.dropna(subset=["value", "depth_m", "datetime_UTC"])

    x = pd.DataFrame(
        {
            "datetime_UTC": long["datetime_UTC"],
            "site_id": site_id,
            "depth_m": long["depth_m"],
            "replicate": 1,
            "is_timeseries": True,
            "volumetric_water_content_m3_m3": long["value"],
            "gravimetric_water_content_gH2O_gs": np.nan,
            "water_potential_kPa": np.nan,
        }
    )
    return ensure_harmonized_cols(x)


def harmonize() -> pd.DataFrame:
    parts = [harmonize_one(f, s, h) for (f, s, h) in PAYLOAD_FILES]
    return pd.concat(parts, ignore_index=True)


def build_locations(harmonized: pd.DataFrame) -> pd.DataFrame:
    # No location file in package; no cached metadata; no resolving registry.
    loc = pd.DataFrame(
        {"site_id": sorted(harmonized["site_id"].dropna().unique())}
    )
    loc["latitude"] = np.nan
    loc["longitude"] = np.nan
    loc["source_dataset_id"] = DATASET_ID
    loc["qc_flag"] = "g2"
    return loc


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    harmonized = harmonize()
    harmonized = harmonized.sort_values(
        by=["datetime_UTC", "site_id", "depth_m", "replicate"]
    ).reset_index(drop=True)

    out_file = OUT_DIR / f"{DATASET_ID}_harmonized.csv"
    harmonized.to_csv(out_file, index=False)
    print(f"Wrote {out_file} ({len(harmonized)} rows)")

    loc = build_locations(harmonized)
    loc_file = OUT_DIR / f"{DATASET_ID}_location.csv"
    loc.to_csv(loc_file, index=False)
    print(f"Wrote {loc_file} ({len(loc)} rows)")


if __name__ == "__main__":
    main()
