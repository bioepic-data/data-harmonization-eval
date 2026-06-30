"""Expert harmonization for dataset index 26.

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
    """Harmonize dataset 26, returning its DatasetResult."""
    map_json = ctx.map_json
    REF_IDX = ctx.ref_idx
    dsid = ctx.dsid
    read_ds_csv = ctx.read_ds_csv
    __locations = []

    # =============================================================
    # Dataset 26
    # =============================================================
    idx = 26
    f26 = as_list(map_json[idx]["data_payload_files"])[0]
    m26 = as_list(map_json[REF_IDX]["location_metadata_files"])[0]

    ddf26 = read_ds_csv(idx, f26, index_col=0)
    mdf26 = read_ds_csv(REF_IDX, m26)

    x = ddf26.copy()
    x["datetime_UTC"] = parse_local_to_utc(x["Collection date"], "%m/%d/%y", "America/Denver")
    x["site_id"] = x["SampleSiteCode"]
    x["depth_m"] = (pd.to_numeric(x["Top sample depth_cm"], errors="coerce") + pd.to_numeric(x["Bottom sample depth_cm"], errors="coerce")) / 2 / 100
    x["replicate"] = 1
    x["is_timeseries"] = False
    x["interval_min"] = np.nan
    x["volumetric_water_content_m3_m3"] = pd.to_numeric(x["water content %vol"], errors="coerce") / 100
    x["gravimetric_water_content_gH2O_gs"] = np.nan
    x["water_potential_kPa"] = np.nan

    df26_harmonized = ensure_harmonized_cols(x)
    __harmonized = df26_harmonized
    __dataset_id = dsid(idx)

    loc26 = mdf26.rename(columns={"Location_ID": "site_id", "Latitude": "latitude", "Longitude": "longitude"})[
        ["site_id", "latitude", "longitude"]
    ].copy()
    loc26 = loc26[loc26["site_id"].isin(df26_harmonized["site_id"].dropna().unique())]
    loc26["source_dataset_id"] = dsid(idx)
    loc26 = add_loc_qc(loc26)
    __locations.append(loc26)

    return DatasetResult(__dataset_id, __harmonized, __locations)
