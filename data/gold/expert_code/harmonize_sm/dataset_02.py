"""Expert harmonization for dataset index 2.

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
    """Harmonize dataset 2, returning its DatasetResult."""
    map_json = ctx.map_json
    REF_IDX = ctx.ref_idx
    dsid = ctx.dsid
    read_ds_csv = ctx.read_ds_csv
    __locations = []

    # =============================================================
    # Dataset 2
    # =============================================================
    idx = 2
    f2 = as_list(map_json[idx]["data_payload_files"])
    m2 = as_list(map_json[idx]["location_metadata_files"])[0]

    ls2 = [read_ds_csv(idx, x) for x in f2]
    mdf2 = read_ds_csv(idx, m2)

    ls2_h = []
    for i, d in enumerate(ls2):
        # Select moisture-related columns
        cols = [c for c in d.columns if re.search(r"Moisture", c)]
        x = d[["DateTime"] + cols].copy()

        # datetime: pattern_1 - Convert 'DateTime' to ISO 8601 UTC format
        x["datetime_UTC"] = parse_local_to_utc(x["DateTime"], "%m/%d/%Y %I:%M:%S %p", "America/Denver")
        x["interval_min"] = interval_min(x["datetime_UTC"])
        x = x.drop(columns=["DateTime"])

        # volumetric_water_content: pattern_1
        # Coerce from 'wide' format with column variables containing depth and replicate information to 'long' format
        long = x.melt(
            id_vars=["datetime_UTC", "interval_min"],
            var_name="name",
            value_name="volumetric_water_content_m3_m3",
        )

        # depth: pattern_1 - Parse float j from '*_at_jcm' and divide by 1e2 to convert from cm to m
        long["depth_m"] = (
            pd.to_numeric(long["name"].str.split("_").str[-1].str.replace("cm", "", regex=False), errors="coerce") / 100
        )

        # site_id: pattern_1 - Parse site_id from source filename
        long["site_id"] = re.sub(r"\.csv$", "", f2[i])
        long["is_timeseries"] = True

        # soil_water_potential: pattern_1 - Not reported in source; populate with NA
        long["water_potential_kPa"] = np.nan
        long["gravimetric_water_content_gH2O_gs"] = np.nan

        # replicate: pattern_1 - Parse integer i from '*_i_at_jcm'
        long["replicate"] = long.groupby(["datetime_UTC", "depth_m", "name"]).cumcount() + 1

        ls2_h.append(ensure_harmonized_cols(long))

    df2_harmonized = pd.concat(ls2_h, ignore_index=True)
    __harmonized = df2_harmonized
    __dataset_id = dsid(idx)

    # latitude: pattern_1 & longitude: pattern_1
    # Look up 'Northing' and 'Easting' for 'site_id' in SM_loc.csv (stored as 'Lat ' and 'Lon')
    loc2 = mdf2.rename(columns={"Name": "site_id", "Lat ": "latitude", "Lon": "longitude"})[
        ["site_id", "latitude", "longitude"]
    ].copy()
    loc2["source_dataset_id"] = dsid(idx)
    loc2 = add_loc_qc(loc2)
    __locations.append(loc2)

    return DatasetResult(__dataset_id, __harmonized, __locations)
