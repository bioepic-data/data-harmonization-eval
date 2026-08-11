"""Expert harmonization for dataset index 23.

Auto-split from the expert monolith; the body below is verbatim except that
the shared-accumulator writes are captured into the returned DatasetResult.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from common import (
    DatasetResult,
    as_list,
    parse_local_to_utc,
    interval_min,
    ensure_harmonized_cols,
    add_loc_qc,
)


def harmonize(ctx):
    """Harmonize dataset 23, returning its DatasetResult."""
    map_json = ctx.map_json
    REF_IDX = ctx.ref_idx
    dsid = ctx.dsid
    read_ds_csv = ctx.read_ds_csv
    __locations = []

    # =============================================================
    # Dataset 23
    # =============================================================
    idx = 23
    m23 = as_list(map_json[REF_IDX]["location_metadata_files"])[0]

    ddf23 = read_ds_csv(idx, "WM_SWC.csv")
    sdf23 = read_ds_csv(idx, "sensor_metadata.csv")
    pdf23 = read_ds_csv(idx, "plot_metadata.csv")
    mdf23 = read_ds_csv(REF_IDX, m23)

    # Filter to soil water content sensors
    x = ddf23[ddf23["Sensor.Type"] == "SWC"].copy()

    # datetime: pattern_1 - Convert 'Date Time' to ISO 8601 UTC format
    x["datetime_UTC"] = parse_local_to_utc(x["Date Time"], "%Y-%m-%d %H:%M:%S", "America/Denver")

    # Merge sensor depth metadata
    smeta = sdf23[sdf23["Sensor Type"] == "SWC"].copy()
    smeta["Sensor.SN"] = pd.to_numeric(smeta["Sensor.SN"], errors="coerce")
    smeta = smeta[["Sensor.SN", "Depth.cm"]]

    x["Sensor.SN"] = pd.to_numeric(x["Sensor.SN"], errors="coerce")
    x = x.merge(smeta, on="Sensor.SN", how="left")
    x = x.merge(pdf23, on="Plot.Location", how="left")
    x = x[x["Treatment"] == "control"].copy()

    # site_id: pattern_1 - Construct from 'Point.Location' and 'Veg'
    x["site_id"] = x["Point.Location"].astype(str) + "_" + x["Veg"].astype(str)

    # depth: pattern_1 - Parse from sensor metadata and divide by 1e2 to convert from cm to m
    x["depth_m"] = pd.to_numeric(x["Depth.cm"], errors="coerce") / 100
    x["is_timeseries"] = True

    # volumetric_water_content: pattern_1 - Rename 'Measurement' variable (source units are m3/m3)
    x["volumetric_water_content_m3_m3"] = pd.to_numeric(x["Measurement"], errors="coerce")

    # soil_water_potential: pattern_1 - Not reported in source; populate with NA
    x["water_potential_kPa"] = np.nan
    x["gravimetric_water_content_gH2O_gs"] = np.nan

    # replicate: pattern_1 - Infer from unique sensor/location/depth combinations
    x["rep_key"] = x["site_id"].astype(str) + "|" + x["Sensor.SN"].astype(str) + "|" + x["depth_m"].astype(str)
    x["replicate"] = pd.factorize(x["rep_key"])[0] + 1

    x = x.sort_values(["site_id", "depth_m", "replicate", "datetime_UTC"])
    x["interval_min"] = x.groupby(["site_id", "depth_m", "replicate"])["datetime_UTC"].diff().dt.total_seconds() / 60.0
    x.loc[x["interval_min"] < 0, "interval_min"] = np.nan

    df23_harmonized = ensure_harmonized_cols(x)
    __harmonized = df23_harmonized
    __dataset_id = dsid(idx)

    # latitude: pattern_1 & longitude: pattern_1
    # Geospatial information not directly provided for constructed site_id
    # Create placeholder for composite site_ids
    loc23 = pd.DataFrame({"site_id": df23_harmonized["site_id"].dropna().unique()})
    loc23["latitude"] = np.nan
    loc23["longitude"] = np.nan
    loc23 = loc23[loc23["site_id"].isin(df23_harmonized["site_id"].dropna().unique())].copy()
    loc23["source_dataset_id"] = dsid(idx)
    loc23 = add_loc_qc(loc23).drop_duplicates()
    __locations.append(loc23)

    # Look up location data from reference dataset for base point locations
    loc23 = mdf23.rename(columns={"Location_ID": "site_id", "Latitude": "latitude", "Longitude": "longitude"})[
        ["site_id", "latitude", "longitude"]
    ].copy()
    loc23 = loc23[loc23["site_id"].isin(df23_harmonized["site_id"].str.split('_').str[0].dropna().unique())].copy()
    loc23["source_dataset_id"] = dsid(idx)
    loc23 = add_loc_qc(loc23)
    __locations.append(loc23)


    return DatasetResult(__dataset_id, __harmonized, __locations)
