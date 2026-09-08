"""
Dataset 10 harmonization.

Dataset: ess-dive-01092fc392bc46d-20240819T143818677
DOI: doi:10.15485/2322567
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
    """Harmonize dataset 10."""
    idx = 10
    __locations = []

    f10 = as_list(ctx.map_json[idx]["data_payload_files"])[0]
    m10 = as_list(ctx.map_json[ctx.ref_idx]["location_metadata_files"])[0]

    ddf10 = ctx.read_ds_csv(idx, f10)
    mdf10 = ctx.read_ds_csv(ctx.ref_idx, m10)

    x = ddf10.iloc[1:].copy()
    x["datetime_UTC"] = parse_local_to_utc(x["Date"], "%Y-%m-%d", "America/Denver")

    vcols = [c for c in x.columns if re.search(r"vol_water_content", c)]
    long = x.melt(id_vars=["datetime_UTC"], value_vars=vcols, var_name="name", value_name="volumetric_water_content_m3_m3")
    nm = long['name'].str.extract(r"(.*)\ _(.*)")
    long["site_id"] = nm[0]
    long["depth_m"] = np.select(
        [long["site_id"].eq("PLM1"), long["site_id"].eq("PLM2"), long["site_id"].eq("PLM3")],
        [0.3, 0.28, 0.2],
        default=np.nan,
    )
    long["volumetric_water_content_m3_m3"] = pd.to_numeric(long["volumetric_water_content_m3_m3"], errors="coerce")
    long.loc[long["volumetric_water_content_m3_m3"] == -9999.000, "volumetric_water_content_m3_m3"] = np.nan

    long["is_timeseries"] = True
    long["water_potential_kPa"] = np.nan
    long["replicate"] = 1
    long["gravimetric_water_content_gH2O_gs"] = np.nan

    __harmonized = ensure_harmonized_cols(long)

    sites = __harmonized["site_id"].dropna().astype(str).unique().tolist()
    pattern = r"(?:^|)(%s)$" % "|".join([re.escape(s) for s in sites]) if sites else r"$^"
    loc10 = mdf10[mdf10["Location_ID"].astype(str).str.contains(pattern, regex=True, na=False)].copy()
    loc10["site_id"] = loc10["Location_ID"].str.replace("ER-", "", regex=False)
    loc10 = loc10.rename(columns={"Latitude": "latitude", "Longitude": "longitude"})[["site_id", "latitude", "longitude"]]
    loc10["source_dataset_id"] = ctx.dsid(idx)
    loc10 = add_loc_qc(loc10)
    __locations.append(loc10)

    return DatasetResult(
        dataset_id=ctx.dsid(idx),
        harmonized_data=__harmonized,
        location_data=pd.concat(__locations, ignore_index=True) if __locations else pd.DataFrame()
    )
