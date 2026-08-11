"""Expert harmonization for dataset index 8.

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
    """Harmonize dataset 8, returning its DatasetResult."""
    map_json = ctx.map_json
    REF_IDX = ctx.ref_idx
    dsid = ctx.dsid
    read_ds_csv = ctx.read_ds_csv
    __locations = []

    # =============================================================
    # Dataset 8
    # =============================================================
    idx = 8
    f8 = as_list(map_json[idx]["data_payload_files"])
    m8 = as_list(map_json[idx]["location_metadata_files"])

    ls8 = [read_ds_csv(idx, x) for x in f8]
    mdf8 = pd.concat([read_ds_csv(idx, x) for x in m8], ignore_index=True)

    ls8_h = []
    for d in ls8:
        # Select soil moisture and water potential columns
        cols = [c for c in d.columns if re.search(r"SoilMoisture|SoilMatricPot", c)]
        x = d[["DateTime.MST"] + cols].copy()

        # datetime: pattern_1 - Convert 'DateTime.MST' to ISO 8601 UTC format
        x["datetime_UTC"] = parse_local_to_utc(x["DateTime.MST"], "%Y-%m-%d %H:%M:%S", "America/Denver")
        x["interval_min"] = interval_min(x["datetime_UTC"])
        x = x.drop(columns=["DateTime.MST"])
        x.columns = [re.sub(r"\.m3\.m3|\.kPa", "", c) for c in x.columns]

        # volumetric_water_content: pattern_1 & soil_water_potential: pattern_1
        # Coerce from 'wide' format with column variables containing depth information to 'long' format
        value_cols = [c for c in x.columns if re.search(r"SoilMoisture|SoilMatricPot", c)]
        long = x.melt(id_vars=["datetime_UTC", "interval_min"], value_vars=value_cols, var_name="name", value_name="value")
        m = long["name"].str.extract(r"^(SoilMoisture|SoilMatricPot)_(.*)$")
        long["var"] = m[0]

        # depth: pattern_1 - Parse float j from '*_jcm.*' and divide by 1e2 to convert from cm to m
        long["depth_m"] = pd.to_numeric(m[1].str.replace("cm", "", regex=False), errors="coerce") / 100
        long["value"] = pd.to_numeric(long["value"], errors="coerce")
        long.loc[long["value"] == -9999, "value"] = np.nan

        wide = (
            long.pivot_table(
                index=["datetime_UTC", "interval_min", "depth_m"],
                columns="var",
                values="value",
                aggfunc="first",
            )
            .reset_index()
            .rename(columns={"SoilMoisture": "volumetric_water_content_m3_m3", "SoilMatricPot": "water_potential_kPa"})
        )

        # replicate: pattern_1 - Replicate information not provided in source; populate with 1
        wide["replicate"] = 1

        # site_id: pattern_1 - Parse site_id from source filename
        wide["site_id"] = "Slate River OBJ-2"
        wide["is_timeseries"] = True
        wide["gravimetric_water_content_gH2O_gs"] = np.nan

        ls8_h.append(ensure_harmonized_cols(wide))

    df8_harmonized = pd.concat(ls8_h, ignore_index=True)
    __harmonized = df8_harmonized
    __dataset_id = dsid(idx)

    # latitude: pattern_1 & longitude: pattern_1
    # Look up 'Latitude' and 'Longitude' for 'site_id' in location metadata file
    loc8 = mdf8.iloc[[0]].rename(columns={"SiteName": "site_id", "Latitude": "latitude", "Longitude": "longitude"})[
        ["site_id", "latitude", "longitude"]
    ].copy()
    loc8["source_dataset_id"] = dsid(idx)
    loc8 = add_loc_qc(loc8)
    __locations.append(loc8)

    return DatasetResult(__dataset_id, __harmonized, __locations)
