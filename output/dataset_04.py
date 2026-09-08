"""
Dataset 04 harmonization (fold-09-target-4).

Dataset: ess-dive-6c7085e9c544cc6-20250424T164534831
Package: Johnsen_Bi_2025_DAE_Manuscript_Data_Package

Self-contained harmonization script for the WFSFA soil moisture project,
following the conventions in skills/essdive_sm_harmonizer/SKILL.md (SECTION 6).

Notes / limitations (see harmonization_notes.md):
- `swc` is soil (volumetric) water content already in m3 m-3 (range 0.10-0.40).
- `swp` is soil water potential already in kPa (negative, range -8386..-3).
- Measurement depth is not reported anywhere in the package -> depth_m = NaN.
- Sampling is discrete (one observation per site+date) -> is_timeseries = False.
- No coordinates are available in the package, and no location registry is
  staged in this workspace -> qc_flag = "g2" for all sites.
"""

from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

# %%
# =============================================================
# Dataset 4
# =============================================================
BASE_DIR = Path("inputs/raw")
OUT_DIR = Path("output")

idx = 4
DATASET_ID = "ess-dive-6c7085e9c544cc6-20250424T164534831"
PACKAGE_SUBDIR = "Johnsen_Bi_2025_DAE_Manuscript_Data_Package"

DATA_FILE = "df_data.csv"
META_FILE = "df_meta.csv"

pkg_dir = BASE_DIR / DATASET_ID / PACKAGE_SUBDIR
ddf = pd.read_csv(pkg_dir / DATA_FILE)
mdf = pd.read_csv(pkg_dir / META_FILE)

# df_data.csv and df_meta.csv are row-aligned (both 1001 rows); df_meta carries
# the site and observation date for each corresponding measurement row.
if len(ddf) != len(mdf):
    raise ValueError(
        f"Row count mismatch: df_data={len(ddf)} df_meta={len(mdf)}; "
        "cannot align measurements to site/date metadata."
    )

x = pd.DataFrame(index=ddf.index)

# Timestamp: date-only daily values, East River / Snodgrass sites (Colorado).
x["datetime_UTC"] = (
    pd.to_datetime(mdf["datetime"], format="%Y-%m-%d", errors="coerce")
    .dt.tz_localize("America/Denver", ambiguous="NaT", nonexistent="shift_forward")
    .dt.tz_convert("UTC")
)

x["site_id"] = mdf["site"].astype(str)

# Depth not reported in the package.
x["depth_m"] = np.nan

x["replicate"] = np.nan
x["is_timeseries"] = False
x["interval_min"] = np.nan

# swc already in m3 m-3; swp already in kPa (negative). No unit conversion.
x["volumetric_water_content_m3_m3"] = pd.to_numeric(ddf["swc"], errors="coerce")
x["gravimetric_water_content_gH2O_gs"] = np.nan
x["water_potential_kPa"] = pd.to_numeric(ddf["swp"], errors="coerce")

# Coordinates unresolvable in this workspace.
x["qc_flag"] = "g2"

COLS = [
    "datetime_UTC",
    "site_id",
    "depth_m",
    "replicate",
    "is_timeseries",
    "interval_min",
    "volumetric_water_content_m3_m3",
    "gravimetric_water_content_gH2O_gs",
    "water_potential_kPa",
    "qc_flag",
]
df_harmonized = x[COLS].copy()

# Datetimes -> ISO-8601 UTC strings.
df_harmonized["datetime_UTC"] = df_harmonized["datetime_UTC"].dt.strftime(
    "%Y-%m-%dT%H:%M:%SZ"
)

df_harmonized = df_harmonized.sort_values(
    ["datetime_UTC", "site_id", "depth_m"]
).reset_index(drop=True)

# Location accumulator: no coordinates available -> g2.
loc = pd.DataFrame({"site_id": sorted(df_harmonized["site_id"].unique())})
loc["latitude"] = np.nan
loc["longitude"] = np.nan
loc["source_dataset_id"] = DATASET_ID
loc["qc_flag"] = "g2"

if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_csv = OUT_DIR / f"{DATASET_ID}_harmonized.csv"
    df_harmonized.to_csv(out_csv, index=False)
    loc.to_csv(OUT_DIR / f"{DATASET_ID}_location.csv", index=False)
    print(f"Wrote {out_csv} ({len(df_harmonized)} rows)")
    print(df_harmonized.head().to_string())
