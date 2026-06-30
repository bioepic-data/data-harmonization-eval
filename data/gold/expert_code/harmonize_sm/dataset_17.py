"""Expert harmonization for dataset index 17.

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
    utm32613_to_latlon,
    ensure_harmonized_cols,
    add_loc_qc,
)


def harmonize(ctx):
    """Harmonize dataset 17, returning its DatasetResult."""
    map_json = ctx.map_json
    REF_IDX = ctx.ref_idx
    dsid = ctx.dsid
    read_ds_csv = ctx.read_ds_csv
    __locations = []

    # =============================================================
    # Dataset 17
    # =============================================================
    idx = 17
    f17 = as_list(map_json[idx]["data_payload_files"])
    m17 = as_list(map_json[idx]["location_metadata_files"])[0]

    ls17 = [read_ds_csv(idx, x) for x in f17]
    mdf17 = read_ds_csv(idx, m17)

    ls17_h = []
    for i, d in enumerate(ls17):
        siten = f17[i]
        x = d.iloc[1:].copy()

        # datetime: pattern_1 - Convert 'DateTime' to ISO 8601 UTC format
        x["datetime_UTC"] = parse_local_to_utc(x["DateTime"], "%Y-%m-%d %H:%M:%S", "America/Denver")
        x["interval_min"] = interval_min(x["datetime_UTC"])

        # site_id: pattern_1 - Parse site_id from source filename
        site_guess = re.split(r"/|\.", siten)
        x["site_id"] = site_guess[2] if len(site_guess) > 2 else np.nan

        # volumetric_water_content: pattern_1
        # Coerce from 'wide' format to 'long' format
        mc_cols = [c for c in x.columns if re.search(r"MC", c)]
        long = x.melt(id_vars=["datetime_UTC", "interval_min", "site_id"], value_vars=mc_cols, var_name="name", value_name="value")

        # depth: pattern_1 - Parse depth from variable name (source units are m)
        m = long["name"].str.extract(r"(.*)_(.*)")
        long["depth_m"] = pd.to_numeric(m[1].str.replace("m", "", regex=False), errors="coerce")
        long["volumetric_water_content_m3_m3"] = pd.to_numeric(long["value"], errors="coerce")

        # replicate: pattern_1 - Replicate information not provided in source; populate with 1
        long["replicate"] = 1
        long["is_timeseries"] = True

        # soil_water_potential: pattern_1 - Not reported in source; populate with NA
        long["water_potential_kPa"] = np.nan
        long["gravimetric_water_content_gH2O_gs"] = np.nan

        ls17_h.append(ensure_harmonized_cols(long))

    df17_harmonized = pd.concat(ls17_h, ignore_index=True)
    __harmonized = df17_harmonized
    __dataset_id = dsid(idx)

    # latitude: pattern_1 & longitude: pattern_1
    # Look up 'Northing' and 'Easting' for 'site_id' in location metadata
    # Reproject from EPSG:32613 (WGS84 UTM Zone 13N, meters) to EPSG:4326 (WGS84, decimal degrees)
    loc17_tmp = utm32613_to_latlon(mdf17, "Easting", "Northing")
    loc17 = pd.DataFrame(
        {
            "site_id": loc17_tmp["ID"],
            "latitude": loc17_tmp["latitude"],
            "longitude": loc17_tmp["longitude"],
        }
    )
    loc17["source_dataset_id"] = dsid(idx)
    loc17 = add_loc_qc(loc17)
    loc17 = loc17[loc17["site_id"].astype(str).str.contains("TMC", na=False)]
    __locations.append(loc17)

    return DatasetResult(__dataset_id, __harmonized, __locations)
