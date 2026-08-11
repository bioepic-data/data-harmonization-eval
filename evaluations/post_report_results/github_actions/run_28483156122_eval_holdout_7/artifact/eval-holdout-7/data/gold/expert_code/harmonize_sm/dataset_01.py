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
        # Select moisture-related columns
        cols = [c for c in d.columns if re.search(r"Water_Content|VWC|Potential", c)]
        x = d[["Time"] + cols].copy()

        # datetime: pattern_1 - Convert 'Time' to ISO 8601 UTC format
        x["datetime_UTC"] = parse_local_to_utc(x["Time"], "%Y-%m-%d %H:%M:%S", "America/Denver")
        x["interval_min"] = interval_min(x["datetime_UTC"])
        x = x.drop(columns=["Time"])

        # volumetric_water_content: pattern_1 & pattern_2 + soil_water_potential: pattern_1
        # Coerce from 'wide' format with column variables containing depth and replicate information to 'long' format
        long = x.melt(id_vars=["datetime_UTC", "interval_min"], var_name="name", value_name="value")
        m = long["name"].str.extract(r"^(.*)_at_(.*)$")
        long["var_name"] = m[0]
        long["depth"] = m[1]
        long = long.dropna(subset=["depth"])

        # Clean -9999 sentinel values
        long["value"] = pd.to_numeric(long["value"], errors="coerce")
        long.loc[long["value"] == -9999, "value"] = np.nan
        long = long.dropna(subset=["value"])

        # Map source variables to destination variables
        # m3_m3_Water_Content_i_at_jcm or m3_m3_VWC_at_jcm -> volumetric_water_content_m3_m3
        # kPa_Potential_i_at_jcm -> water_potential_kPa
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

        # replicate: pattern_1 - Parse integer i from '*_i_at_jcm'
        long["replicate"] = long.groupby(["datetime_UTC", "depth", "dest_var"]).cumcount() + 1

        # Pivot to wide format with separate columns for volumetric water content and water potential
        wide = (
            long.pivot_table(
                index=["datetime_UTC", "interval_min", "depth", "replicate"],
                columns="dest_var",
                values="value",
                aggfunc="first",
            )
            .reset_index()
        )

        # depth: pattern_1 - Parse float j from '*_at_jcm' and divide by 1e2 to convert from cm to m
        wide["depth_m"] = pd.to_numeric(wide["depth"].str.replace("cm", "", regex=False), errors="coerce") / 100

        # site_id: pattern_1 - Parse site_id from source filename
        wide["site_id"] = re.sub(r"\.csv$", "", f1[i])
        wide["is_timeseries"] = True
        wide["gravimetric_water_content_gH2O_gs"] = np.nan

        ls1_h.append(ensure_harmonized_cols(wide))

    df1_harmonized = pd.concat(ls1_h, ignore_index=True)
    __harmonized = df1_harmonized
    __dataset_id = dsid(idx)

    # latitude: pattern_1 & longitude: pattern_1
    # Look up 'Northing' and 'Easting' for 'site_id' in Sensor_Location.csv
    # Reproject from EPSG:32613 (WGS84 UTM Zone 13N, meters) to EPSG:4326 (WGS84, decimal degrees)
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
