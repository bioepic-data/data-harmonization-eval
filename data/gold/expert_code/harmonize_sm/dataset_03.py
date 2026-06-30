"""Expert harmonization for dataset index 3.

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
    """Harmonize dataset 3, returning its DatasetResult."""
    map_json = ctx.map_json
    REF_IDX = ctx.ref_idx
    dsid = ctx.dsid
    read_ds_csv = ctx.read_ds_csv
    __locations = []

    # =============================================================
    # Dataset 3
    # =============================================================
    idx = 3
    f3 = as_list(map_json[idx]["data_payload_files"])[0]
    m3 = as_list(map_json[idx]["location_metadata_files"])[0]

    df3 = read_ds_csv(idx, f3)
    mdf3 = read_ds_csv(idx, m3)

    x = df3.copy()
    x["datetime_UTC"] = parse_local_to_utc(x["TIMESTAMP"], "%Y-%m-%d %H:%M", "America/Denver")
    x["interval_min"] = interval_min(x["datetime_UTC"])

    mp_cols = [c for c in x.columns if "_MP" in c]
    for c in mp_cols:
        x[c] = pd.to_numeric(x[c], errors="coerce")

    long = x.melt(id_vars=["datetime_UTC", "interval_min"], value_vars=mp_cols, var_name="name", value_name="water_potential_kPa")
    long["depth_m"] = pd.to_numeric(
        long["name"].str.replace(r"[._]", " ", regex=True).str.split().str[1].str.replace("cm", "", regex=False),
        errors="coerce",
    ) / 100
    long["site_id"] = "ER-LLN1"
    long["is_timeseries"] = True
    long["water_potential_kPa"] = long["water_potential_kPa"].where(~np.isnan(long["water_potential_kPa"]), np.nan)
    long["volumetric_water_content_m3_m3"] = np.nan
    long["gravimetric_water_content_gH2O_gs"] = np.nan
    long["replicate"] = long.groupby(["datetime_UTC", "depth_m"]).cumcount() + 1

    df3_harmonized = ensure_harmonized_cols(long)
    __harmonized = df3_harmonized
    __dataset_id = dsid(idx)

    loc3 = mdf3.rename(columns={"Location_ID": "site_id", "Latitude": "latitude", "Longitude": "longitude"})[
        ["site_id", "latitude", "longitude"]
    ].copy()
    loc3["source_dataset_id"] = dsid(idx)
    loc3 = add_loc_qc(loc3)
    __locations.append(loc3)

    return DatasetResult(__dataset_id, __harmonized, __locations)
