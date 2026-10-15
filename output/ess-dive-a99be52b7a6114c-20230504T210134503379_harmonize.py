"""
Harmonization code for a single ESS-DIVE soil moisture dataset.

Dataset: ess-dive-a99be52b7a6114c-20230504T210134503379
DOI:     doi:10.15485/1842908
Title:   Surface soil temperature and water content from warming experiment
         located at the Rocky Mountain Biological Laboratory, Colorado, 2015-2019
Index:   23 (canonical index retained from MANIFEST.json)

Run as a standalone fold-evaluation script. Reads staged raw inputs from
inputs/raw/<dataset_identifier>/ and writes deliverables to output/.

Experimental context (SKILL RULE 3 / general-insight 10):
    This is a warming manipulation experiment. Plots alternate between
    'control' and 'heated' treatments (see plot_metadata.csv). Per the
    harmonization rules, a manipulation experiment is FLAGGED and documented
    rather than auto-excluded. Both control and heated plots are retained here;
    the treatment assignment is documented in the mapping JSON and notes so a
    downstream user can filter heated plots if an ambient-only signal is
    required.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


DATASET_ID = "ess-dive-a99be52b7a6114c-20230504T210134503379"
IDX = 23

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
    """Parse a datetime series from local time to UTC (ISO-8601, UTC)."""
    dt = pd.to_datetime(series, format=fmt, errors="coerce")
    dt = dt.dt.tz_localize(tz, ambiguous="NaT", nonexistent="shift_forward")
    return dt.dt.tz_convert("UTC")


def ensure_harmonized_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Enforce the target column schema (and column order)."""
    for c in HARMONIZED_COLS:
        if c not in df.columns:
            df[c] = np.nan
    return df[HARMONIZED_COLS]


def harmonize() -> tuple[pd.DataFrame, pd.DataFrame]:
    ds_dir = BASE_DIR / DATASET_ID

    # ------------------------------------------------------------------
    # Read staged package files.
    #   WM_SWC.csv        -> measurement payload (hourly SWC, long format)
    #   sensor_metadata.csv -> per-sensor depth (Depth.cm) keyed by Sensor.SN
    #   plot_metadata.csv -> plot-level warming treatment (control/heated)
    # ------------------------------------------------------------------
    ddf = pd.read_csv(ds_dir / "WM_SWC.csv")
    sdf = pd.read_csv(ds_dir / "sensor_metadata.csv")

    # Keep only soil-water-content sensor rows from the payload.
    x = ddf[ddf["Sensor.Type"] == "SWC"].copy()

    # Timestamps are local standard time (Mountain Standard Time, no DST in the
    # logged record); use a fixed UTC-7 offset. Etc/GMT+7 == UTC-7.
    x["datetime_UTC"] = parse_local_to_utc(x["Date Time"], "%Y-%m-%d %H:%M:%S", "Etc/GMT+7")

    # site_id: the sensor Point.Location (upper/lower zone within each plot) is
    # the finest-grained spatial identifier and matches the sensor metadata.
    x["site_id"] = x["Point.Location"]

    # Depth: look up Depth.cm for each Sensor.SN in the sensor metadata.
    sw = sdf[sdf["Sensor Type"] == "SWC"].copy()
    sw["Sensor.SN"] = pd.to_numeric(sw["Sensor.SN"], errors="coerce")
    depth_map = (
        sw.dropna(subset=["Sensor.SN"])
        .drop_duplicates(subset=["Sensor.SN"])
        .set_index("Sensor.SN")["Depth.cm"]
    )
    x["depth_m"] = (
        pd.to_numeric(x["Sensor.SN"].map(depth_map), errors="coerce") / 100.0
    )

    # Soil water content is reported directly in m3/m3 (volumetric fraction).
    x["volumetric_water_content_m3_m3"] = pd.to_numeric(
        x["Measurement"], errors="coerce"
    )
    x["gravimetric_water_content_gH2O_gs"] = np.nan
    x["water_potential_kPa"] = np.nan

    # Time series: hourly logger output over multiple years.
    x["is_timeseries"] = True

    # Replicate: multiple SWC sensors exist at the same site_id + depth. Number
    # them per (datetime, site_id, depth) so distinct sensors remain separable.
    x = x.sort_values(["datetime_UTC", "site_id", "depth_m", "Sensor.SN"])
    x["replicate"] = (
        x.groupby(["datetime_UTC", "site_id", "depth_m"], dropna=False).cumcount() + 1
    )

    harmonized = ensure_harmonized_cols(x)

    # ------------------------------------------------------------------
    # Location resolution.
    # Priority cascade (SKILL Section 5):
    #   1. payload file: no coordinates
    #   2. ancillary files: plot/sensor metadata carry no lat/lon
    #   3. package metadata: only a watershed-level bounding box, no per-site
    #      GeoCoordinates -> cannot assign site coordinates
    #   4. approved location registry: Varadharajan et al. (2020) is referenced
    #      in the package metadata but is NOT supplied in this workspace, so it
    #      cannot be used (g1 not available)
    #   5. unresolvable -> lat/lon = NaN, qc_flag = "g2"
    # Emit every distinct site_id with empty coordinates and qc_flag "g2".
    # ------------------------------------------------------------------
    sites = sorted(harmonized["site_id"].dropna().unique())
    loc = pd.DataFrame({"site_id": sites})
    loc["latitude"] = np.nan
    loc["longitude"] = np.nan
    loc["source_dataset_id"] = DATASET_ID
    loc["qc_flag"] = "g2"
    loc = loc[["site_id", "latitude", "longitude", "source_dataset_id", "qc_flag"]]

    return harmonized, loc


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    harmonized, loc = harmonize()

    harmonized = harmonized.sort_values(
        by=["datetime_UTC", "site_id", "depth_m", "replicate"]
    )

    harmonized.to_csv(OUT_DIR / f"{DATASET_ID}_harmonized.csv", index=False)
    loc.to_csv(OUT_DIR / f"{DATASET_ID}_location.csv", index=False)

    print(f"Wrote {DATASET_ID}_harmonized.csv ({len(harmonized)} rows)")
    print(f"Wrote {DATASET_ID}_location.csv ({len(loc)} sites)")


if __name__ == "__main__":
    main()
