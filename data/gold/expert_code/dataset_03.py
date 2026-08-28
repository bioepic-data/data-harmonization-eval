"""
Dataset 3 harmonization.

Dataset: ess-dive-4c1829de1b8a2ec-20260220T045039633
DOI: doi:10.15485/2998779
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
    """Harmonize dataset 3."""
    idx = 3
    __locations = []

    f3 = as_list(ctx.map_json[idx]["data_payload_files"])[0]
    m3 = as_list(ctx.map_json[idx]["location_metadata_files"])[0]

    df3 = ctx.read_ds_csv(idx, f3)
    mdf3 = ctx.read_ds_csv(idx, m3)

    x = df3.copy()
    x["datetime_UTC"] = parse_local_to_utc(x["TIMESTAMP"], "%Y-%m-%d %H:%M", "Etc/GMT+7")

    mp_cols = [c for c in x.columns if "_MP" in c]
    for c in mp_cols:
        x[c] = pd.to_numeric(x[c], errors="coerce")

    long = x.melt(id_vars=["datetime_UTC"], value_vars=mp_cols, var_name="name", value_name="water_potential_kPa")
    long["depth_m"] = pd.to_numeric(
        long["name"].str.split(r"[.|_|-]").str[1].str.replace("cm", "", regex=False),
        errors="coerce",
    ) / 100
    long.drop(columns=["name"], inplace=True)
    long["site_id"] = "ER-LLN1"
    long["is_timeseries"] = True
    long["water_potential_kPa"] = long["water_potential_kPa"].where(~np.isnan(long["water_potential_kPa"]), np.nan)
    long["volumetric_water_content_m3_m3"] = np.nan
    long["gravimetric_water_content_gH2O_gs"] = np.nan
    long["replicate"] = long.groupby(["site_id", "depth_m", "datetime_UTC"]).cumcount().astype(int) + 1
    long = long.sort_values(["datetime_UTC", "site_id", "depth_m", "replicate"])

    __harmonized = ensure_harmonized_cols(long)

    loc3 = mdf3.rename(columns={"Location_ID": "site_id", "Latitude": "latitude", "Longitude": "longitude"})[
        ["site_id", "latitude", "longitude"]
    ].copy()
    loc3["source_dataset_id"] = ctx.dsid(idx)
    loc3 = add_loc_qc(loc3)
    __locations.append(loc3)

    return DatasetResult(
        dataset_id=ctx.dsid(idx),
        harmonized_data=__harmonized,
        location_data=pd.concat(__locations, ignore_index=True) if __locations else pd.DataFrame()
    )
