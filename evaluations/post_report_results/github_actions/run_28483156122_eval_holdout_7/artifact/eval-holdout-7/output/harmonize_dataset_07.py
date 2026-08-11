"""Harmonization for held-out dataset index 7.

Dataset: ess-dive-38e901ec3d7bd24-20230504T211548257225

This module follows the same conventions as the expert per-dataset
harmonizers (``dataset_NN.py``): it exposes a ``harmonize(ctx)`` function
that returns a :class:`common.DatasetResult`. Because this dataset is held
out of the gold mapping JSON, the file/column references are hard-coded here
(rather than read from ``map_json[idx]``) but otherwise use the shared
helpers from ``common.py``.

Structure (from inspection of the raw package):
  * BM_Merged_T_VWC_0616_1018.csv  -- DATA PAYLOAD
      date.time, record, Volumetric Water Content, Electrical Conductivity (dS/m),
      T (degrees celcius), Depth (cm)
      Long-format hourly soil-moisture time series at a single station ("BM"),
      with an explicit Depth (cm) column. VWC is already in m3/m3 (values ~0.12).
  * BM_EGM_Well_CO2.csv            -- ANCILLARY (soil CO2 profiles; NOT soil moisture)
      Location, Latitude, Longitude, Date, Time, Depth, CO2.Max, Notes
      Used ONLY as the location source: it carries decimal-degree coordinates
      for site "BM".

Decisions:
  * INCLUDE (Rule 2 satisfied: direct VWC observations present).
  * Only the VWC column is harmonized. Electrical Conductivity, soil
    temperature, and CO2 are out of schema and dropped.
  * is_timeseries = True (regular hourly logger output, many obs per
    site+depth); interval_min inferred per site+depth from timestamp diffs.
  * Depth is explicit (cm) -> divide by 100 -> m. No depth approximation,
    so no 'd1' qc_flag.
  * Coordinates come from the package's own CO2 file (decimal degrees),
    Location resolution priority Source 2 -> no qc_flag needed.
  * replicate = 1 (single sensor per depth; no replicate info in source).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from common import (
    DatasetResult,
    parse_local_to_utc,
    ensure_harmonized_cols,
    add_loc_qc,
)

DATASET_ID = "ess-dive-38e901ec3d7bd24-20230504T211548257225"
PAYLOAD_FILE = "BM_Merged_T_VWC_0616_1018.csv"
LOCATION_FILE = "BM_EGM_Well_CO2.csv"


def harmonize(ctx) -> DatasetResult:
    """Harmonize held-out dataset 7, returning its DatasetResult."""
    ds_dir = ctx.base_dir / DATASET_ID
    __locations = []

    # =============================================================
    # Dataset 7 (held out)
    # =============================================================
    ddf = pd.read_csv(ds_dir / PAYLOAD_FILE, encoding="utf-8")
    mdf = pd.read_csv(ds_dir / LOCATION_FILE, encoding="latin-1")

    x = ddf.copy()

    # datetime: Convert 'date.time' (local America/Denver) to ISO 8601 UTC.
    x["datetime_UTC"] = parse_local_to_utc(x["date.time"], "%m/%d/%y %H:%M", "America/Denver")

    # site_id: single station for this package; the CO2/location file names it "BM".
    x["site_id"] = "BM"

    # depth: explicit 'Depth (cm)' column -> divide by 100 for meters.
    x["depth_m"] = pd.to_numeric(x["Depth (cm)"], errors="coerce") / 100.0

    # replicate: not provided in source; populate with 1.
    x["replicate"] = 1
    x["is_timeseries"] = True

    # interval_min: inferred per site+depth from timestamp differences.
    x = x.sort_values(["site_id", "depth_m", "datetime_UTC"])
    x["interval_min"] = (
        x.groupby(["site_id", "depth_m"])["datetime_UTC"].diff().dt.total_seconds() / 60.0
    )
    x.loc[x["interval_min"] < 0, "interval_min"] = np.nan

    # volumetric_water_content: 'Volumetric Water Content' already in m3/m3.
    x["volumetric_water_content_m3_m3"] = pd.to_numeric(
        x["Volumetric Water Content"], errors="coerce"
    )

    # Not reported in source.
    x["gravimetric_water_content_gH2O_gs"] = np.nan
    x["water_potential_kPa"] = np.nan

    df_harmonized = ensure_harmonized_cols(x)

    # latitude / longitude: decimal degrees from the package CO2 file for site "BM".
    lat_col = [c for c in mdf.columns if c.lower().startswith("latitude")][0]
    lon_col = [c for c in mdf.columns if c.lower().startswith("longitude")][0]
    loc = (
        mdf.rename(columns={"Location": "site_id", lat_col: "latitude", lon_col: "longitude"})[
            ["site_id", "latitude", "longitude"]
        ]
        .copy()
    )
    loc["latitude"] = pd.to_numeric(loc["latitude"], errors="coerce")
    loc["longitude"] = pd.to_numeric(loc["longitude"], errors="coerce")
    loc = loc.drop_duplicates(subset=["site_id"])
    loc = loc[loc["site_id"].isin(df_harmonized["site_id"].dropna().unique())]
    loc["source_dataset_id"] = DATASET_ID
    loc = add_loc_qc(loc)
    __locations.append(loc)

    return DatasetResult(DATASET_ID, df_harmonized, __locations)


# ------------------------------------------------------------------
# Standalone runner: writes the harmonized CSV + a small location CSV
# into this run's output/ directory.
# ------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    here = Path(__file__).resolve().parent
    run_root = here.parent  # .runs/holdout-7
    # make common.py importable
    sys.path.insert(0, str(run_root / "data" / "gold" / "expert_code" / "harmonize_sm"))
    from common import Context  # noqa: E402

    base_dir = Path.home() / "ess-dive_wfsfa_soil_datasets"
    out_dir = here  # output/
    mapping_path = run_root / "data" / "processed" / "ess-dive_wfsfa_soil_datasets" / "sm_data_harmonization_mapping.json"

    ctx = Context.load(base_dir=base_dir, out_dir=out_dir, mapping_path=mapping_path)

    result = harmonize(ctx)

    result.harmonized.to_csv(out_dir / f"{DATASET_ID}_harmonized.csv", index=False)
    if result.locations:
        pd.concat(result.locations, ignore_index=True).to_csv(
            out_dir / f"{DATASET_ID}_locations.csv", index=False
        )

    df = result.harmonized
    print("rows:", len(df))
    print("depths_m:", sorted(df["depth_m"].dropna().unique()))
    print("vwc min/max:", df["volumetric_water_content_m3_m3"].min(), df["volumetric_water_content_m3_m3"].max())
    print("datetime range:", df["datetime_UTC"].min(), "->", df["datetime_UTC"].max())
    print("median interval_min:", df["interval_min"].median())
    print(pd.concat(result.locations, ignore_index=True).to_string(index=False))
