"""
Dataset 7 harmonization.

Dataset: ess-dive-38e901ec3d7bd24-20230504T211548257225
DOI: doi:10.15485/1660455
"""

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
    """Harmonize dataset 7."""
    idx = 7
    __locations = []

    f7 = as_list(ctx.map_json[idx]["data_payload_files"])[0]
    m7 = as_list(ctx.map_json[idx]["location_metadata_files"])[0]

    ddf7 = ctx.read_ds_csv(idx, f7)
    mdf7 = ctx.read_ds_csv(idx, m7, encoding='latin-1')

    x = ddf7.copy()
    x["datetime_UTC"] = parse_local_to_utc(x["date.time"], "%m/%d/%y %H:%M", "Etc/GMT+7")
    x["site_id"] = "BM"
    x["depth_m"] = pd.to_numeric(x["Depth (cm)"], errors="coerce") / 100
    x["replicate"] = int(1)
    x["is_timeseries"] = True
    x["volumetric_water_content_m3_m3"] = pd.to_numeric(x["Volumetric Water Content"], errors="coerce")
    x["water_potential_kPa"] = np.nan
    x["gravimetric_water_content_gH2O_gs"] = np.nan

    __harmonized = ensure_harmonized_cols(x)

    lat_col = [c for c in mdf7.columns if "Latitude" in c][0]
    lon_col = [c for c in mdf7.columns if "Longitude" in c][0]
    loc7 = mdf7.iloc[[0]].rename(columns={"Location": "site_id", lat_col: "latitude", lon_col: "longitude"})[
        ["site_id", "latitude", "longitude"]
    ].copy()
    loc7["source_dataset_id"] = ctx.dsid(idx)
    loc7 = add_loc_qc(loc7)
    __locations.append(loc7)

    return DatasetResult(
        dataset_id=ctx.dsid(idx),
        harmonized_data=__harmonized,
        location_data=pd.concat(__locations, ignore_index=True) if __locations else pd.DataFrame()
    )
