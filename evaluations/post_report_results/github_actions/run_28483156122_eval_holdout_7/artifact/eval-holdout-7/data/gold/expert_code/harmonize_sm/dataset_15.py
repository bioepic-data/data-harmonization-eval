"""Expert harmonization for dataset index 15.

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
    interval_min,
    utm32613_to_latlon,
    ensure_harmonized_cols,
    add_loc_qc,
)


def harmonize(ctx):
    """Harmonize dataset 15, returning its DatasetResult."""
    map_json = ctx.map_json
    REF_IDX = ctx.ref_idx
    dsid = ctx.dsid
    read_ds_csv = ctx.read_ds_csv
    __locations = []

    # =============================================================
    # Dataset 15
    # =============================================================
    idx = 15
    f15 = as_list(map_json[idx]["data_payload_files"])[0]
    m15 = as_list(map_json[idx]["location_metadata_files"])[0]

    ddf15 = read_ds_csv(idx, f15)
    mdf15 = read_ds_csv(idx, m15)

    x = ddf15.iloc[1:].copy()

    # datetime: pattern_1 - Date information not reported in dataset; populate with first date reported in package metadata
    # under 'Temporal Coverage/Date Range' (2019-07-02) and assign time as 06:00 UTC
    x["datetime_UTC"] = pd.Timestamp("2019-07-02 06:00:00", tz="UTC")
    x["is_timeseries"] = False
    x["interval_min"] = np.nan

    # volumetric_water_content: pattern_1
    # Coerce from 'wide' format to 'long' format
    vcols = [c for c in x.columns if re.search(r"SM\.VWC", c)]
    long = x.melt(
        id_vars=["datetime_UTC", "GPS_id", "is_timeseries", "interval_min"],
        value_vars=vcols,
        var_name="name",
        value_name="volumetric_water_content_m3_m3",
    )

    # replicate: pattern_1 - Parse from variable name
    long["replicate"] = long["name"].str.extract(r"\._(.*)$")[0]
    long["volumetric_water_content_m3_m3"] = pd.to_numeric(long["volumetric_water_content_m3_m3"], errors="coerce") / 100

    # depth: pattern_1 - Populate with sampling depth reported in package metadata (25 cm -> 0.25 m)
    long["depth_m"] = 0.25

    # soil_water_potential: pattern_1 - Not reported in source; populate with NA
    long["water_potential_kPa"] = np.nan
    long["gravimetric_water_content_gH2O_gs"] = np.nan

    # site_id: pattern_1 - Use GPS_id as site_id
    long["site_id"] = long["GPS_id"]

    df15_harmonized = ensure_harmonized_cols(long)
    __harmonized = df15_harmonized
    __dataset_id = dsid(idx)

    # latitude: pattern_1 & longitude: pattern_1
    # Look up 'Northing_m' and 'Easting_m' for 'site_id' in TDR_survey_ER_20190701.csv
    # Reproject from EPSG:32613 (WGS84 UTM Zone 13N, meters) to EPSG:4326 (WGS84, decimal degrees)
    loc15_tmp = utm32613_to_latlon(mdf15, "Easting_m", "Northing_m")
    loc15 = pd.DataFrame(
        {
            "site_id": loc15_tmp["GPS_id"],
            "latitude": loc15_tmp["latitude"],
            "longitude": loc15_tmp["longitude"],
        }
    )
    loc15["source_dataset_id"] = dsid(idx)
    loc15 = add_loc_qc(loc15)
    __locations.append(loc15)

    return DatasetResult(__dataset_id, __harmonized, __locations)
