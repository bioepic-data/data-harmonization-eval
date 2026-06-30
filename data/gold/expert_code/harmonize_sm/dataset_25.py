"""Expert harmonization for dataset index 25.

Auto-split from the expert monolith; the body below is verbatim except that
the shared-accumulator writes are captured into the returned DatasetResult.
"""
from __future__ import annotations

import re
import numpy as np
import pandas as pd

from common import (
    DatasetResult,
    parse_local_to_utc,
    interval_min,
    ensure_harmonized_cols,
    add_loc_qc,
)


def harmonize(ctx):
    """Harmonize dataset 25, returning its DatasetResult."""
    map_json = ctx.map_json
    REF_IDX = ctx.ref_idx
    dsid = ctx.dsid
    read_ds_csv = ctx.read_ds_csv
    __locations = []

    # =============================================================
    # Dataset 25
    # =============================================================
    idx = 25
    # Load and combine aspen and conifer site data
    ddf25_conifer = read_ds_csv(idx, "Carbone_conifer.csv")
    ddf25_aspen = read_ds_csv(idx, "Carbone_aspen.csv", header=None)
    ddf25_aspen.columns = ddf25_conifer.columns

    # site_id: pattern_1 - Assign based on file name (aspen vs conifer)
    ddf25 = pd.concat(
        [
            ddf25_aspen.assign(site_id="aspen"),
            ddf25_conifer.assign(site_id="conifer"),
        ],
        ignore_index=True,
    )

    x = ddf25.copy()

    # datetime: pattern_1 - Construct from 'Year', 'Month', 'Day', 'Hour' columns and convert to ISO 8601 UTC format
    x["datetime_UTC"] = parse_local_to_utc(
        x["Year"].astype(str) + "-" + x["Month"].astype(str) + "-" + x["Day"].astype(str) + "-" + x["Hour"].astype(str),
        "%Y-%m-%d-%H",
        "America/Denver",
    )
    x = x.sort_values(["site_id", "datetime_UTC"])
    x["interval_min"] = x.groupby("site_id")["datetime_UTC"].diff().dt.total_seconds() / 60.0

    # volumetric_water_content: pattern_1
    # Coerce from 'wide' format to 'long' format
    vwc_cols = [c for c in x.columns if re.search(r"vwc", c, flags=re.IGNORECASE)]
    long = x.melt(
        id_vars=["datetime_UTC", "site_id", "interval_min"],
        value_vars=vwc_cols,
        var_name="name",
        value_name="volumetric_water_content_m3_m3",
    )

    # depth: pattern_1 - Parse depth (cm) from column name and divide by 1e2 to convert to m
    long["depth_m"] = pd.to_numeric(long["name"].str.extract(r"(\d+)")[0], errors="coerce") / 100

    # replicate: pattern_1 - Replicate information not provided in source; populate with 1
    long["replicate"] = 1
    long["is_timeseries"] = True

    # soil_water_potential: pattern_1 - Not reported in source; populate with NA
    long["water_potential_kPa"] = np.nan
    long["gravimetric_water_content_gH2O_gs"] = np.nan
    long["volumetric_water_content_m3_m3"] = pd.to_numeric(long["volumetric_water_content_m3_m3"], errors="coerce")
    long = long[long["volumetric_water_content_m3_m3"].notna()]

    df25_harmonized = ensure_harmonized_cols(long)
    __harmonized = df25_harmonized
    __dataset_id = dsid(idx)

    # latitude: pattern_1 & longitude: pattern_1
    # Geospatial information not provided in data files; look up in ESS-DIVE package metadata
    loc25 = pd.DataFrame(
        {
            "site_id": ["aspen", "conifer"],
            "latitude": [38.9581589, 38.9581589],
            "longitude": [-106.9855848, -106.9855848],
        }
    ).drop_duplicates()
    loc25["source_dataset_id"] = dsid(idx)
    loc25 = add_loc_qc(loc25)
    __locations.append(loc25)

    return DatasetResult(__dataset_id, __harmonized, __locations)
