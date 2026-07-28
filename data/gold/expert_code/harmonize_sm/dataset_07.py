"""Expert harmonization for dataset index 7.

Auto-split from the expert monolith; the body below is verbatim except that
the shared-accumulator writes are captured into the returned DatasetResult.
"""
from __future__ import annotations

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
    """Harmonize dataset 7, returning its DatasetResult."""
    map_json = ctx.map_json
    REF_IDX = ctx.ref_idx
    dsid = ctx.dsid
    read_ds_csv = ctx.read_ds_csv
    __locations = []

    # =============================================================
    # Dataset 7
    # =============================================================
    idx = 7
    f7 = as_list(map_json[idx]["data_payload_files"])[0]
    m7 = as_list(map_json[idx]["location_metadata_files"])[0]

    ddf7 = read_ds_csv(idx, f7)
    mdf7 = read_ds_csv(idx, m7, encoding='latin-1')

    x = ddf7.copy()

    # datetime: pattern_1 - Convert 'date.time' to ISO 8601 UTC format
    x["datetime_UTC"] = parse_local_to_utc(x["date.time"], "%m/%d/%y %H:%M", "America/Denver")

    # site_id: pattern_1 - Parse site_id from 'Location' in BM_EGM_Well_CO2.csv
    x["site_id"] = "BM"
    x["interval_min"] = interval_min(x["datetime_UTC"])

    # depth: pattern_1 - Rename 'Depth..cm.' variable and divide by 1e2 to convert from cm to m
    x["depth_m"] = pd.to_numeric(x["Depth (cm)"], errors="coerce") / 100

    # replicate: pattern_1 - Replicate information not provided in source; populate with 1
    x["replicate"] = 1
    x["is_timeseries"] = True

    # volumetric_water_content: pattern_1 - Rename 'Volumetric.Water.Content' variable (source units are m3/m3)
    x["volumetric_water_content_m3_m3"] = pd.to_numeric(x["Volumetric Water Content"], errors="coerce")

    # soil_water_potential: pattern_1 - Not reported in source; populate with NA
    x["water_potential_kPa"] = np.nan
    x["gravimetric_water_content_gH2O_gs"] = np.nan

    df7_harmonized = ensure_harmonized_cols(x)
    __harmonized = df7_harmonized
    __dataset_id = dsid(idx)

    # latitude: pattern_1 & longitude: pattern_1
    # Look up 'Latitude (º N)' and 'Longitude (º E)' for 'site_id' in BM_EGM_Well_CO2.csv
    lat_col = [c for c in mdf7.columns if "Latitude" in c][0]
    lon_col = [c for c in mdf7.columns if "Longitude" in c][0]
    loc7 = mdf7.iloc[[0]].rename(columns={"Location": "site_id", lat_col: "latitude", lon_col: "longitude"})[
        ["site_id", "latitude", "longitude"]
    ].copy()
    loc7["source_dataset_id"] = dsid(idx)
    loc7 = add_loc_qc(loc7)
    __locations.append(loc7)

    return DatasetResult(__dataset_id, __harmonized, __locations)
