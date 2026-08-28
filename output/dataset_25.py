"""
Dataset 25 harmonization (leave-one-cluster-out fold-13).

Dataset: ess-dive-e67ab1151ebc525-20230929T190307767
DOI: doi:10.15485/... (not resolvable from staged workspace; see notes)

Self-contained harmonization script for a single held-out dataset. Follows the
conventions in skills/essdive_sm_harmonizer/SKILL.md (fold-evaluation mode).

Package contents (two payload files, one per site):
  - Carbone_aspen.csv    (NO header row; identical 24-column layout as conifer)
  - Carbone_conifer.csv  (header row present)

Both files are hourly forest-floor soil profile records (2011-2021) with:
  Year, Month, Day, Hour, CO2-*, T-*, VWC-{50,15,5}cm, DecagonT-*, EC-*, BatteryVoltage

Only the three VWC-{depth}cm columns are direct soil moisture observations and
are harmonized. VWC values are already fractional (m3/m3), so no unit conversion.
Site coordinates are not present in any staged file or cached metadata, so
locations are unresolved and flagged g2.
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

# Canonical 24-column layout (conifer header; aspen has no header but same order).
COLUMNS = [
    "Year", "Month", "Day", "Hour",
    "CO2-50cm", "CO2-15cm", "CO2-5cm", "CO2-0cm", "CO2-above",
    "T-50cm", "T-15cm", "T-5cm", "T-0cm", "T-above",
    "VWC-50cm", "VWC-15cm", "VWC-5cm",
    "DecagonT-50cm", "DecagonT-15cm", "DecagonT-5cm",
    "EC-50cm", "EC-15cm", "EC-5cm",
    "BatteryVoltage",
]

# site_id <- source filename stem "Carbone_<site>"
FILE_SITE = {
    "Carbone_aspen.csv": "aspen",
    "Carbone_conifer.csv": "conifer",
}


def ensure_harmonized_cols(df: pd.DataFrame) -> pd.DataFrame:
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
    if "qc_flag" not in df.columns:
        df["qc_flag"] = np.where(
            df["latitude"].isna() | df["longitude"].isna(), "g2", None
        )
    return df


def read_site(filename: str, has_header: bool) -> pd.DataFrame:
    path = BASE_DIR / DATASET_ID / filename
    if has_header:
        return pd.read_csv(path)
    return pd.read_csv(path, header=None, names=COLUMNS)


def harmonize() -> tuple[pd.DataFrame, pd.DataFrame]:
    frames = []
    for filename, has_header in (("Carbone_aspen.csv", False), ("Carbone_conifer.csv", True)):
        raw = read_site(filename, has_header)

        x = raw.copy()
        # Build a naive local timestamp from Year/Month/Day/Hour then localize.
        # Timezone of the record clock is not documented in the package; the
        # Carbone Manitou Experimental Forest sites are in Colorado, so we use
        # America/Denver (see notes for the associated uncertainty).
        naive = pd.to_datetime(
            dict(
                year=pd.to_numeric(x["Year"], errors="coerce"),
                month=pd.to_numeric(x["Month"], errors="coerce"),
                day=pd.to_numeric(x["Day"], errors="coerce"),
                hour=pd.to_numeric(x["Hour"], errors="coerce"),
            ),
            errors="coerce",
        )
        x["datetime_UTC"] = (
            naive.dt.tz_localize(
                "America/Denver", ambiguous="NaT", nonexistent="shift_forward"
            ).dt.tz_convert("UTC")
        )

        x["site_id"] = FILE_SITE[filename]

        vwc_cols = [c for c in x.columns if c.startswith("VWC-")]
        long = x.melt(
            id_vars=["datetime_UTC", "site_id"],
            value_vars=vwc_cols,
            var_name="name",
            value_name="volumetric_water_content_m3_m3",
        )
        # depth embedded in column name "VWC-<d>cm"
        long["depth_m"] = (
            pd.to_numeric(long["name"].str.extract(r"(\d+\.?\d*)cm")[0], errors="coerce")
            / 100.0
        )
        long["volumetric_water_content_m3_m3"] = pd.to_numeric(
            long["volumetric_water_content_m3_m3"], errors="coerce"
        )
        # Common sentinels
        long.loc[
            long["volumetric_water_content_m3_m3"] == -9999.0,
            "volumetric_water_content_m3_m3",
        ] = np.nan

        long["replicate"] = 1
        long["is_timeseries"] = True
        long["water_potential_kPa"] = np.nan
        long["gravimetric_water_content_gH2O_gs"] = np.nan

        frames.append(long)

    combined = pd.concat(frames, ignore_index=True)
    harmonized = ensure_harmonized_cols(combined)

    # Location metadata: no coordinates in payload, ancillary file, or cached
    # metadata -> unresolved, flagged g2.
    loc = pd.DataFrame(
        {
            "site_id": ["aspen", "conifer"],
            "latitude": [np.nan, np.nan],
            "longitude": [np.nan, np.nan],
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
    )

    out_csv = OUT_DIR / f"{DATASET_ID}_harmonized.csv"
    harmonized.to_csv(out_csv, index=False)
    loc.to_csv(OUT_DIR / f"{DATASET_ID}_location.csv", index=False)

    print(f"Wrote {out_csv} ({len(harmonized)} rows)")
    print(harmonized.head())


if __name__ == "__main__":
    main()
