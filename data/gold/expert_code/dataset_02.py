"""
Dataset 2 harmonization.

Dataset: ess-dive-9fd65df885a8e87-20250715T064942543
DOI: doi:10.15485/1646477
"""

import re
import numpy as np
import pandas as pd

from common import (
    DatasetResult,
    as_list,
    parse_local_to_utc,
    ensure_harmonized_cols,
    add_loc_qc,
)


def harmonize(ctx):
    """Harmonize dataset 2."""
    idx = 2
    __locations = []

    f2 = as_list(ctx.map_json[idx]["data_payload_files"])
    m2 = as_list(ctx.map_json[idx]["location_metadata_files"])[0]

    ls2 = [ctx.read_ds_csv(idx, x) for x in f2]
    mdf2 = ctx.read_ds_csv(idx, m2)

    ls2_h = []
    for i, d in enumerate(ls2):
        cols = [c for c in d.columns if re.search(r"Moisture", c)]
        x = d[["DateTime"] + cols].copy()
        x["datetime_UTC"] = parse_local_to_utc(x["DateTime"], "%m/%d/%Y %I:%M:%S %p", "Etc/GMT+7")
        x = x.drop(columns=["DateTime"])

        long = x.melt(
            id_vars=["datetime_UTC"],
            var_name="name",
            value_name="volumetric_water_content_m3_m3",
        )
        long["depth_m"] = (
            pd.to_numeric(long["name"].str.split("_").str[-1].str.replace("cm", "", regex=False), errors="coerce") / 100
        )
        long["site_id"] = re.sub(r"\.csv$", "", f2[i])
        long["site_id"] = long["site_id"].str.replace("_", "-")
        long["is_timeseries"] = True
        long.loc[long["volumetric_water_content_m3_m3"] == -9999.0, "volumetric_water_content_m3_m3"] = np.nan
        long["water_potential_kPa"] = np.nan
        long["gravimetric_water_content_gH2O_gs"] = np.nan
        long["replicate"] = long.groupby(["datetime_UTC", "depth_m", "name"]).cumcount().astype(int) + 1

        ls2_h.append(ensure_harmonized_cols(long))

    __harmonized = pd.concat(ls2_h, ignore_index=True)

    loc2 = mdf2.rename(columns={"Name": "site_id", "Lat ": "latitude", "Lon": "longitude"})[
        ["site_id", "latitude", "longitude"]
    ].copy()
    loc2["source_dataset_id"] = ctx.dsid(idx)
    loc2 = add_loc_qc(loc2)
    __locations.append(loc2)

    return DatasetResult(
        dataset_id=ctx.dsid(idx),
        harmonized_data=__harmonized,
        location_data=pd.concat(__locations, ignore_index=True) if __locations else pd.DataFrame()
    )
