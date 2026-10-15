"""
Harmonization code for dataset index 10.

Dataset: ess-dive-01092fc392bc46d-20240819T143818677
DOI: doi:10.15485/2322567
Title: Hydrological control of chemical weathering and rock-carbon fluxes:
       East River, Colorado (Watershed Function SFA)

Fold-evaluation standalone script. Follows the wfsfa_sm_harmonization skill
code conventions (SECTION 6). It reads only the staged payload file and writes
the required deliverables under output/.
"""

from __future__ import annotations

from pathlib import Path
import re
import numpy as np
import pandas as pd

BASE_DIR = Path("inputs/raw")
OUT_DIR = Path("output")

DATASET_ID = "ess-dive-01092fc392bc46d-20240819T143818677"
idx = 10

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


# %%
# =============================================================
# Dataset 10
# =============================================================
# Wide-format volumetric water content for three PLM sites
# (PLM1, PLM2, PLM3) in the East River watershed. Row 2 of the
# source file is a units row (m3/m3) and is skipped. Values are
# already in m3/m3, so no unit conversion is required. -9999 is a
# missing-value sentinel.

f10 = "Soil_water_content_Fig4e.csv"
ddf10 = pd.read_csv(BASE_DIR / DATASET_ID / f10, skiprows=[1], encoding="utf-8-sig")

x = ddf10.copy()

# Date column is date-only (YYYY-MM-DD); no reported timezone. Treat local
# collection date as Etc/GMT+7 (US Mountain) consistent with other East
# River datasets in this project, then convert to UTC.
dt = pd.to_datetime(x["Date"], format="%Y-%m-%d", errors="coerce")
dt = dt.dt.tz_localize("Etc/GMT+7", ambiguous="NaT", nonexistent="shift_forward")
x["datetime_UTC"] = dt.dt.tz_convert("UTC")

vwc_cols = [c for c in x.columns if re.search(r"vol_water_content", c, flags=re.IGNORECASE)]

long = x.melt(
    id_vars=["datetime_UTC"],
    value_vars=vwc_cols,
    var_name="name",
    value_name="volumetric_water_content_m3_m3",
)

# site_id is embedded in the source column name (e.g., "PLM1 _vol_water_content").
long["site_id"] = long["name"].str.extract(r"(PLM\d+)", flags=re.IGNORECASE)[0]

long["volumetric_water_content_m3_m3"] = pd.to_numeric(
    long["volumetric_water_content_m3_m3"], errors="coerce"
)
long.loc[long["volumetric_water_content_m3_m3"] == -9999, "volumetric_water_content_m3_m3"] = np.nan
long = long.dropna(subset=["volumetric_water_content_m3_m3"])

# Depth not reported in the payload; measurement-depth metadata (Methods PDF)
# is not staged in this fold, so depth_m is left unresolved (NaN).
long["depth_m"] = np.nan
long["replicate"] = 1
long["is_timeseries"] = True
long["gravimetric_water_content_gH2O_gs"] = np.nan
long["water_potential_kPa"] = np.nan

df10_harmonized = ensure_harmonized_cols(long)
df10_harmonized = df10_harmonized.sort_values(
    by=["datetime_UTC", "site_id", "depth_m", "replicate"]
).reset_index(drop=True)

# -------------------------------------------------------------
# Location resolution
# -------------------------------------------------------------
# No per-site coordinates in the payload. Package metadata provides only a
# watershed bounding box (NW/SE corners), not per-PLM-site coordinates. The
# Varadharajan et al. (doi:10.15485/1660962) location registry is referenced
# by the package but is NOT staged in this workspace, so PLM1/PLM2/PLM3
# coordinates are unresolvable. Emit every site with empty lat/lon and qc_flag g2.
loc10 = pd.DataFrame({"site_id": sorted(df10_harmonized["site_id"].dropna().unique())})
loc10["latitude"] = np.nan
loc10["longitude"] = np.nan
loc10["source_dataset_id"] = DATASET_ID
loc10 = add_loc_qc(loc10)
loc10 = loc10[["site_id", "latitude", "longitude", "source_dataset_id", "qc_flag"]]


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df10_harmonized.to_csv(OUT_DIR / f"{DATASET_ID}_harmonized.csv", index=False)
    loc10.to_csv(OUT_DIR / f"{DATASET_ID}_location.csv", index=False)
    print(f"Wrote {DATASET_ID}_harmonized.csv ({len(df10_harmonized)} rows)")
    print(f"Wrote {DATASET_ID}_location.csv ({len(loc10)} rows)")
