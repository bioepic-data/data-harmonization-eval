"""Expert harmonization for dataset index 16.

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
    """Harmonize dataset 16, returning its DatasetResult."""
    map_json = ctx.map_json
    REF_IDX = ctx.ref_idx
    dsid = ctx.dsid
    read_ds_csv = ctx.read_ds_csv
    __locations = []

    # =============================================================
    # Dataset 16
    # =============================================================
    idx = 16
    f16 = as_list(map_json[idx]["data_payload_files"])
    m16 = as_list(map_json[idx]["location_metadata_files"])[0]
    s16 = as_list(map_json[idx]["sensor_metadata_files"])[0]

    ls16 = [read_ds_csv(idx, x) for x in f16]
    mdf16 = read_ds_csv(idx, m16)
    sdf16 = read_ds_csv(idx, s16)

    ls16_h = []
    for i, d in enumerate(ls16):
        siten = f16[i]
        x = d.copy()

        # datetime: pattern_1 - Convert 'TIMESTAMP_END' to ISO 8601 UTC format
        x["datetime_UTC"] = parse_local_to_utc(x["TIMESTAMP_END"], "%Y-%m-%d %H:%M:%S", "Etc/GMT+7")
        x["interval_min"] = interval_min(x["datetime_UTC"])

        # site_id: pattern_1 - Parse site_id from source filename
        parts = siten.split("_")
        x["SITE_ID"] = parts[6] if len(parts) >= 7 else np.nan

        # volumetric_water_content: pattern_1 & soil_water_potential: pattern_1
        # Coerce from 'wide' format to 'long' format
        sw_cols = [c for c in x.columns if re.search(r"SWC|SWP", c)]
        long = x.melt(id_vars=["datetime_UTC", "interval_min", "SITE_ID"], value_vars=sw_cols, var_name="VARIABLE", value_name="value")

        # depth: pattern_1 - Look up 'HEIGHT' from sensor metadata and convert to depth (multiply by -1)
        meta = sdf16.loc[sdf16["VARIABLE"].astype(str).str.contains("SWC|SWP", regex=True, na=False), ["SITE_ID", "VARIABLE", "HEIGHT"]]
        long = long.merge(meta, on=["SITE_ID", "VARIABLE"], how="left")
        long["VARIABLE"] = long["VARIABLE"].astype(str).str.split("_").str[0]
        long["depth_m"] = pd.to_numeric(long["HEIGHT"], errors="coerce") * -1

        # replicate: pattern_1 - Replicate information not provided in source; populate with 1
        long["replicate"] = 1
        long["is_timeseries"] = True
        long["gravimetric_water_content_gH2O_gs"] = np.nan
        long = long.drop_duplicates()

        wide = (
            long.pivot_table(
                index=["datetime_UTC", "SITE_ID", "depth_m", "replicate", "is_timeseries", "interval_min", "gravimetric_water_content_gH2O_gs"],
                columns="VARIABLE",
                values="value",
                aggfunc="first",
            )
            .reset_index()
        )

        # Clean sentinel values and rename variables
        wide["SWC"] = pd.to_numeric(wide.get("SWC"), errors="coerce")
        wide["SWP"] = pd.to_numeric(wide.get("SWP"), errors="coerce")
        wide["volumetric_water_content_m3_m3"] = np.where(wide["SWC"].isin([9999.0, -9999.0]), np.nan, wide["SWC"])
        wide["water_potential_kPa"] = np.where(wide["SWP"].isin([9999.0, -9999.0]), np.nan, wide["SWP"])
        wide = wide.rename(columns={"SITE_ID": "site_id"})

        ls16_h.append(ensure_harmonized_cols(wide))

    df16_harmonized = pd.concat(ls16_h, ignore_index=True)
    __harmonized = df16_harmonized
    __dataset_id = dsid(idx)

    # latitude: pattern_1 & longitude: pattern_1
    # Look up 'LOCATION_LAT' and 'LOCATION_LONG' for 'SITE_ID' in location metadata
    loc16 = mdf16.rename(columns={"SITE_ID": "site_id", "LOCATION_LAT": "latitude", "LOCATION_LONG": "longitude"})[
        ["site_id", "latitude", "longitude"]
    ].copy()
    loc16["source_dataset_id"] = dsid(idx)
    loc16 = add_loc_qc(loc16)
    __locations.append(loc16)

    return DatasetResult(__dataset_id, __harmonized, __locations)
