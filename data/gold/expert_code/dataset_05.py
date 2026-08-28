"""
Dataset 5 harmonization.

Dataset: ess-dive-8ac2940c708a515-20230504T210140482233
DOI: doi:10.15485/1842907
"""

import numpy as np
import pandas as pd

from common import (
    DatasetResult,
    as_list,
    ensure_harmonized_cols,
)


def harmonize(ctx):
    """Harmonize dataset 5."""
    idx = 5
    __locations = []

    f5 = as_list(ctx.map_json[idx]["data_payload_files"])[0]
    m5 = as_list(ctx.map_json[ctx.ref_idx]["location_metadata_files"])[0]

    ddf5 = ctx.read_ds_csv(idx, f5)
    mdf5 = ctx.read_ds_csv(ctx.ref_idx, m5)

    x = ddf5.copy()
    dt_local = pd.to_datetime(x["Date Time"], errors="coerce").dt.tz_localize("Etc/GMT+7", ambiguous="NaT", nonexistent="shift_forward")
    x["datetime_UTC"] = dt_local.dt.tz_convert("UTC")
    x["site_id"] = x["SFA_Location"]
    x["depth_m"] = np.nan
    x["replicate"] = int(1)
    x["is_timeseries"] = True
    x["volumetric_water_content_m3_m3"] = pd.to_numeric(x["Measurement"], errors="coerce")
    x["water_potential_kPa"] = np.nan
    x["gravimetric_water_content_gH2O_gs"] = np.nan

    __harmonized = ensure_harmonized_cols(x)

    loc5 = pd.DataFrame({"site_id": __harmonized["site_id"].dropna().unique()})

    loc5a = loc5.merge(
        mdf5[["Location_ID", "Latitude", "Longitude"]],
        left_on="site_id",
        right_on="Location_ID",
        how="left",
    ).drop(columns=["Location_ID"])

    loc5b = loc5.merge(
        mdf5[["Parent_Location_ID", "Latitude", "Longitude"]],
        left_on="site_id",
        right_on="Parent_Location_ID",
        how="left",
    ).drop(columns=["Parent_Location_ID"])

    loc5m = loc5a.merge(loc5b, on="site_id", how="left", suffixes=(".x", ".y"))
    loc5m["latitude"] = loc5m["Latitude.x"].combine_first(loc5m["Latitude.y"])
    loc5m["longitude"] = loc5m["Longitude.x"].combine_first(loc5m["Longitude.y"])
    loc5m["source_dataset_id"] = ctx.dsid(idx)

    loc5 = loc5m[["site_id", "latitude", "longitude", "source_dataset_id"]].drop_duplicates(subset=["site_id"])
    loc5["qc_flag"] = np.where(loc5["latitude"].isna() | loc5["longitude"].isna(), "g2", "g1")
    __locations.append(loc5)

    return DatasetResult(
        dataset_id=ctx.dsid(idx),
        harmonized_data=__harmonized,
        location_data=pd.concat(__locations, ignore_index=True) if __locations else pd.DataFrame()
    )
