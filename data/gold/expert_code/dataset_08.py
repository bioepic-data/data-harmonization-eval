"""
Dataset 8 harmonization.

Dataset: ess-dive-61a0ecd70856892-20230808T205724993
DOI: doi:10.15485/1958210
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
    """Harmonize dataset 8."""
    idx = 8
    __locations = []

    f8 = as_list(ctx.map_json[idx]["data_payload_files"])
    m8 = as_list(ctx.map_json[idx]["location_metadata_files"])

    ls8 = [ctx.read_ds_csv(idx, x) for x in f8]
    mdf8 = pd.concat([ctx.read_ds_csv(idx, x) for x in m8], ignore_index=True)

    ls8_h = []
    for d in ls8:
        cols = [c for c in d.columns if re.search(r"SoilMoisture|SoilMatricPot", c)]
        x = d[["DateTime.MST"] + cols].copy()
        x["datetime_UTC"] = parse_local_to_utc(x["DateTime.MST"], "%Y-%m-%d %H:%M:%S", "Etc/GMT+7")
        x = x.drop(columns=["DateTime.MST"])
        x.columns = [re.sub(r"\.m3\.m3|\.kPa", "", c) for c in x.columns]
        print(x.columns)

        value_cols = [c for c in x.columns if re.search(r"SoilMoisture|SoilMatricPot", c)]
        long = x.melt(id_vars=["datetime_UTC"], value_vars=value_cols, var_name="name", value_name="value")
        m = long["name"].str.extract(r"^(SoilMoisture|SoilMatricPot)_(.*)$")

        long["var"] = m[0]
        long["depth_m"] = pd.to_numeric(m[1].str.replace("cm", "", regex=False), errors="coerce") / 100
        long["value"] = pd.to_numeric(long["value"], errors="coerce")
        long.loc[long["value"] == -9999, "value"] = np.nan

        wide = (
            long.pivot_table(
                index=["datetime_UTC", "depth_m"],
                columns="var",
                values="value",
                aggfunc="first",
            )
            .reset_index()
            .rename(columns={"SoilMoisture": "volumetric_water_content_m3_m3", "SoilMatricPot": "water_potential_kPa"})
        )

        wide["replicate"] = int(1)
        wide["site_id"] = "Slate River OBJ-2"
        wide["is_timeseries"] = True
        wide["gravimetric_water_content_gH2O_gs"] = np.nan

        ls8_h.append(ensure_harmonized_cols(wide))

    __harmonized = pd.concat(ls8_h, ignore_index=True)

    loc8 = mdf8.iloc[[0]].rename(columns={"SiteName": "site_id", "Latitude": "latitude", "Longitude": "longitude"})[
        ["site_id", "latitude", "longitude"]
    ].copy()
    loc8["source_dataset_id"] = ctx.dsid(idx)
    loc8 = add_loc_qc(loc8)
    __locations.append(loc8)

    return DatasetResult(
        dataset_id=ctx.dsid(idx),
        harmonized_data=__harmonized,
        location_data=pd.concat(__locations, ignore_index=True) if __locations else pd.DataFrame()
    )
