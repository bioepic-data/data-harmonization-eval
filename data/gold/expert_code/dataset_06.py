"""
Dataset 6 harmonization.

Dataset: ess-dive-18e91eb74405882-20241017T173226640
DOI: doi:10.15485/1909712
"""

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
    ddf6 = ctx.read_ds_csv(idx, f6)

    x = ddf6.iloc[2:].copy()
    x["datetime_UTC"] = pd.to_datetime(x["TIMESTAMP"], format="%m/%d/%y %H:%M", errors="coerce", utc=False)
    x["datetime_UTC"] = x["datetime_UTC"].dt.tz_localize("Etc/GMT+7", ambiguous="NaT", nonexistent="shift_forward").dt.tz_convert("UTC")
    x["site_id"] = x["site"]

    vwc_cols = [c for c in x.columns if "VWC" in c]
    long = x.melt(
        id_vars=["datetime_UTC", "site_id"],
        value_vars=vwc_cols,
        var_name="name",
        value_name="volumetric_water_content_m3_m3",
    )
    long["depth_m"] = (
        pd.to_numeric(long["name"].str.split("_").str[-1].str.replace("cm", "", regex=False), errors="coerce") / 100
    )
    long["replicate"] = 1
    long["is_timeseries"] = True
    long["water_potential_kPa"] = np.nan
    long["gravimetric_water_content_gH2O_gs"] = np.nan

    __harmonized = ensure_harmonized_cols(long)

    loc6 = (
        ddf6.iloc[2:]
        .groupby("site", as_index=False)
        .first()[["site", "latitude", "longitude"]]
        .rename(columns={"site": "site_id"})
    )
    loc6["source_dataset_id"] = ctx.dsid(idx)
    loc6 = add_loc_qc(loc6)
    __locations.append(loc6)

    return DatasetResult(
        dataset_id=ctx.dsid(idx),
        harmonized_data=__harmonized,
        location_data=pd.concat(__locations, ignore_index=True) if __locations else pd.DataFrame()
    )
