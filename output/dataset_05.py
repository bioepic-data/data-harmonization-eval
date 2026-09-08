"""
Dataset 5 harmonization.

Dataset: ess-dive-8ac2940c708a515-20230504T210140482233
DOI: not available in staged workspace (record limitation)

Fold-evaluation harmonization of the Watershed Function SFA soil water
content (SWC) time-series package `SM_SWC.csv`.

This module mirrors the modular expert-code pattern (see
data/gold/expert_code/dataset_23.py, the closest structural analog: a
`*_SWC.csv` payload with Date Time / <location> / Sensor.SN / Measurement
columns and East River SFA site identifiers). It is written to be runnable
standalone within the run workspace: it reads the staged raw file from
inputs/raw/<dataset_identifier>/ and writes a harmonized CSV to output/.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

# =============================================================
# Paths (run-workspace relative)
# =============================================================
IDX = 5
DATASET_ID = "ess-dive-8ac2940c708a515-20230504T210140482233"
BASE_DIR = Path("inputs/raw")
OUT_DIR = Path("output")

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


def parse_local_to_utc(series: pd.Series, fmt: str | None, tz: str) -> pd.Series:
    """Parse a datetime series from local time to UTC."""
    dt = pd.to_datetime(series, format=fmt, errors="coerce")
    dt = dt.dt.tz_localize(tz, ambiguous="NaT", nonexistent="shift_forward")
    return dt.dt.tz_convert("UTC")


def ensure_harmonized_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure all harmonized columns are present, in canonical order."""
    for c in HARMONIZED_COLS:
        if c not in df.columns:
            df[c] = np.nan
    return df[HARMONIZED_COLS]


def harmonize() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Harmonize dataset 5. Returns (harmonized_data, location_data)."""
    ddf = pd.read_csv(
        BASE_DIR / DATASET_ID / "SM_SWC.csv",
        encoding="utf-8",
    )

    x = ddf.copy()

    # datetime: East River / Watershed Function SFA local standard time is
    # MST (UTC-7, no DST); expressed as Etc/GMT+7 to match expert convention
    # used for the analogous SFA SWC package (dataset 23).
    x["datetime_UTC"] = parse_local_to_utc(
        x["Date Time"], "%Y-%m-%d %H:%M:%S", "Etc/GMT+7"
    )

    # site_id: rename SFA_Location.
    x["site_id"] = x["SFA_Location"].astype(str)

    # depth: not reported in this package (no sensor/plot metadata file and no
    # depth column). Left as NaN and documented as a limitation.
    x["depth_m"] = np.nan

    # volumetric water content: 'Measurement' is already reported in m3/m3
    # (observed range ~0.0003-0.59); no unit conversion.
    x["volumetric_water_content_m3_m3"] = pd.to_numeric(
        x["Measurement"], errors="coerce"
    )
    x["gravimetric_water_content_gH2O_gs"] = np.nan
    x["water_potential_kPa"] = np.nan

    # time series: multiple observations per site with regular ~hourly/10-min
    # timestamps over 2017-2020 -> sensor deployment time series.
    x["is_timeseries"] = True

    # replicate: some SFA_Locations carry two sensors (Sensor.SN) at the same
    # timestamp; number replicates within site/depth/time.
    x = x.sort_values(["site_id", "datetime_UTC", "Sensor.SN"])
    x["replicate"] = (
        x.groupby(["datetime_UTC", "site_id", "depth_m"], dropna=False)
        .cumcount()
        .astype(int)
        + 1
    )

    x = x.sort_values(["site_id", "depth_m", "replicate", "datetime_UTC"])
    harmonized = ensure_harmonized_cols(x)

    # location: no coordinates in the payload and no ancillary location file in
    # this package. The SFA point-location registry (mapping index 0) is
    # referenced in the mapping JSON but its CSV is not staged in this
    # workspace, so coordinates are unresolvable here -> qc_flag "g2".
    site_ids = harmonized["site_id"].dropna().unique()
    loc = pd.DataFrame(
        {
            "site_id": site_ids,
            "latitude": np.nan,
            "longitude": np.nan,
        }
    )
    loc["source_dataset_id"] = DATASET_ID
    loc["qc_flag"] = "g2"

    return harmonized, loc


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    harmonized, loc = harmonize()

    harmonized_out = harmonized.sort_values(
        by=["datetime_UTC", "site_id", "depth_m", "replicate"]
    )
    out_file = OUT_DIR / f"{DATASET_ID}_harmonized.csv"
    harmonized_out.to_csv(out_file, index=False)
    print(f"Wrote {out_file.name}: {len(harmonized_out)} rows")

    loc_file = OUT_DIR / f"{DATASET_ID}_location.csv"
    loc.to_csv(loc_file, index=False)
    print(f"Wrote {loc_file.name}: {len(loc)} sites")


if __name__ == "__main__":
    main()
