"""
Dataset 24 harmonization.

Dataset: ess-dive-daa156d2129c471-20250716T160748658
DOI: doi:10.15485/2462766
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
    """Harmonize dataset 24."""
    idx = 24
    __locations = []

    f24 = as_list(ctx.map_json[idx]["data_payload_files"])[0]
    m24 = as_list(ctx.map_json[idx]["location_metadata_files"])[0]

    ddf24 = ctx.read_ds_csv(idx, f24, sep=";")
    mdf24 = ctx.read_ds_csv(idx, m24, sep=";")

    x = ddf24.copy()
    keep = ["Timestamp"] + [c for c in x.columns if re.search(r"^P[12]_MP_(15|30|60)$", c)]
    x = x[keep]
    x["datetime_UTC"] = parse_local_to_utc(x["Timestamp"], "%Y-%m-%d", "UTC")

    x = x.drop(columns=["Timestamp"])

    mp_cols = [c for c in x.columns if re.search(r"^P[12]_MP_(15|30|60)$", c)]
    long = x.melt(id_vars=["datetime_UTC"], value_vars=mp_cols, var_name="name", value_name="MP")
    m = long["name"].str.extract(r"^(P[12])_(MP)_(\d+)$")
    long["site_id"] = m[0]
    long["depth_cm"] = m[2]
    long = long[long["MP"].notna()].copy()
    long["depth_m"] = pd.to_numeric(long["depth_cm"], errors="coerce") / 100
    long["replicate"] = 1
    long["is_timeseries"] = True
    long["volumetric_water_content_m3_m3"] = np.nan
    long["gravimetric_water_content_gH2O_gs"] = np.nan
    long["water_potential_kPa"] = pd.to_numeric(long["MP"], errors="coerce")
    long = long[long["water_potential_kPa"].notna()]

    __harmonized = ensure_harmonized_cols(long)

    loc24 = mdf24.rename(columns={"ID": "site_id", "Latitude": "latitude", "Longitude": "longitude"})[
        ["site_id", "latitude", "longitude"]
    ].copy()
    loc24 = loc24[loc24["site_id"].isin(__harmonized["site_id"].dropna().unique())].drop_duplicates()
    loc24["source_dataset_id"] = ctx.dsid(idx)
    loc24 = add_loc_qc(loc24)
    __locations.append(loc24)

    return DatasetResult(
        dataset_id=ctx.dsid(idx),
        harmonized_data=__harmonized,
        location_data=pd.concat(__locations, ignore_index=True) if __locations else pd.DataFrame()
    )
