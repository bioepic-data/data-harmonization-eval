"""Expert harmonization for dataset index 24.

Auto-split from the expert monolith; the body below is verbatim except that
the shared-accumulator writes are captured into the returned DatasetResult.
"""
from __future__ import annotations

import re
import numpy as np
import pandas as pd

from common import (
    DatasetResult,
    as_list,
    parse_local_to_utc,
    interval_min,
    ensure_harmonized_cols,
    add_loc_qc,
)


def harmonize(ctx):
    """Harmonize dataset 24, returning its DatasetResult."""
    map_json = ctx.map_json
    REF_IDX = ctx.ref_idx
    dsid = ctx.dsid
    read_ds_csv = ctx.read_ds_csv
    __locations = []

    # =============================================================
    # Dataset 24
    # =============================================================
    idx = 24
    f24 = as_list(map_json[idx]["data_payload_files"])[0]
    m24 = as_list(map_json[idx]["location_metadata_files"])[0]

    ddf24 = read_ds_csv(idx, f24, sep=";")
    mdf24 = read_ds_csv(idx, m24, sep=";")

    x = ddf24.copy()

    # Select relevant columns (timestamp and matric potential at specific depths)
    keep = ["Timestamp"] + [c for c in x.columns if re.search(r"^P[12]_MP_(15|30|60)$", c)]
    x = x[keep]

    # datetime: pattern_1 - Convert 'Timestamp' to ISO 8601 UTC format
    x["datetime_UTC"] = parse_local_to_utc(x["Timestamp"], "%Y-%m-%d", "America/Denver")
    x["interval_min"] = interval_min(x["datetime_UTC"])
    x = x.drop(columns=["Timestamp"])

    # soil_water_potential: pattern_1
    # Coerce from 'wide' format with column variables containing site and depth information to 'long' format
    mp_cols = [c for c in x.columns if re.search(r"^P[12]_MP_(15|30|60)$", c)]
    long = x.melt(id_vars=["datetime_UTC", "interval_min"], value_vars=mp_cols, var_name="name", value_name="MP")

    # site_id: pattern_1 - Parse 'P1' or 'P2' from column name
    m = long["name"].str.extract(r"^(P[12])_(MP)_(\d+)$")
    long["site_id"] = m[0]
    long["depth_cm"] = m[2]
    long = long[long["MP"].notna()].copy()

    # depth: pattern_1 - Parse depth (cm) from column name and divide by 1e2 to convert to m
    long["depth_m"] = pd.to_numeric(long["depth_cm"], errors="coerce") / 100

    # replicate: pattern_1 - Replicate information not provided in source; populate with 1
    long["replicate"] = 1
    long["is_timeseries"] = True

    # volumetric_water_content: pattern_1 - Not reported in source; populate with NA
    long["volumetric_water_content_m3_m3"] = np.nan
    long["gravimetric_water_content_gH2O_gs"] = np.nan

    # Rename water potential variable (source units are kPa)
    long["water_potential_kPa"] = pd.to_numeric(long["MP"], errors="coerce")
    long = long[long["water_potential_kPa"].notna()]

    df24_harmonized = ensure_harmonized_cols(long)
    __harmonized = df24_harmonized
    __dataset_id = dsid(idx)

    # latitude: pattern_1 & longitude: pattern_1
    # Look up 'Latitude' and 'Longitude' for 'ID' in location metadata
    loc24 = mdf24.rename(columns={"ID": "site_id", "Latitude": "latitude", "Longitude": "longitude"})[
        ["site_id", "latitude", "longitude"]
    ].copy()
    loc24 = loc24[loc24["site_id"].isin(df24_harmonized["site_id"].dropna().unique())].drop_duplicates()
    loc24["source_dataset_id"] = dsid(idx)
    loc24 = add_loc_qc(loc24)
    __locations.append(loc24)

    return DatasetResult(__dataset_id, __harmonized, __locations)
