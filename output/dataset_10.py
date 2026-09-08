"""
Dataset 10 harmonization.

Dataset: ess-dive-01092fc392bc46d-20240819T143818677
DOI: (not available in fold workspace)

Wide-format soil volumetric water content extracted from a figure (Fig 4e).
One date column plus three site columns (PLM1, PLM2, PLM3), each already
reported in m3/m3. A units row ("YYYY-MM-DD", "m3/m3", ...) precedes the data
and is skipped. Sentinel -9999 marks missing values.

Location: no location file, no cached ESS-DIVE metadata, and no approved
location registry are available in this fold workspace, so coordinates are
unresolvable and every site is flagged g2.
"""

import re
import numpy as np
import pandas as pd

from common import (
    DatasetResult,
    as_list,
    ensure_harmonized_cols,
    add_loc_qc,
)


def harmonize(ctx):
    """Harmonize dataset 10."""
    idx = 10
    __locations = []

    f10 = as_list(ctx.map_json[idx]["data_payload_files"])[0]

    ddf10 = ctx.read_ds_csv(idx, f10, skiprows=[1])

    x = ddf10.copy()

    dt = pd.to_datetime(x["Date"], format="%Y-%m-%d", errors="coerce")
    dt = dt.dt.tz_localize("UTC")
    x["datetime_UTC"] = dt
    x = x.drop(columns=["Date"])

    vwc_cols = [c for c in x.columns if re.search(r"vol_water_content", c)]

    long = x.melt(
        id_vars=["datetime_UTC"],
        value_vars=vwc_cols,
        var_name="name",
        value_name="volumetric_water_content_m3_m3",
    )

    long["site_id"] = long["name"].str.extract(r"(PLM\d+)")[0]
    long["volumetric_water_content_m3_m3"] = pd.to_numeric(
        long["volumetric_water_content_m3_m3"], errors="coerce"
    )
    long.loc[long["volumetric_water_content_m3_m3"] == -9999, "volumetric_water_content_m3_m3"] = np.nan
    long = long.dropna(subset=["volumetric_water_content_m3_m3"])

    long["depth_m"] = np.nan
    long["replicate"] = 1
    long["is_timeseries"] = True
    long["water_potential_kPa"] = np.nan
    long["gravimetric_water_content_gH2O_gs"] = np.nan

    __harmonized = ensure_harmonized_cols(long)

    loc10 = pd.DataFrame(
        {
            "site_id": sorted(long["site_id"].dropna().unique()),
            "latitude": np.nan,
            "longitude": np.nan,
        }
    )
    loc10["source_dataset_id"] = ctx.dsid(idx)
    loc10 = add_loc_qc(loc10)
    __locations.append(loc10)

    return DatasetResult(
        dataset_id=ctx.dsid(idx),
        harmonized_data=__harmonized,
        location_data=pd.concat(__locations, ignore_index=True) if __locations else pd.DataFrame(),
    )
