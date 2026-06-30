"""Expert harmonization for dataset index 10.

Auto-split from the expert monolith; the body below is verbatim except that
the shared-accumulator writes are captured into the returned DatasetResult.
"""
from __future__ import annotations

import re
import numpy as np

from common import (
    DatasetResult,
    as_list,
    parse_local_to_utc,
    interval_min,
    ensure_harmonized_cols,
    add_loc_qc,
)


def harmonize(ctx):
    """Harmonize dataset 10, returning its DatasetResult."""
    map_json = ctx.map_json
    REF_IDX = ctx.ref_idx
    dsid = ctx.dsid
    read_ds_csv = ctx.read_ds_csv
    __locations = []

    # =============================================================
    # Dataset 10
    # =============================================================
    idx = 10
    f10 = as_list(map_json[idx]["data_payload_files"])[0]
    m10 = as_list(map_json[REF_IDX]["location_metadata_files"])[0]

    ddf10 = read_ds_csv(idx, f10)
    mdf10 = read_ds_csv(REF_IDX, m10)

    x = ddf10.iloc[1:].copy()

    # datetime: pattern_1 - Convert 'Date' to ISO 8601 UTC format
    x["datetime_UTC"] = parse_local_to_utc(x["Date"], "%Y-%m-%d", "America/Denver")
    x["interval_min"] = interval_min(x["datetime_UTC"])

    # volumetric_water_content: pattern_1
    # Coerce from 'wide' format with column variables containing site information to 'long' format
    vcols = [c for c in x.columns if re.search(r"vol_water_content", c)]
    long = x.melt(id_vars=["datetime_UTC", "interval_min"], value_vars=vcols, var_name="name", value_name="volumetric_water_content_m3_m3")

    # site_id: pattern_1 - Parse site_id from 'PLMi' in volumetric water content column name
    nm = long["name"].str.extract(r"(.*)\._(.*)")
    long["site_id"] = nm[0]

    # depth: pattern_1 - Populate with depths reported in legend labels for Fig. 4 in associated manuscript
    long["depth_m"] = np.select(
        [long["site_id"].eq("PLM1"), long["site_id"].eq("PLM2"), long["site_id"].eq("PLM3")],
        [0.3, 0.28, 0.2],
        default=np.nan,
    )
    long["is_timeseries"] = True

    # soil_water_potential: pattern_1 - Not reported in source; populate with NA
    long["water_potential_kPa"] = np.nan

    # replicate: pattern_1 - Replicate information not provided in source; populate with 1
    long["replicate"] = 1
    long["gravimetric_water_content_gH2O_gs"] = np.nan

    df10_harmonized = ensure_harmonized_cols(long)
    __harmonized = df10_harmonized
    __dataset_id = dsid(idx)

    # latitude: pattern_1 & longitude: pattern_1
    # Location information not reported in package; look up 'Latitude' and 'Longitude' for 'site_id' in Varadharajan et al.
    sites = df10_harmonized["site_id"].dropna().astype(str).unique().tolist()
    pattern = r"(?:^|)(%s)$" % "|".join([re.escape(s) for s in sites]) if sites else r"$^"
    loc10 = mdf10[mdf10["Location_ID"].astype(str).str.contains(pattern, regex=True, na=False)].copy()
    loc10["site_id"] = loc10["Location_ID"].str.replace("ER-", "", regex=False)
    loc10 = loc10.rename(columns={"Latitude": "latitude", "Longitude": "longitude"})[["site_id", "latitude", "longitude"]]
    loc10["source_dataset_id"] = dsid(idx)
    loc10 = add_loc_qc(loc10)
    __locations.append(loc10)

    return DatasetResult(__dataset_id, __harmonized, __locations)
