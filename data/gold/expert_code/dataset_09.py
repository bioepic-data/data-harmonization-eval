"""
Dataset 9 harmonization.

Dataset: ess-dive-460e696d8210ed3-20260309T155937802
DOI: doi:10.15485/3013006
"""

import numpy as np
import pandas as pd

from common import (
    DatasetResult,
    as_list,
    parse_local_to_utc,
    utm32613_to_latlon,
    ensure_harmonized_cols,
    add_loc_qc,
)


def harmonize(ctx):
    """Harmonize dataset 9."""
    idx = 9
    __locations = []

    f9 = as_list(ctx.map_json[idx]["data_payload_files"])[0]
    m9 = as_list(ctx.map_json[idx]["location_metadata_files"])[0]

    ddf9 = ctx.read_ds_csv(idx, f9)
    mdf9 = ctx.read_ds_csv(idx, m9)

    x = ddf9.copy()
    x["datetime_UTC"] = parse_local_to_utc(x["Collection Date"], "%Y-%m-%d", "America/Denver")
    x["site_id"] = x["SampleSiteCode"]
    x["depth_m"] = 0.2
    x["is_timeseries"] = False
    x["water_potential_kPa"] = np.nan

    long = x.melt(
        id_vars=["datetime_UTC", "site_id", "depth_m", "is_timeseries", "water_potential_kPa"],
        value_vars=["VWC_1", "VWC_2"],
        var_name="tmp",
        value_name="VWC",
    )
    long["replicate"] = long["tmp"].str.extract(r"_(\d+)")[0]
    long["VWC"] = pd.to_numeric(long["VWC"], errors="coerce")
    long.loc[long["VWC"] == -9999.0, "VWC"] = np.nan
    long = long[long["VWC"].notna()].copy()
    long["volumetric_water_content_m3_m3"] = long["VWC"] / 100
    long["volumetric_water_content_m3_m3"] = long["volumetric_water_content_m3_m3"].round(3)
    long["gravimetric_water_content_gH2O_gs"] = np.nan

    __harmonized = ensure_harmonized_cols(long)

    loc9_tmp = utm32613_to_latlon(mdf9, "Easting", "Northing")
    loc9 = pd.DataFrame(
        {
            "site_id": loc9_tmp["SampleSiteCode"],
            "latitude": loc9_tmp["latitude"],
            "longitude": loc9_tmp["longitude"],
        }
    )
    loc9["source_dataset_id"] = ctx.dsid(idx)
    loc9 = add_loc_qc(loc9)
    __locations.append(loc9)

    return DatasetResult(
        dataset_id=ctx.dsid(idx),
        harmonized_data=__harmonized,
        location_data=pd.concat(__locations, ignore_index=True) if __locations else pd.DataFrame()
    )
