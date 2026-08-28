"""
Dataset 15 harmonization.

Dataset: ess-dive-987726ef1235abc-20230504T210342929747
DOI: doi:10.15485/1648526
"""

import re
import numpy as np
import pandas as pd

from common import (
    DatasetResult,
    as_list,
    utm32613_to_latlon,
    ensure_harmonized_cols,
    add_loc_qc,
)


def harmonize(ctx):
    """Harmonize dataset 15."""
    idx = 15
    __locations = []

    f15 = as_list(ctx.map_json[idx]["data_payload_files"])[0]
    m15 = as_list(ctx.map_json[idx]["location_metadata_files"])[0]

    ddf15 = ctx.read_ds_csv(idx, f15)
    mdf15 = ctx.read_ds_csv(idx, m15)

    x = ddf15.iloc[1:].copy()
    x["datetime_UTC"] = pd.Timestamp("2019-07-02 06:00:00", tz="UTC")
    x["is_timeseries"] = False

    vcols = [c for c in x.columns if re.search(r"SM\(VWC", c)]
    long = x.melt(
        id_vars=["datetime_UTC", "GPS_id", "is_timeseries"],
        value_vars=vcols,
        var_name="name",
        value_name="volumetric_water_content_m3_m3",
    )
    long["replicate"] = long["name"].str.extract(r"\)_(.*)$")[0]
    long["volumetric_water_content_m3_m3"] = pd.to_numeric(long["volumetric_water_content_m3_m3"], errors="coerce") / 100
    long["depth_m"] = 0.25
    long["water_potential_kPa"] = np.nan
    long["gravimetric_water_content_gH2O_gs"] = np.nan
    long["site_id"] = long["GPS_id"]

    __harmonized = ensure_harmonized_cols(long)

    loc15_tmp = utm32613_to_latlon(mdf15, "Easting_m", "Northing_m")
    loc15 = pd.DataFrame(
        {
            "site_id": loc15_tmp["GPS_id"],
            "latitude": loc15_tmp["latitude"],
            "longitude": loc15_tmp["longitude"],
        }
    )
    loc15["source_dataset_id"] = ctx.dsid(idx)
    loc15 = add_loc_qc(loc15)
    __locations.append(loc15)

    return DatasetResult(
        dataset_id=ctx.dsid(idx),
        harmonized_data=__harmonized,
        location_data=pd.concat(__locations, ignore_index=True) if __locations else pd.DataFrame()
    )
