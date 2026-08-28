"""
Dataset 17 harmonization.

Dataset: ess-dive-be919d7d5d42c94-20240130T205332180
DOI: doi:10.15485/2283406
"""

import re
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
    """Harmonize dataset 17."""
    idx = 17
    __locations = []

    f17 = as_list(ctx.map_json[idx]["data_payload_files"])
    m17 = as_list(ctx.map_json[idx]["location_metadata_files"])[0]

    ls17 = [ctx.read_ds_csv(idx, x) for x in f17]
    mdf17 = ctx.read_ds_csv(idx, m17)

    ls17_h = []
    for i, d in enumerate(ls17):
        siten = f17[i]
        x = d.iloc[1:].copy()
        x["datetime_UTC"] = parse_local_to_utc(x["DateTime"], "%Y-%m-%d %H:%M:%S", "Etc/GMT+7")

        site_guess = re.split(r"/|\.", siten)
        x["site_id"] = site_guess[2] if len(site_guess) > 2 else np.nan

        mc_cols = [c for c in x.columns if re.search(r"MC", c)]
        long = x.melt(id_vars=["datetime_UTC", "site_id"], value_vars=mc_cols, var_name="name", value_name="value")
        m = long["name"].str.extract(r"(.*)_(.*)")
        long["depth_m"] = pd.to_numeric(m[1].str.replace("m", "", regex=False), errors="coerce")
        long["volumetric_water_content_m3_m3"] = pd.to_numeric(long["value"], errors="coerce")
        long["replicate"] = 1
        long["is_timeseries"] = True
        long["water_potential_kPa"] = np.nan
        long["gravimetric_water_content_gH2O_gs"] = np.nan

        ls17_h.append(ensure_harmonized_cols(long))

    __harmonized = pd.concat(ls17_h, ignore_index=True)

    loc17_tmp = utm32613_to_latlon(mdf17, "Easting", "Northing")
    loc17 = pd.DataFrame(
        {
            "site_id": loc17_tmp["ID"],
            "latitude": loc17_tmp["latitude"],
            "longitude": loc17_tmp["longitude"],
        }
    )
    loc17["source_dataset_id"] = ctx.dsid(idx)
    loc17 = add_loc_qc(loc17)
    loc17 = loc17[loc17["site_id"].astype(str).str.contains("TMC", na=False)]
    __locations.append(loc17)

    return DatasetResult(
        dataset_id=ctx.dsid(idx),
        harmonized_data=__harmonized,
        location_data=pd.concat(__locations, ignore_index=True) if __locations else pd.DataFrame()
    )
