"""Expert harmonization for dataset index 6.

Auto-split from the expert monolith; the body below is verbatim except that
the shared-accumulator writes are captured into the returned DatasetResult.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from common import (
    DatasetResult,
    as_list,
    interval_min,
    ensure_harmonized_cols,
    add_loc_qc,
)


def harmonize(ctx):
    """Harmonize dataset 6, returning its DatasetResult."""
    map_json = ctx.map_json
    REF_IDX = ctx.ref_idx
    dsid = ctx.dsid
    read_ds_csv = ctx.read_ds_csv
    __locations = []

    # =============================================================
    # Dataset 6
    # =============================================================
    idx = 6
    f6 = as_list(map_json[idx]["data_payload_files"])[0]
    ddf6 = read_ds_csv(idx, f6)

    x = ddf6.iloc[2:].copy()

    # datetime: pattern_1 - Convert 'TIMESTAMP' to ISO 8601 UTC format
    x["datetime_UTC"] = pd.to_datetime(x["TIMESTAMP"], format="%m/%d/%y %H:%M", errors="coerce", utc=True)

    # site_id: pattern_1 - Rename column 'site' to 'site_id'
    x["site_id"] = x["site"]
    x["interval_min"] = interval_min(x["datetime_UTC"])

    # volumetric_water_content: pattern_1
    # Coerce from 'wide' format with column variables containing depth information to 'long' format
    vwc_cols = [c for c in x.columns if "VWC" in c]
    long = x.melt(
        id_vars=["datetime_UTC", "site_id", "interval_min"],
        value_vars=vwc_cols,
        var_name="name",
        value_name="volumetric_water_content_m3_m3",
    )

    # depth: pattern_1 - Parse float j from 'VWC_jcm' and divide by 1e2 to convert from cm to m
    long["depth_m"] = (
        pd.to_numeric(long["name"].str.split("_").str[-1].str.replace("cm", "", regex=False), errors="coerce") / 100
    )

    # replicate: pattern_1 - Replicate information not provided in source; populate with 1
    long["replicate"] = 1
    long["is_timeseries"] = True

    # soil_water_potential: pattern_1 - Not reported in source; populate with NA
    long["water_potential_kPa"] = np.nan
    long["gravimetric_water_content_gH2O_gs"] = np.nan

    df6_harmonized = ensure_harmonized_cols(long)
    __harmonized = df6_harmonized
    __dataset_id = dsid(idx)

    # latitude: pattern_1 & longitude: pattern_1
    # Look up 'latitude' and 'longitude' for 'site_id' in data file
    loc6 = (
        ddf6.iloc[2:]
        .groupby("site", as_index=False)
        .first()[["site", "latitude", "longitude"]]
        .rename(columns={"site": "site_id"})
    )
    loc6["source_dataset_id"] = dsid(idx)
    loc6 = add_loc_qc(loc6)
    __locations.append(loc6)

    return DatasetResult(__dataset_id, __harmonized, __locations)
