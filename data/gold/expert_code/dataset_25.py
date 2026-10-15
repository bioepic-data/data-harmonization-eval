"""
Dataset 25 harmonization.

Dataset: ess-dive-e67ab1151ebc525-20230929T190307767
DOI: doi:10.6084/M9.FIGSHARE.7834406.V2
"""

import re
import numpy as np
import pandas as pd

from common import (
    DatasetResult,
    parse_local_to_utc,
    ensure_harmonized_cols,
    add_loc_qc,
)


def harmonize(ctx):
    """Harmonize dataset 25."""
    idx = 25
    __locations = []

    ddf25_conifer = ctx.read_ds_csv(idx, "Carbone_conifer.csv")
    ddf25_aspen = ctx.read_ds_csv(idx, "Carbone_aspen.csv", header=None)
    ddf25_aspen.columns = ddf25_conifer.columns

    ddf25 = pd.concat(
        [
            ddf25_aspen.assign(site_id="aspen"),
            ddf25_conifer.assign(site_id="conifer"),
        ],
        ignore_index=True,
    )

    x = ddf25.copy()
    x["datetime_UTC"] = parse_local_to_utc(
        x["Year"].astype(str) + "-" + x["Month"].astype(str) + "-" + x["Day"].astype(str) + "-" + x["Hour"].astype(str),
        "%Y-%m-%d-%H",
        "Etc/GMT+7",
    )
    x = x.sort_values(["site_id", "datetime_UTC"])

    vwc_cols = [c for c in x.columns if re.search(r"vwc", c, flags=re.IGNORECASE)]
    long = x.melt(
        id_vars=["datetime_UTC", "site_id"],
        value_vars=vwc_cols,
        var_name="name",
        value_name="volumetric_water_content_m3_m3",
    )
    long["depth_m"] = pd.to_numeric(long["name"].str.extract(r"(\d+)")[0], errors="coerce") / 100
    long["replicate"] = 1
    long["is_timeseries"] = True
    long["water_potential_kPa"] = np.nan
    long["gravimetric_water_content_gH2O_gs"] = np.nan
    long["volumetric_water_content_m3_m3"] = pd.to_numeric(long["volumetric_water_content_m3_m3"], errors="coerce")
    long = long[long["volumetric_water_content_m3_m3"].notna()]

    __harmonized = ensure_harmonized_cols(long)

    loc25 = pd.DataFrame(
        {
            "site_id": ["aspen", "conifer"],
            "latitude": [38.9581589, 38.9581589],
            "longitude": [-106.9855848, -106.9855848],
        }
    ).drop_duplicates()
    loc25["source_dataset_id"] = ctx.dsid(idx)
    loc25 = add_loc_qc(loc25)
    __locations.append(loc25)

    return DatasetResult(
        dataset_id=ctx.dsid(idx),
        harmonized_data=__harmonized,
        location_data=pd.concat(__locations, ignore_index=True) if __locations else pd.DataFrame()
    )
