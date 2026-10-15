"""
Harmonization transformation code for dataset index 27.

Dataset: ess-dive-c37aaf9ed6d4c0d-20230504T205923265966
DOI: doi:10.15485/1788230
Title: Continuous sensor suite measurements of weather, energy, soil and flux
       at four PumpHouse sites at the East River, Colorado (WFSFA SFA).

This is a self-contained fold-evaluation script. Per AGENT_INSTRUCTIONS.md it
reads only from the staged raw inputs and writes all deliverables under output/.

Structure of the source package (one CSV per PumpHouse site):
  ER-PHS1 .. ER-PHS4  -> site_id = ER-PHS1 .. ER-PHS4

Soil sensor layout (from package field notes / measurementTechnique):
  S1 = Teros12 VWC/EC/temp at 115 cm depth (106 cm at ER-PHS4)
  S2 = Teros12 VWC/EC/temp at 60 cm depth
  S3 = Teros12 VWC/EC/temp at 30 cm depth
  S4 = Teros12 VWC/EC/temp at 10 cm depth
  S5 = MPS6 (TEROS 21) soil matric/water potential at 30 cm depth

Harmonized variables extracted:
  Sn_wc_(m3/m3) -> volumetric_water_content_m3_m3 (already m3 m-3; no conversion)
  S5_wp_(kPa)   -> water_potential_kPa            (already kPa, negative)
"""

from __future__ import annotations

from pathlib import Path
import json

import numpy as np
import pandas as pd

BASE_DIR = Path("inputs/raw")
OUT_DIR = Path("output")

idx = 27
DATASET_ID = "ess-dive-c37aaf9ed6d4c0d-20230504T205923265966"

# Local time zone of the East River, Colorado monitoring stations (Mountain Time).
LOCAL_TZ = "America/Denver"
TIME_FMT = "%m/%d/%Y %H:%M"

# Missing-value sentinel used in the water-potential column.
WP_SENTINEL = -99999.0

# Per-file site_id and S1 depth (ER-PHS4 S1 is at 106 cm per field notes).
SITE_FILES = {
    "ER-PHS1": "ER-PHS1_Field dataset_2019_Oct11 to_2020_Mar20.csv",
    "ER-PHS2": "ER-PHS2_Field Dataset_2019_Oct11 to 2020_Apr03.csv",
    "ER-PHS3": "ER-PHS3_Field dataset_2019_Oct12.csv",
    "ER-PHS4": "ER-PHS4_Field Dataset_2019_Oct14 to 2020_Apr03.csv",
}

# Depth (meters) of each soil sensor channel. S1 overridden to 1.06 m at ER-PHS4.
VWC_DEPTH_M = {"S1": 1.15, "S2": 0.60, "S3": 0.30, "S4": 0.10}
WP_DEPTH_M = 0.30  # S5 water potential at 30 cm


def parse_local_to_utc(series: pd.Series, fmt: str | None, tz: str) -> pd.Series:
    dt = pd.to_datetime(series, format=fmt, errors="coerce")
    dt = dt.dt.tz_localize(tz, ambiguous="NaT", nonexistent="shift_forward")
    return dt.dt.tz_convert("UTC")


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


def harmonize_site(site_id: str, path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig")

    s1_depth = 1.06 if site_id == "ER-PHS4" else VWC_DEPTH_M["S1"]
    depth_lookup = {**VWC_DEPTH_M, "S1": s1_depth}

    dt = parse_local_to_utc(df["Time"], TIME_FMT, LOCAL_TZ)

    # --- Volumetric water content (S1-S4), wide -> long ---
    vwc_cols = [f"{s}_wc_(m3/m3)" for s in ["S1", "S2", "S3", "S4"]]
    vwc = pd.DataFrame({"datetime_UTC": dt})
    for c in vwc_cols:
        vwc[c] = pd.to_numeric(df[c], errors="coerce")
    vwc_long = vwc.melt(
        id_vars=["datetime_UTC"],
        value_vars=vwc_cols,
        var_name="sensor",
        value_name="volumetric_water_content_m3_m3",
    )
    vwc_long["sensor"] = vwc_long["sensor"].str.extract(r"^(S\d)")[0]
    vwc_long["depth_m"] = vwc_long["sensor"].map(depth_lookup)
    vwc_long["water_potential_kPa"] = np.nan

    # --- Water potential (S5), already kPa; replace sentinel with NaN ---
    wp_long = pd.DataFrame({"datetime_UTC": dt})
    wp_vals = pd.to_numeric(df["S5_wp_(kPa)"], errors="coerce")
    wp_vals = wp_vals.where(wp_vals > WP_SENTINEL, np.nan)
    wp_long["water_potential_kPa"] = wp_vals
    wp_long["depth_m"] = WP_DEPTH_M
    wp_long["volumetric_water_content_m3_m3"] = np.nan

    long = pd.concat([vwc_long.drop(columns=["sensor"]), wp_long], ignore_index=True)

    # Drop rows where every soil-moisture observation is missing.
    has_obs = (
        long["volumetric_water_content_m3_m3"].notna()
        | long["water_potential_kPa"].notna()
    )
    long = long[has_obs & long["datetime_UTC"].notna()].copy()

    long["site_id"] = site_id
    long["replicate"] = 1
    long["is_timeseries"] = True
    long["gravimetric_water_content_gH2O_gs"] = np.nan

    return ensure_harmonized_cols(long)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ds_dir = BASE_DIR / DATASET_ID

    harmonized_parts = []
    for site_id, fname in SITE_FILES.items():
        harmonized_parts.append(harmonize_site(site_id, ds_dir / fname))

    harmonized = pd.concat(harmonized_parts, ignore_index=True)
    harmonized = harmonized.sort_values(
        by=["datetime_UTC", "site_id", "depth_m", "replicate"]
    ).reset_index(drop=True)
    harmonized["datetime_UTC"] = harmonized["datetime_UTC"].dt.strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    harmonized.to_csv(OUT_DIR / f"{DATASET_ID}_harmonized.csv", index=False)

    # --- Location file: coordinates unresolvable in this workspace -> g2 ---
    # No per-site coordinates exist in the payload, any ancillary file, the
    # cached package metadata (only a watershed bounding box is given), or an
    # approved location registry staged in this workspace. Emit every site_id
    # with empty lat/lon and qc_flag = g2 (do not invent coordinates).
    loc = pd.DataFrame(
        {
            "site_id": list(SITE_FILES.keys()),
            "latitude": [np.nan] * len(SITE_FILES),
            "longitude": [np.nan] * len(SITE_FILES),
            "source_dataset_id": DATASET_ID,
            "qc_flag": "g2",
        }
    )
    loc.to_csv(OUT_DIR / f"{DATASET_ID}_location.csv", index=False)

    print(f"Wrote {len(harmonized)} harmonized rows across {harmonized['site_id'].nunique()} sites.")
    print(harmonized["site_id"].value_counts().to_string())
    print("VWC non-null:", harmonized["volumetric_water_content_m3_m3"].notna().sum())
    print("WP non-null:", harmonized["water_potential_kPa"].notna().sum())


if __name__ == "__main__":
    main()
