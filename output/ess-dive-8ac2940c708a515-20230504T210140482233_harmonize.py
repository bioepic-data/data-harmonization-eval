"""
Dataset 5 harmonization.

Dataset: ess-dive-8ac2940c708a515-20230504T210140482233
DOI: doi:10.15485/1842907
Title: Microclimate observations associated with snowmelt experiment gradient
       sites, East River, Colorado, 2017 to 2020.

Fold-evaluation standalone harmonizer. Reads only the staged package file
(inputs/raw/<dataset_identifier>/SM_SWC.csv) and the target's cached ESS-DIVE
metadata, and writes deliverables under output/. No network access.

Follows the wfsfa_sm_harmonization SKILL conventions (SECTION 6 / 7). This is
the snowmelt-manipulation sibling of dataset 23 (the warming-manipulation
package WM_SWC.csv). Unlike dataset 23, this package's sensor_metadata.csv and
plot_metadata.csv are NOT staged in the fold, so depth and treatment/control
labels are unavailable; and the Varadharajan location registry (index 0) file
is not staged, so per-site coordinates cannot be resolved. These limitations
are documented in the notes/JSON rather than worked around.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path("inputs/raw")
OUT_DIR = Path("output")

idx = 5
DATASET_ID = "ess-dive-8ac2940c708a515-20230504T210140482233"
DATA_FILE = "SM_SWC.csv"


def parse_local_to_utc(series: pd.Series, fmt: str | None, tz: str) -> pd.Series:
    """Parse datetime series from local time to UTC (verbatim from common.py)."""
    dt = pd.to_datetime(series, format=fmt, errors="coerce")
    dt = dt.dt.tz_localize(tz, ambiguous="NaT", nonexistent="shift_forward")
    return dt.dt.tz_convert("UTC")


def ensure_harmonized_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure all harmonized columns are present (verbatim from common.py)."""
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


def harmonize() -> tuple[pd.DataFrame, pd.DataFrame]:
    ddf = pd.read_csv(BASE_DIR / DATASET_ID / DATA_FILE)

    x = ddf.copy()

    # Timestamps: 'Date Time' is local standard time (East River, CO = Etc/GMT+7,
    # i.e. MST / no DST), matching the sibling package dataset 23.
    x["datetime_UTC"] = parse_local_to_utc(x["Date Time"], "%Y-%m-%d %H:%M:%S", "Etc/GMT+7")

    # site_id: SFA_Location column (plot/sub-plot identifier).
    x["site_id"] = x["SFA_Location"].astype(str)

    # Depth: not provided in payload; sensor_metadata.csv is not staged in this
    # fold, so depth cannot be resolved. Leave NaN.
    x["depth_m"] = np.nan

    x["is_timeseries"] = True

    # Measurement is soil water content, already volumetric (m3/m3); observed
    # range 0.0003-0.5887 is consistent with VWC in m3 m-3 (no unit conversion).
    x["volumetric_water_content_m3_m3"] = pd.to_numeric(x["Measurement"], errors="coerce")
    x["gravimetric_water_content_gH2O_gs"] = np.nan
    x["water_potential_kPa"] = np.nan

    # Replicate: a few sites host >1 sensor (Sensor.SN). Number replicates within
    # each (datetime, site, depth) group, matching dataset 23's approach.
    x["replicate"] = (
        x.groupby(["datetime_UTC", "site_id", "depth_m"], dropna=False).cumcount().astype(int) + 1
    )

    x = x.sort_values(["site_id", "depth_m", "replicate", "datetime_UTC"])

    harmonized = ensure_harmonized_cols(x)

    # Location: per-site coordinates are not in the payload. The package metadata
    # provides only a watershed bounding box (NW/SE corners), not per-site points,
    # and the Varadharajan location registry (index 0) referenced by the sibling
    # package is NOT staged in this fold. Coordinates are therefore unresolvable:
    # emit every site_id with empty lat/lon and qc_flag 'g2'. Do not invent coords.
    sites = sorted(harmonized["site_id"].dropna().unique())
    loc = pd.DataFrame({
        "site_id": sites,
        "latitude": [np.nan] * len(sites),
        "longitude": [np.nan] * len(sites),
    })
    loc["source_dataset_id"] = DATASET_ID
    loc["qc_flag"] = "g2"
    loc = loc[["site_id", "latitude", "longitude", "source_dataset_id", "qc_flag"]]

    return harmonized, loc


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    harmonized, loc = harmonize()

    harmonized_out = harmonized.sort_values(
        by=["datetime_UTC", "site_id", "depth_m", "replicate"]
    )
    harmonized_out.to_csv(OUT_DIR / f"{DATASET_ID}_harmonized.csv", index=False)
    loc.to_csv(OUT_DIR / f"{DATASET_ID}_location.csv", index=False)

    print(f"harmonized rows: {len(harmonized_out)}")
    print(f"distinct sites : {loc['site_id'].nunique()}")
    print(f"vwc non-null   : {harmonized_out['volumetric_water_content_m3_m3'].notna().sum()}")


if __name__ == "__main__":
    main()
