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
    x["datetime_UTC"] = parse_local_to_utc(x["date.time"], "%m/%d/%y %H:%M", "America/Denver")
    x["site_id"] = "BM"
    x["interval_min"] = interval_min(x["datetime_UTC"])
    x["depth_m"] = pd.to_numeric(x["Depth (cm)"], errors="coerce") / 100
    x["replicate"] = 1
    x["is_timeseries"] = True
    x["volumetric_water_content_m3_m3"] = pd.to_numeric(x["Volumetric Water Content"], errors="coerce")
    x["water_potential_kPa"] = np.nan
    x["gravimetric_water_content_gH2O_gs"] = np.nan

    df7_harmonized = ensure_harmonized_cols(x)
    __harmonized = df7_harmonized
    __dataset_id = dsid(idx)

    lat_col = [c for c in mdf7.columns if "Latitude" in c][0]
    lon_col = [c for c in mdf7.columns if "Longitude" in c][0]
    loc7 = mdf7.iloc[[0]].rename(columns={"Location": "site_id", lat_col: "latitude", lon_col: "longitude"})[
        ["site_id", "latitude", "longitude"]
    ].copy()
    loc7["source_dataset_id"] = dsid(idx)
    loc7 = add_loc_qc(loc7)
    __locations.append(loc7)

    return DatasetResult(__dataset_id, __harmonized, __locations)
