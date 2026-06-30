"""Expert harmonization for dataset index 4.

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
    """Harmonize dataset 4, returning its DatasetResult."""
    map_json = ctx.map_json
    REF_IDX = ctx.ref_idx
    dsid = ctx.dsid
    read_ds_csv = ctx.read_ds_csv
    __locations = []

    # =============================================================
    # Dataset 4
    # =============================================================
    idx = 4
    f4 = as_list(map_json[idx]["data_payload_files"])[0]
    m4 = as_list(map_json[idx]["location_metadata_files"])[0]
    ddf4 = read_ds_csv(idx, f4)
    mdf4 = read_ds_csv(idx, m4)

    x = pd.concat([ddf4.reset_index(drop=True), mdf4.reset_index(drop=True)], axis=1)
    dt = pd.to_datetime(x["datetime"], errors="coerce").dt.tz_localize("America/Denver", ambiguous="NaT", nonexistent="shift_forward")
    x["datetime_UTC"] = dt.dt.tz_convert("UTC")
    x["site_id"] = x["site"]
    x["depth_m"] = np.nan
    x["replicate"] = 1
    x["is_timeseries"] = True
    x["interval_min"] = 24 * 60
    x["volumetric_water_content_m3_m3"] = pd.to_numeric(x["swc"], errors="coerce")
    x["water_potential_kPa"] = pd.to_numeric(x["swp"], errors="coerce")
    x["gravimetric_water_content_gH2O_gs"] = np.nan
    x = x.sort_values(["datetime_UTC", "site_id"])
    x = x[x["site_id"] != "tb"]

    df4_harmonized = ensure_harmonized_cols(x)
    __harmonized = df4_harmonized
    __dataset_id = dsid(idx)

    loc4 = pd.DataFrame(
        {
            "site_id": ["ph1", "ph2", "sg5"],
            "latitude": [38.92, 38.922583, 38.926250],
            "longitude": [-106.95, -106.947288, -106.98],
        }
    )
    loc4["source_dataset_id"] = dsid(idx)
    loc4 = add_loc_qc(loc4)
    __locations.append(loc4)

    return DatasetResult(__dataset_id, __harmonized, __locations)
