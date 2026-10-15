"""
Dataset 16 harmonization — fold-05 targeted leave-one-out.

Dataset: ess-dive-b3d271f19a94e8d-20260114T204512119
DOI: doi:10.15485/3007697
Title: Meteorological and Soil Data from Ecohydrology Sensor Towers at Pump
       House and Snodgrass Mountain in East River Watershed, Colorado, 2019-2025.

Self-contained transformation script for the fold run environment. Reads raw
package files from inputs/raw/<dataset_identifier>/ and writes the five required
deliverables under output/. Follows the WFSFA soil-moisture harmonization
schema (SKILL.md Sections 1, 6, 7).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

# -------------------------------------------------------------------
# Paths / configuration
# -------------------------------------------------------------------
IDX = 16
DATASET_ID = "ess-dive-b3d271f19a94e8d-20260114T204512119"
DOI = "doi:10.15485/3007697"

BASE_DIR = Path("inputs/raw")
OUT_DIR = Path("output")
PKG_DIR = BASE_DIR / DATASET_ID / "WFSFA_EHG_SensorTowers_Wu_et_al"

SITE_META_FILE = "metadata_site_v1-1.csv"
INST_META_FILE = "metadata_instrument_v1-1.csv"

DATA_FILES = [
    "data_ER-PHS1_v1-1.csv",
    "data_ER-PHS2_v1-1.csv",
    "data_ER-PHS3_v1-1.csv",
    "data_ER-PHS4_v1-1.csv",
    "data_SG-EHS5_v1-1.csv",
    "data_SG-EHS6_v1-1.csv",
    "data_SG-EHS7_v1-1.csv",
    "data_SG-EHS8_v1-1.csv",
]

# Timezone: site metadata reports UTC_OFFSET = -7 for all sites (Mountain
# Standard Time, no DST) -> fixed offset. Etc/GMT+7 is UTC-7 (POSIX sign flip).
LOCAL_TZ = "Etc/GMT+7"

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


def site_id_from_filename(fname: str) -> str:
    m = re.match(r"data_(.+?)_v\d", fname)
    return m.group(1) if m else fname


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------------
    # Instrument metadata -> depth lookup per (site, variable).
    # HEIGHT is negative (below surface); depth_m = abs(HEIGHT).
    # ---------------------------------------------------------------
    inst = pd.read_csv(PKG_DIR / INST_META_FILE)
    sw = inst[inst["VARIABLE"].str.match(r"^SW[CP]_")].copy()
    sw["HEIGHT"] = pd.to_numeric(sw["HEIGHT"], errors="coerce")
    # HEIGHT is stable per (site, variable); take the first.
    depth_lookup = (
        sw.groupby(["SITE_ID", "VARIABLE"])["HEIGHT"].first().abs().to_dict()
    )

    # ---------------------------------------------------------------
    # Harmonize each per-site data file.
    # ---------------------------------------------------------------
    harmonized_parts: list[pd.DataFrame] = []

    for fname in DATA_FILES:
        site_id = site_id_from_filename(fname)
        df = pd.read_csv(PKG_DIR / fname)

        dt_utc = (
            pd.to_datetime(df["TIMESTAMP_START"], format="%Y-%m-%d %H:%M:%S",
                           errors="coerce")
            .dt.tz_localize(LOCAL_TZ, ambiguous="NaT", nonexistent="shift_forward")
            .dt.tz_convert("UTC")
        )

        swc_cols = [c for c in df.columns if c.startswith("SWC_")]
        swp_cols = [c for c in df.columns if c.startswith("SWP_")]

        parts = []

        # --- Soil water content (VWC, % -> m3/m3) ---
        if swc_cols:
            base = pd.DataFrame({"datetime_UTC": dt_utc})
            for c in swc_cols:
                base[c] = df[c]
            long = base.melt(
                id_vars=["datetime_UTC"],
                value_vars=swc_cols,
                var_name="source_variable",
                value_name="value",
            )
            long["site_id"] = site_id
            long["depth_m"] = long["source_variable"].map(
                lambda v: depth_lookup.get((site_id, v), np.nan)
            )
            val = pd.to_numeric(long["value"], errors="coerce")
            val = val.where(val != -9999.0, np.nan)  # numeric missing code
            long["volumetric_water_content_m3_m3"] = val / 100.0
            long["water_potential_kPa"] = np.nan
            long = long[long["volumetric_water_content_m3_m3"].notna()]
            parts.append(long)

        # --- Soil water potential (kPa, missing code +9999) ---
        if swp_cols:
            base = pd.DataFrame({"datetime_UTC": dt_utc})
            for c in swp_cols:
                base[c] = df[c]
            long = base.melt(
                id_vars=["datetime_UTC"],
                value_vars=swp_cols,
                var_name="source_variable",
                value_name="value",
            )
            long["site_id"] = site_id
            long["depth_m"] = long["source_variable"].map(
                lambda v: depth_lookup.get((site_id, v), np.nan)
            )
            val = pd.to_numeric(long["value"], errors="coerce")
            val = val.where(val != 9999.0, np.nan)  # SWP missing code is +9999
            long["water_potential_kPa"] = val
            long["volumetric_water_content_m3_m3"] = np.nan
            long = long[long["water_potential_kPa"].notna()]
            parts.append(long)

        if parts:
            site_long = pd.concat(parts, ignore_index=True)
            site_long["replicate"] = 1
            site_long["is_timeseries"] = True
            site_long["gravimetric_water_content_gH2O_gs"] = np.nan
            harmonized_parts.append(site_long)

    harmonized = ensure_harmonized_cols(
        pd.concat(harmonized_parts, ignore_index=True)
    )
    harmonized = harmonized.sort_values(
        ["datetime_UTC", "site_id", "depth_m", "replicate"]
    ).reset_index(drop=True)

    harmonized.to_csv(OUT_DIR / f"{DATASET_ID}_harmonized.csv", index=False)

    # ---------------------------------------------------------------
    # Location file: one row per distinct site_id, from site metadata.
    # ---------------------------------------------------------------
    site_meta = pd.read_csv(PKG_DIR / SITE_META_FILE)
    loc = site_meta.rename(
        columns={
            "SITE_ID": "site_id",
            "LOCATION_LAT": "latitude",
            "LOCATION_LONG": "longitude",
        }
    )[["site_id", "latitude", "longitude"]].copy()

    present = sorted(harmonized["site_id"].dropna().astype(str).unique())
    loc = loc[loc["site_id"].isin(present)].copy()
    loc["latitude"] = pd.to_numeric(loc["latitude"], errors="coerce")
    loc["longitude"] = pd.to_numeric(loc["longitude"], errors="coerce")
    loc["source_dataset_id"] = DATASET_ID
    loc = add_loc_qc(loc)
    loc = loc.drop_duplicates(subset=["site_id"]).sort_values("site_id")
    loc = loc[["site_id", "latitude", "longitude", "source_dataset_id", "qc_flag"]]

    loc.to_csv(OUT_DIR / f"{DATASET_ID}_location.csv", index=False)

    # ---------------------------------------------------------------
    # Change-mapping JSON entry.
    # ---------------------------------------------------------------
    mapping_entry = build_mapping_entry()
    with open(OUT_DIR / f"{DATASET_ID}_mapping.json", "w", encoding="utf-8") as f:
        json.dump(mapping_entry, f, indent=2)

    print(f"harmonized rows: {len(harmonized)}")
    print(f"location rows:   {len(loc)}")
    print(harmonized["site_id"].value_counts().to_string())


def build_mapping_entry() -> dict:
    data_files = DATA_FILES
    return {
        "index": IDX,
        "dataset_identifier": DATASET_ID,
        "doi": DOI,
        "archive_repository": "ESS-DIVE",
        "inclusion_decision": "include",
        "exclusion_reason": None,
        "data_payload_files": data_files,
        "location_metadata_files": [SITE_META_FILE],
        "sensor_metadata_files": [INST_META_FILE],
        "harmonization_mappings": {
            "datetime": {
                "pattern_1": {
                    "source_pattern": "TIMESTAMP_START",
                    "source_files": data_files,
                    "destination_variable": "datetime_UTC",
                    "transformation": (
                        "Parse TIMESTAMP_START with format '%Y-%m-%d %H:%M:%S' "
                        "in fixed local time (Etc/GMT+7, i.e. UTC-7, per site "
                        "metadata UTC_OFFSET=-7) and convert to UTC."
                    ),
                    "unit_conversion": None,
                }
            },
            "site_id": {
                "pattern_1": {
                    "source_pattern": r"data_(.+?)_v\d",
                    "source_files": data_files,
                    "destination_variable": "site_id",
                    "transformation": (
                        "Site identifier taken from the {SITE_ID} token embedded "
                        "in each per-site data filename."
                    ),
                    "unit_conversion": None,
                }
            },
            "depth": {
                "pattern_1": {
                    "source_pattern": "HEIGHT (metadata_instrument_v1-1.csv)",
                    "source_files": [INST_META_FILE],
                    "destination_variable": "depth_m",
                    "transformation": (
                        "Join each SWC_1_V_1 / SWP_1_1_1 observation column to the "
                        "instrument metadata by (SITE_ID, VARIABLE); use the "
                        "sensor installation HEIGHT (negative, below surface) as "
                        "the measurement depth."
                    ),
                    "unit_conversion": (
                        "Take absolute value of HEIGHT (already in meters) to "
                        "express depth below surface as a positive value."
                    ),
                }
            },
            "volumetric_water_content": {
                "pattern_1": {
                    "source_pattern": r"SWC_1_\d_1",
                    "source_files": data_files,
                    "destination_variable": "volumetric_water_content_m3_m3",
                    "transformation": (
                        "Melt the SWC_1_V_1 wide columns to long form; one row per "
                        "timestamp/site/depth. Missing-value code -9999 set to NaN."
                    ),
                    "unit_conversion": "Divide by 100 to convert from % to m3 m-3.",
                }
            },
            "water_potential": {
                "pattern_1": {
                    "source_pattern": "SWP_1_1_1",
                    "source_files": data_files,
                    "destination_variable": "water_potential_kPa",
                    "transformation": (
                        "Melt the SWP_1_1_1 column to long form. Already negative "
                        "kPa; missing-value code +9999 set to NaN (SWP uses +9999 "
                        "because valid values are negative)."
                    ),
                    "unit_conversion": None,
                }
            },
            "latitude": {
                "pattern_1": {
                    "source_pattern": "LOCATION_LAT",
                    "source_files": [SITE_META_FILE],
                    "destination_variable": "latitude",
                    "transformation": (
                        "Look up latitude by matching site_id to SITE_ID in the "
                        "package site metadata file."
                    ),
                    "unit_conversion": None,
                }
            },
            "longitude": {
                "pattern_1": {
                    "source_pattern": "LOCATION_LONG",
                    "source_files": [SITE_META_FILE],
                    "destination_variable": "longitude",
                    "transformation": (
                        "Look up longitude by matching site_id to SITE_ID in the "
                        "package site metadata file."
                    ),
                    "unit_conversion": None,
                }
            },
        },
    }


if __name__ == "__main__":
    main()
