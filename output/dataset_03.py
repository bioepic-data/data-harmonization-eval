# %%
# =============================================================
# Dataset 3
# ess-dive-4c1829de1b8a2ec-20260220T045039633
# =============================================================
#
# Soil water potential (matric potential) sensor time series from the
# East River / Coal Creek SFA "North Facing Hillslope Sagebrush Site 1"
# (Location_ID ER-LLN1). Wide-format CR-logger export with matric potential
# and soil temperature per sensor. Depth (25/60 cm) and station (SD1/SD11)
# are embedded in the column names. This block follows the SECTION 6/7
# conventions in skills/essdive_sm_harmonizer/SKILL.md and mirrors the
# wide->long melt/pivot pattern used by the expert code for dataset 8
# (data/gold/expert_code/dataset_08.py).

from __future__ import annotations

from pathlib import Path
import re

import numpy as np
import pandas as pd


BASE_DIR = Path("inputs/raw")
OUT_DIR = Path("output")

IDX = 3
DATASET_ID = "ess-dive-4c1829de1b8a2ec-20260220T045039633"
DOI = None  # not available in the run workspace; recorded as unresolved (see notes)

DATA_FILE = "Soil_water_potential.csv"
LOC_FILE = "locations.csv"

# Sensor error / out-of-range sentinel used by the datalogger for matric
# potential (readings below the sensor's measurable dry limit are reported
# as exactly -7999). Treated as missing.
MP_SENTINEL = -7999.0

# East River, Colorado -> Mountain Time. Logger timestamps carry no offset;
# harmonized to UTC using a fixed no-DST Mountain offset (UTC-7), consistent
# with the "Etc/GMT+7" handling the expert code uses for the same SFA loggers.
LOCAL_TZ = "Etc/GMT+7"


def ensure_harmonized_cols(df: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "datetime_UTC",
        "site_id",
        "depth_m",
        "replicate",
        "is_timeseries",
        "interval_min",
        "volumetric_water_content_m3_m3",
        "gravimetric_water_content_gH2O_gs",
        "water_potential_kPa",
    ]
    for c in cols:
        if c not in df.columns:
            df[c] = np.nan
    return df[cols]


def parse_mp_column(name: str):
    """Parse (site_id, depth_m, replicate) from a matric-potential column name.

    Examples:
      SD11-25cm_MP                       -> (SD11, 0.25, 1)
      SD11-60cm_MP_2_Avg                 -> (SD11, 0.60, 1)
      SD1-25cm_MP_3_Avg                  -> (SD1,  0.25, 1)
      SD1-60cm_MP_4_Avg                  -> (SD1,  0.60, 1)
      SD1-25cm_sagebrush_rhizo_MP_5_Avg  -> (SD1,  0.25, 2)  # rhizosphere sensor
    """
    m = re.match(r"^(SD\d+)-(\d+(?:\.\d+)?)cm_(.*)$", name)
    if not m:
        return None
    site_id = m.group(1)
    depth_m = float(m.group(2)) / 100.0
    remainder = m.group(3)
    # A second sensor co-located at the same station+depth (the sagebrush
    # rhizosphere probe) is treated as a distinct replicate.
    replicate = 2 if "rhizo" in remainder.lower() else 1
    return site_id, depth_m, replicate


def harmonize():
    ddf = pd.read_csv(BASE_DIR / DATASET_ID / DATA_FILE)
    mdf = pd.read_csv(BASE_DIR / DATASET_ID / LOC_FILE)

    # UTC timestamp
    dt_local = pd.to_datetime(ddf["TIMESTAMP"], errors="coerce")
    dt_local = dt_local.dt.tz_localize(
        LOCAL_TZ, ambiguous="NaT", nonexistent="shift_forward"
    )
    ddf = ddf.copy()
    ddf["datetime_UTC"] = dt_local.dt.tz_convert("UTC")

    mp_cols = [c for c in ddf.columns if re.match(r"^SD\d+-\d", c) and "_MP" in c]

    frames = []
    for c in mp_cols:
        parsed = parse_mp_column(c)
        if parsed is None:
            continue
        site_id, depth_m, replicate = parsed
        vals = pd.to_numeric(ddf[c], errors="coerce")
        vals = vals.replace([np.inf, -np.inf], np.nan)
        vals = vals.mask(vals == MP_SENTINEL, np.nan)
        sub = pd.DataFrame(
            {
                "datetime_UTC": ddf["datetime_UTC"],
                "site_id": site_id,
                "depth_m": depth_m,
                "replicate": replicate,
                "water_potential_kPa": vals,
            }
        )
        frames.append(sub)

    x = pd.concat(frames, ignore_index=True)
    x = x[x["water_potential_kPa"].notna()].copy()

    x["is_timeseries"] = True
    x["volumetric_water_content_m3_m3"] = np.nan
    x["gravimetric_water_content_gH2O_gs"] = np.nan

    # interval_min from median timestamp difference per site+depth+replicate
    x = x.sort_values(["site_id", "depth_m", "replicate", "datetime_UTC"])
    diffs = (
        x.groupby(["site_id", "depth_m", "replicate"])["datetime_UTC"]
        .diff()
        .dt.total_seconds()
        / 60.0
    )
    x["interval_min"] = float(np.nanmedian(diffs.values))

    harmonized = ensure_harmonized_cols(x)

    # Location resolution: the package ancillary locations.csv provides a single
    # coordinate for the hillslope site (Location_ID ER-LLN1). The logger station
    # IDs (SD1, SD11) do not appear as Location_IDs, so the single site-level
    # coordinate is applied to both stations. qc_flag = g1 (coordinates from a
    # supplied location file, not a 1:1 per-station match).
    lat = pd.to_numeric(mdf["Latitude"], errors="coerce").iloc[0]
    lon = pd.to_numeric(mdf["Longitude"], errors="coerce").iloc[0]
    site_ids = sorted(harmonized["site_id"].dropna().unique())
    loc = pd.DataFrame(
        {
            "site_id": site_ids,
            "latitude": lat,
            "longitude": lon,
        }
    )
    loc["source_dataset_id"] = DATASET_ID
    loc["qc_flag"] = np.where(loc["latitude"].isna() | loc["longitude"].isna(), "g2", "g1")

    return harmonized, loc


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    harmonized, loc = harmonize()

    harmonized_out = harmonized.sort_values(
        by=["datetime_UTC", "site_id", "depth_m", "replicate"]
    )
    harmonized_out.to_csv(OUT_DIR / f"{DATASET_ID}_harmonized.csv", index=False)
    loc.to_csv(OUT_DIR / f"{DATASET_ID}_location.csv", index=False)

    print(f"Wrote {DATASET_ID}_harmonized.csv ({len(harmonized_out)} rows)")
    print(f"Wrote {DATASET_ID}_location.csv ({len(loc)} rows)")
    print(harmonized_out.head().to_string())
    print(loc.to_string())
