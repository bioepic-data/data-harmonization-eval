"""
Dataset 27 harmonization.

Dataset: ess-dive-c37aaf9ed6d4c0d-20230504T205923265966
DOI: doi:10.15485/1788230
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
    """Harmonize dataset 27."""
    idx = 27
    __locations = []

    f27 = as_list(ctx.map_json[idx]["data_payload_files"])
    m27 = as_list(ctx.map_json[ctx.ref_idx]["location_metadata_files"])[0]

    ls27 = [ctx.read_ds_csv(idx, x) for x in f27]
    mdf27 = ctx.read_ds_csv(ctx.ref_idx, m27)

    ls27_h = []
    for i, d in enumerate(ls27):
        x = d.copy()
        dt = pd.to_datetime(x["Time"], format="%m/%d/%Y %H:%M", errors="coerce")
        dt = dt.dt.tz_localize("Etc/GMT+7", ambiguous="NaT", nonexistent="shift_forward")
        x["datetime_UTC"] = dt.dt.tz_convert("UTC")

        cols = [c for c in x.columns if re.search(r"^S[1-4]_wc_\(m3/m3\)$|^S5_wp_\(kPa\)$", c)]
        long = x.melt(id_vars=["datetime_UTC"], value_vars=cols, var_name="name", value_name="value")

        long["variable"] = np.select(
            [
                long["name"].str.contains("_wc_", regex=False, na=False),
                long["name"].str.contains("_wp_", regex=False, na=False),
            ],
            ["volumetric_water_content_m3_m3", "water_potential_kPa"],
            default=np.nan,
        )

        fname = f27[i]
        long["depth_m"] = np.select(
            [
                long["name"].str.contains(r"^S1_", regex=True, na=False) & pd.Series([bool(re.search(r"ER-PHS4", fname))] * len(long)),
                long["name"].str.contains(r"^S1_", regex=True, na=False),
                long["name"].str.contains(r"^S2_", regex=True, na=False),
                long["name"].str.contains(r"^S3_", regex=True, na=False),
                long["name"].str.contains(r"^S4_", regex=True, na=False),
                long["name"].str.contains(r"^S5_", regex=True, na=False),
            ],
            [1.06, 1.15, 0.60, 0.30, 0.10, 0.30],
            default=np.nan,
        )

        site_match = re.search(r"ER-PHS[1-4]", fname)
        site_id_val = site_match.group(0) if site_match else np.nan
        long["site_id"] = site_id_val
        long["replicate"] = 1
        long["is_timeseries"] = True

        long = long[long["value"].notna() & long["variable"].notna() & long["depth_m"].notna()].copy()
        wide = (
            long.pivot_table(
                index=["datetime_UTC", "site_id", "depth_m", "replicate", "is_timeseries"],
                columns="variable",
                values="value",
                aggfunc="first",
            )
            .reset_index()
        )

        wide["volumetric_water_content_m3_m3"] = pd.to_numeric(wide.get("volumetric_water_content_m3_m3"), errors="coerce")
        wide["water_potential_kPa"] = pd.to_numeric(wide.get("water_potential_kPa"), errors="coerce")
        wide["water_potential_kPa"] = wide["water_potential_kPa"].replace(-99999, np.nan)
        wide["gravimetric_water_content_gH2O_gs"] = np.nan

        ls27_h.append(ensure_harmonized_cols(wide))

    __harmonized = pd.concat(ls27_h, ignore_index=True)

    loc27 = mdf27.rename(columns={"Location_ID": "site_id", "Latitude": "latitude", "Longitude": "longitude"})[
        ["site_id", "latitude", "longitude"]
    ].copy()
    loc27 = loc27[loc27["site_id"].isin(__harmonized["site_id"].dropna().unique())]
    loc27["source_dataset_id"] = ctx.dsid(idx)
    loc27 = add_loc_qc(loc27)
    __locations.append(loc27)

    return DatasetResult(
        dataset_id=ctx.dsid(idx),
        harmonized_data=__harmonized,
        location_data=pd.concat(__locations, ignore_index=True) if __locations else pd.DataFrame()
    )
