"""Expert harmonization for dataset index 9.

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
    utm32613_to_latlon,
    ensure_harmonized_cols,
    add_loc_qc,
)


def harmonize(ctx):
    """Harmonize dataset 9, returning its DatasetResult."""
    map_json = ctx.map_json
    REF_IDX = ctx.ref_idx
    dsid = ctx.dsid
    read_ds_csv = ctx.read_ds_csv
    __locations = []

    # =============================================================
    # Dataset 9
    # =============================================================
    idx = 9
    f9 = as_list(map_json[idx]["data_payload_files"])[0]
    m9 = as_list(map_json[idx]["location_metadata_files"])[0]

    ddf9 = read_ds_csv(idx, f9)
    mdf9 = read_ds_csv(idx, m9)

    x = ddf9.copy()
    x["datetime_UTC"] = parse_local_to_utc(x["Collection Date"], "%Y-%m-%d", "America/Denver")
    x["site_id"] = x["SampleSiteCode"]
    x["interval_min"] = np.nan
    x["depth_m"] = 0.2
    x["is_timeseries"] = False
    x["water_potential_kPa"] = np.nan

    long = x.melt(
        id_vars=["datetime_UTC", "site_id", "interval_min", "depth_m", "is_timeseries", "water_potential_kPa"],
        value_vars=["VWC_1", "VWC_2"],
        var_name="tmp",
        value_name="VWC",
    )
    long["replicate"] = long["tmp"].str.extract(r"_(\d+)")[0]
    long["VWC"] = pd.to_numeric(long["VWC"], errors="coerce")
    long.loc[long["VWC"] == -9999.0, "VWC"] = np.nan
    long = long[long["VWC"].notna()].copy()
    long["volumetric_water_content_m3_m3"] = long["VWC"]
    long["gravimetric_water_content_gH2O_gs"] = np.nan

    df9_harmonized = ensure_harmonized_cols(long)
    __harmonized = df9_harmonized
    __dataset_id = dsid(idx)

    loc9_tmp = utm32613_to_latlon(mdf9, "Easting", "Northing")
    loc9 = pd.DataFrame(
        {
            "site_id": loc9_tmp["SampleSiteCode"],
            "latitude": loc9_tmp["latitude"],
            "longitude": loc9_tmp["longitude"],
        }
    )
    loc9["source_dataset_id"] = dsid(idx)
    loc9 = add_loc_qc(loc9)
    __locations.append(loc9)

    return DatasetResult(__dataset_id, __harmonized, __locations)
