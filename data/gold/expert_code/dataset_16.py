"""
Dataset 16 harmonization.

Dataset: ess-dive-b3d271f19a94e8d-20260114T204512119
DOI: doi:10.15485/3007697
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
    """Harmonize dataset 16."""
    idx = 16
    __locations = []

    f16 = as_list(ctx.map_json[idx]["data_payload_files"])
    m16 = as_list(ctx.map_json[idx]["location_metadata_files"])[0]
    s16 = as_list(ctx.map_json[idx]["sensor_metadata_files"])[0]

    ls16 = [ctx.read_ds_csv(idx, x) for x in f16]
    mdf16 = ctx.read_ds_csv(idx, m16)
    sdf16 = ctx.read_ds_csv(idx, s16)

    ls16_h = []
    for i, d in enumerate(ls16):
        siten = f16[i]
        x = d.copy()
        x["datetime_UTC"] = parse_local_to_utc(x["TIMESTAMP_END"], "%Y-%m-%d %H:%M:%S", "Etc/GMT+7")
        parts = siten.split("_")
        x["SITE_ID"] = parts[6] if len(parts) >= 7 else np.nan

        sw_cols = [c for c in x.columns if re.search(r"SWC|SWP", c)]
        long = x.melt(id_vars=["datetime_UTC", "SITE_ID"], value_vars=sw_cols, var_name="VARIABLE", value_name="value")

        meta = sdf16.loc[sdf16["VARIABLE"].astype(str).str.contains("SWC|SWP", regex=True, na=False), ["SITE_ID", "VARIABLE", "HEIGHT"]]
        long = long.merge(meta, on=["SITE_ID", "VARIABLE"], how="left")
        long["VARIABLE"] = long["VARIABLE"].astype(str).str.split("_").str[0]
        long["depth_m"] = pd.to_numeric(long["HEIGHT"], errors="coerce") * -1
        long["replicate"] = 1
        long["is_timeseries"] = True
        long["gravimetric_water_content_gH2O_gs"] = np.nan
        long = long.drop_duplicates()

        wide = (
            long.pivot_table(
                index=["datetime_UTC", "SITE_ID", "depth_m", "replicate", "is_timeseries"],
                columns="VARIABLE",
                values="value",
                aggfunc="first",
            )
            .reset_index()
        )

        wide["SWC"] = pd.to_numeric(wide.get("SWC"), errors="coerce")
        wide["SWP"] = pd.to_numeric(wide.get("SWP"), errors="coerce")
        wide["volumetric_water_content_m3_m3"] = np.where(wide["SWC"].isin([9999.0, -9999.0]), np.nan, wide["SWC"] / 100)
        wide["water_potential_kPa"] = np.where(wide["SWP"].isin([9999.0, -9999.0]), np.nan, wide["SWP"])
        wide = wide.rename(columns={"SITE_ID": "site_id"})

        ls16_h.append(ensure_harmonized_cols(wide))

    __harmonized = pd.concat(ls16_h, ignore_index=True)

    loc16 = mdf16.rename(columns={"SITE_ID": "site_id", "LOCATION_LAT": "latitude", "LOCATION_LONG": "longitude"})[
        ["site_id", "latitude", "longitude"]
    ].copy()
    loc16["source_dataset_id"] = ctx.dsid(idx)
    loc16 = add_loc_qc(loc16)
    __locations.append(loc16)

    return DatasetResult(
        dataset_id=ctx.dsid(idx),
        harmonized_data=__harmonized,
        location_data=pd.concat(__locations, ignore_index=True) if __locations else pd.DataFrame()
    )
