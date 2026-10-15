"""
Dataset 7 harmonization.

Dataset: ess-dive-38e901ec3d7bd24-20230504T211548257225
DOI: doi:10.15485/1660455
Soil Environmental Conditions in the East River Watershed, CO (Bradley Meadow).

Payload: BM_Merged_T_VWC_0616_1018.csv
  Datalogger output from 7 Campbell CS655 soil moisture/temperature sensors
  (depth, temperature, VWC, electrical conductivity), hourly, Jun 2016 - Oct 2018.
  Volumetric Water Content is reported as a decimal fraction (m3 m-3), no unit
  conversion required.

Coordinates: single site "BM" (Bradley Meadow, Gothic, CO) at
  38.98715, -107.003863, taken from BM_EGM_Well_CO2.csv (and corroborated by
  the package ESS-DIVE spatialCoverage record).

Run as a standalone block (fold evaluation); reads from inputs/raw and writes
to output/.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from common import (
    parse_local_to_utc,
    ensure_harmonized_cols,
    add_loc_qc,
)

BASE_DIR = Path("inputs/raw")
OUT_DIR = Path("output")

DATASET_ID = "ess-dive-38e901ec3d7bd24-20230504T211548257225"
IDX = 7

DATA_FILE = "BM_Merged_T_VWC_0616_1018.csv"
COORD_FILE = "BM_EGM_Well_CO2.csv"

SITE_ID = "BM"
SITE_LAT = 38.98715
SITE_LON = -107.003863


def harmonize():
    ds_dir = BASE_DIR / DATASET_ID

    ddf = pd.read_csv(ds_dir / DATA_FILE, encoding="latin1")

    x = ddf.copy()
    # East River / Gothic, CO; use fixed MST offset (Etc/GMT+7) consistent with
    # other Colorado East River datasets in the harmonization project.
    x["datetime_UTC"] = parse_local_to_utc(x["date.time"], "%m/%d/%y %H:%M", "Etc/GMT+7")
    x["site_id"] = SITE_ID
    x["depth_m"] = pd.to_numeric(x["Depth (cm)"], errors="coerce") / 100.0
    x["replicate"] = 1
    x["is_timeseries"] = True
    # VWC already reported as a decimal fraction (m3 m-3).
    x["volumetric_water_content_m3_m3"] = pd.to_numeric(
        x["Volumetric Water Content"], errors="coerce"
    )
    x["gravimetric_water_content_gH2O_gs"] = np.nan
    x["water_potential_kPa"] = np.nan

    df_harmonized = ensure_harmonized_cols(x)

    # Location: single site, coordinates from the package payload/metadata.
    loc = pd.DataFrame(
        {
            "site_id": [SITE_ID],
            "latitude": [SITE_LAT],
            "longitude": [SITE_LON],
        }
    )
    loc["source_dataset_id"] = DATASET_ID
    loc = add_loc_qc(loc)
    loc = loc[["site_id", "latitude", "longitude", "source_dataset_id", "qc_flag"]]

    return df_harmonized, loc


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df_harmonized, loc = harmonize()

    df_out = df_harmonized.sort_values(
        by=["datetime_UTC", "site_id", "depth_m", "replicate"]
    )
    df_out.to_csv(OUT_DIR / f"{DATASET_ID}_harmonized.csv", index=False)
    loc.to_csv(OUT_DIR / f"{DATASET_ID}_location.csv", index=False)

    print(f"Wrote {DATASET_ID}_harmonized.csv ({len(df_out)} rows)")
    print(f"Wrote {DATASET_ID}_location.csv ({len(loc)} rows)")


if __name__ == "__main__":
    main()
