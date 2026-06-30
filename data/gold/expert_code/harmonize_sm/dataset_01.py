"""Expert harmonization for dataset index 1.

Auto-split from the expert monolith; the body below is verbatim except that
the shared-accumulator writes are captured into the returned DatasetResult.
"""
from __future__ import annotations

import re
import numpy as np
import pandas as pd

from common import (
    DatasetResult,
    as_list,
    parse_local_to_utc,
    interval_min,
    utm32613_to_latlon,
    ensure_harmonized_cols,
    add_loc_qc,
)


def harmonize(ctx):
    """Harmonize dataset 1, returning its DatasetResult."""
    map_json = ctx.map_json
    REF_IDX = ctx.ref_idx
    dsid = ctx.dsid
    read_ds_csv = ctx.read_ds_csv
    __locations = []

    # =============================================================
    # Dataset 1
    # =============================================================
    idx = 1
    f1 = as_list(map_json[idx]["data_payload_files"])
    m1 = as_list(map_json[idx]["location_metadata_files"])[0]

    ls1 = [read_ds_csv(idx, x) for x in f1]
    mdf1 = read_ds_csv(idx, m1)

    ls1_h = []
    for i, d in enumerate(ls1):
        cols = [c for c in d.columns if re.search(r"Water_Content|VWC|Potential", c)]
        x = d[["Time"] + cols].copy()

        x["datetime_UTC"] = parse_local_to_utc(x["Time"], "%Y-%m-%d %H:%M:%S", "America/Denver")
        x["interval_min"] = interval_min(x["datetime_UTC"])
        x = x.drop(columns=["Time"])

        long = x.melt(id_vars=["datetime_UTC", "interval_min"], var_name="name", value_name="value")
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
                index=["datetime_UTC", "interval_min", "depth", "replicate"],
                columns="dest_var",
                values="value",
                aggfunc="first",
            )
            .reset_index()
        )

        wide["depth_m"] = pd.to_numeric(wide["depth"].str.replace("cm", "", regex=False), errors="coerce") / 100
        wide["site_id"] = re.sub(r"\.csv$", "", f1[i])
        wide["is_timeseries"] = True
        wide["gravimetric_water_content_gH2O_gs"] = np.nan

        ls1_h.append(ensure_harmonized_cols(wide))

    df1_harmonized = pd.concat(ls1_h, ignore_index=True)
    __harmonized = df1_harmonized
    __dataset_id = dsid(idx)

    loc1_tmp = utm32613_to_latlon(mdf1, "Easting", "Northing")
    loc1 = pd.DataFrame(
        {
            "site_id": loc1_tmp["Name"],
            "latitude": loc1_tmp["latitude"],
            "longitude": loc1_tmp["longitude"],
        }
    )
    loc1["source_dataset_id"] = dsid(idx)
    loc1 = add_loc_qc(loc1)
    __locations.append(loc1)

    return DatasetResult(__dataset_id, __harmonized, __locations)
