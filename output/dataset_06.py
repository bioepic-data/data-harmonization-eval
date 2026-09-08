"""
Dataset 6 harmonization.

Dataset: ess-dive-18e91eb74405882-20241017T173226640
DOI: unavailable (no cached ESS-DIVE metadata supplied in workspace)

Wide-format meteorological + soil sensor time series (Snodgrass_ESS.csv).
Contains volumetric water content at three depths (5, 15, 50 cm) for four
sites, with coordinates embedded in the payload file.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from common import (
    DatasetResult,
    as_list,
    ensure_harmonized_cols,
    add_loc_qc,
)


def harmonize(ctx):
    """Harmonize dataset 6."""
    idx = 6
    __locations = []

    f6 = as_list(ctx.map_json[idx]["data_payload_files"])[0]

    # The file carries two extra descriptive header rows (long name + units)
    # beneath the machine-readable column header, so skip them.
    ddf6 = ctx.read_ds_csv(idx, f6, skiprows=[1, 2], low_memory=False)

    x = ddf6.copy()

    # TIMESTAMP is already reported in UTC ("date_time UTC"), format mm-dd-yyyy hh:mm:ss.
    x["datetime_UTC"] = pd.to_datetime(
        x["TIMESTAMP"], format="%m/%d/%y %H:%M", errors="coerce"
    ).dt.tz_localize("UTC")

    vwc_cols = [c for c in x.columns if re.match(r"^VWC_\d+\.?\d*cm$", c)]

    long = x.melt(
        id_vars=["datetime_UTC", "site"],
        value_vars=vwc_cols,
        var_name="source_variable",
        value_name="volumetric_water_content_m3_m3",
    )

    long["depth_m"] = (
        pd.to_numeric(long["source_variable"].str.extract(r"(\d+\.?\d*)")[0], errors="coerce")
        / 100.0
    )
    long["volumetric_water_content_m3_m3"] = pd.to_numeric(
        long["volumetric_water_content_m3_m3"], errors="coerce"
    )

    long["site_id"] = long["site"]
    long["replicate"] = 1
    long["is_timeseries"] = True
    long["water_potential_kPa"] = np.nan
    long["gravimetric_water_content_gH2O_gs"] = np.nan

    __harmonized = ensure_harmonized_cols(long)

    # Coordinates are embedded in the payload file (one lat/lon per site).
    loc6 = (
        ddf6[["site", "latitude", "longitude"]]
        .drop_duplicates(subset=["site"])
        .rename(columns={"site": "site_id"})
        .copy()
    )
    loc6["latitude"] = pd.to_numeric(loc6["latitude"], errors="coerce")
    loc6["longitude"] = pd.to_numeric(loc6["longitude"], errors="coerce")
    loc6["source_dataset_id"] = ctx.dsid(idx)
    loc6 = add_loc_qc(loc6)
    __locations.append(loc6)

    return DatasetResult(
        dataset_id=ctx.dsid(idx),
        harmonized_data=__harmonized,
        location_data=pd.concat(__locations, ignore_index=True) if __locations else pd.DataFrame(),
    )
