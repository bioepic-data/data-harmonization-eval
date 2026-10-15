"""
Dataset 1 harmonization.

Dataset: ess-dive-beca0be9bb38ece-20250516T122010234
DOI: doi:10.15485/2566877
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
    """Harmonize dataset 1."""
    idx = 1
    __locations = []

    f1 = as_list(ctx.map_json[idx]["data_payload_files"])
    m1 = as_list(ctx.map_json[idx]["location_metadata_files"])[0]

    ls1 = [ctx.read_ds_csv(idx, x) for x in f1]
    mdf1 = ctx.read_ds_csv(idx, m1)

    ls1_h = []
    for i, d in enumerate(ls1):
        cols = [c for c in d.columns if re.search(r"Water_Content|VWC|Potential", c)]
        x = d[["Time"] + cols].copy()

        x["datetime_UTC"] = parse_local_to_utc(x["Time"], "%Y-%m-%d %H:%M:%S", "Etc/GMT+7")
        x = x.drop(columns=["Time"])

        long = x.melt(id_vars=["datetime_UTC"], var_name="name", value_name="value")
        m = long["name"].str.extract(r"^(.*)_at_(.*)$")
        long["var_name"] = m[0]
        long["depth"] = m[1]
        long = long.dropna(subset=["depth"])

        long["value"] = pd.to_numeric(long["value"], errors="coerce")
        long.loc[long["value"] == -9999, "value"] = np.nan
        long = long.dropna(subset=["value"])

        long["dest_var"] = np.where(
            long["var_name"].str.contains(r"Water_Content|VWC", regex=True, na=False),
            "volumetric_water_content_m3_m3",
            np.where(
                long["var_name"].str.contains(r"Potential", regex=True, na=False),
                "water_potential_kPa",
                np.nan,
            ),
        )
        long = long.dropna(subset=["dest_var"])

        long["replicate"] = long.groupby(["datetime_UTC", "depth", "dest_var"]).cumcount() + 1

        wide = (
            long.pivot_table(
                index=["datetime_UTC", "depth", "replicate"],
                columns="dest_var",
                values="value",
                aggfunc="first",
            )
            .reset_index()
        )

        wide["depth_m"] = pd.to_numeric(wide["depth"].str.replace("cm", "", regex=False), errors="coerce") / 100
        wide["site_id"] = re.sub(r"\.csv$", "", f1[i])
        wide["replicate"] = wide["replicate"].astype(int)
        wide["is_timeseries"] = True
        wide["gravimetric_water_content_gH2O_gs"] = np.nan

        ls1_h.append(ensure_harmonized_cols(wide))

    df1_harmonized = pd.concat(ls1_h, ignore_index=True)

    loc1_tmp = utm32613_to_latlon(mdf1, "Easting", "Northing")
    loc1 = pd.DataFrame(
        {
            "site_id": loc1_tmp["Name"],
            "latitude": loc1_tmp["latitude"],
            "longitude": loc1_tmp["longitude"],
        }
    )
    loc1["source_dataset_id"] = ctx.dsid(idx)
    loc1 = add_loc_qc(loc1)
    __locations.append(loc1)

    return DatasetResult(
        dataset_id=ctx.dsid(idx),
        harmonized_data=df1_harmonized,
        location_data=pd.concat(__locations, ignore_index=True) if __locations else pd.DataFrame()
    )
