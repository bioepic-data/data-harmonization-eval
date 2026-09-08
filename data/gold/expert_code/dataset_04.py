"""
Dataset 4 harmonization.

Dataset: ess-dive-6c7085e9c544cc6-20250424T164534831
DOI: doi:10.15485/2561511
"""

import numpy as np
import pandas as pd

from common import (
    DatasetResult,
    as_list,
    ensure_harmonized_cols,
    add_loc_qc,
)


def harmonize(ctx):
    """Harmonize dataset 4."""
    idx = 4
    __locations = []

    f4 = as_list(ctx.map_json[idx]["data_payload_files"])[0]
    m4 = as_list(ctx.map_json[idx]["location_metadata_files"])[0]
    ddf4 = ctx.read_ds_csv(idx, f4)
    mdf4 = ctx.read_ds_csv(idx, m4)

    x = pd.concat([ddf4.reset_index(drop=True), mdf4.reset_index(drop=True)], axis=1)
    dt = pd.to_datetime(x["datetime"], errors="coerce").dt.tz_localize("America/Denver", ambiguous="NaT", nonexistent="shift_forward")
    x["datetime_UTC"] = dt.dt.tz_convert("UTC")
    x["site_id"] = x["site"]
    x["depth_m"] = np.nan
    x["replicate"] = 1
    x["is_timeseries"] = True
    x["volumetric_water_content_m3_m3"] = pd.to_numeric(x["swc"], errors="coerce")
    x["water_potential_kPa"] = pd.to_numeric(x["swp"], errors="coerce")
    x["gravimetric_water_content_gH2O_gs"] = np.nan
    x = x.sort_values(["datetime_UTC", "site_id"])
    x = x[x["site_id"] != "tb"]

    __harmonized = ensure_harmonized_cols(x)

    loc4 = pd.DataFrame(
        {
            "site_id": ["ph1", "ph2", "sg5"],
            "latitude": [38.92, 38.922583, 38.926250],
            "longitude": [-106.95, -106.947288, -106.98],
        }
    )
    loc4["source_dataset_id"] = ctx.dsid(idx)
    loc4 = add_loc_qc(loc4)
    __locations.append(loc4)

    return DatasetResult(
        dataset_id=ctx.dsid(idx),
        harmonized_data=__harmonized,
        location_data=pd.concat(__locations, ignore_index=True) if __locations else pd.DataFrame()
    )
