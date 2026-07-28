"""Expert harmonization for dataset index 18.

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
    """Harmonize dataset 18, returning its DatasetResult."""
    map_json = ctx.map_json
    REF_IDX = ctx.ref_idx
    dsid = ctx.dsid
    read_ds_csv = ctx.read_ds_csv
    __locations = []

    # =============================================================
    # Dataset 18
    # =============================================================
    idx = 18
    f18 = as_list(map_json[idx]["data_payload_files"])[0]
    m18 = as_list(map_json[idx]["location_metadata_files"])[0]

    ddf18 = read_ds_csv(idx, f18, encoding="latin1")
    mdf18 = read_ds_csv(idx, m18, encoding="latin1")

    x = ddf18.copy()

    # datetime: pattern_1 - Convert 'Date_Collected' to ISO 8601 UTC format
    x["datetime_UTC"] = parse_local_to_utc(x["Date_Collected"], "%m/%d/%Y", "America/Denver")
    x["interval_min"] = np.nan

    # site_id: pattern_1 - Construct site_id from 'Field_Site', 'Plot', and 'Topographic_Position'
    x["site_id"] = (x["Field_Site"].astype(str) + "_" + x["Plot"].astype(str) + "_" + x["Topographic_Position"].astype(str)).str.replace(r"_$", "", regex=True)

    # depth: pattern_1 - Parse depth from 'Depth_Increment' categorical values
    x["depth_m"] = np.select(
        [
            x["Depth_Increment"].eq("0-5 cm"),
            x["Depth_Increment"].isin(["5-15 cm", "15-May"]),
            x["Depth_Increment"].eq("15 cm +"),
        ],
        [0.025, 0.10, 0.15],
        default=np.nan,
    )
    x["is_timeseries"] = False

    # soil_water_potential: pattern_1 - Not reported in source; populate with NA
    x["water_potential_kPa"] = np.nan

    # volumetric_water_content: pattern_1 - Not reported in source; populate with NA
    x["volumetric_water_content_m3_m3"] = np.nan

    # gravimetric_water_content: pattern_1 - Rename 'Soil Water Content (g H2O per gram  soil)' variable
    x["gravimetric_water_content_gH2O_gs"] = pd.to_numeric(x["Soil Water Content (g H2O per gram  soil)"], errors="coerce")

    # replicate: pattern_1 - Use 'Replicate' column
    x["replicate"] = x["Replicate"]

    df18_harmonized = ensure_harmonized_cols(x)
    __harmonized = df18_harmonized
    __dataset_id = dsid(idx)

    # latitude: pattern_1 & longitude: pattern_1
    # Look up 'Latitude' and 'Longitude' for constructed 'site_id' in location metadata
    loc18 = mdf18.copy()
    loc18["site_id"] = (loc18["Field_Site"].astype(str) + "_" + loc18["Plot"].astype(str) + "_" + loc18["Topographic_Position"].astype(str)).str.replace(r"_$", "", regex=True)
    loc18["latitude"] = pd.to_numeric(loc18["Latitude"].astype(str).str.extract(r"([-+]?\d*\.?\d+)")[0], errors="coerce")
    loc18["longitude"] = pd.to_numeric(loc18["Longitude"].astype(str).str.extract(r"([-+]?\d*\.?\d+)")[0], errors="coerce")
    loc18["source_dataset_id"] = dsid(idx)
    loc18 = loc18[["site_id", "latitude", "longitude", "source_dataset_id"]].drop_duplicates()
    loc18 = add_loc_qc(loc18)
    __locations.append(loc18)

    return DatasetResult(__dataset_id, __harmonized, __locations)
