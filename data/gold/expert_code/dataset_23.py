"""
Dataset 23 harmonization.

Dataset: ess-dive-a99be52b7a6114c-20230504T210134503379
DOI: doi:10.15485/1842908
"""

import numpy as np
import pandas as pd

from common import (
    DatasetResult,
    as_list,
    parse_local_to_utc,
    ensure_harmonized_cols,
)


def harmonize(ctx):
    """Harmonize dataset 23."""
    idx = 23
    __locations = []

    m23 = as_list(ctx.map_json[ctx.ref_idx]["location_metadata_files"])[0]

    ddf23 = ctx.read_ds_csv(idx, "WM_SWC.csv")
    sdf23 = ctx.read_ds_csv(idx, "sensor_metadata.csv")
    pdf23 = ctx.read_ds_csv(idx, "plot_metadata.csv")
    mdf23 = ctx.read_ds_csv(ctx.ref_idx, m23)

    x = ddf23[ddf23["Sensor.Type"] == "SWC"].copy()
    x["datetime_UTC"] = parse_local_to_utc(x["Date Time"], "%Y-%m-%d %H:%M:%S", "Etc/GMT+7")

    smeta = sdf23[sdf23["Sensor Type"] == "SWC"].copy()
    smeta["Sensor.SN"] = pd.to_numeric(smeta["Sensor.SN"], errors="coerce")
    smeta = smeta[["Sensor.SN", "Depth.cm"]]

    x["Sensor.SN"] = pd.to_numeric(x["Sensor.SN"], errors="coerce")
    x = x.merge(smeta, on="Sensor.SN", how="left")
    x = x.merge(pdf23, on="Plot.Location", how="left")
    x = x[x["Treatment"] == "control"].copy()

    x["site_id"] = x["Point.Location"].astype(str) + "_" + x["Veg"].astype(str)
    x["depth_m"] = pd.to_numeric(x["Depth.cm"], errors="coerce") / 100
    x["is_timeseries"] = True
    x["volumetric_water_content_m3_m3"] = pd.to_numeric(x["Measurement"], errors="coerce")
    x["water_potential_kPa"] = np.nan
    x["gravimetric_water_content_gH2O_gs"] = np.nan

    # x["rep_key"] = x["site_id"].astype(str) + "|" + x["Sensor.SN"].astype(str) + "|" + x["depth_m"].astype(str)
    # x["rep_key"] = x["site_id"].astype(str) + "|" + x["depth_m"].astype(str)
    # x["replicate"] = pd.factorize(x["rep_key"])[0] + 1
    x["replicate"] = x.groupby(["datetime_UTC", "site_id", "depth_m"]).cumcount().astype(int) + 1

    x = x.sort_values(["site_id", "depth_m", "replicate", "datetime_UTC"])

    __harmonized = ensure_harmonized_cols(x)

    loc23 = mdf23.rename(columns={"Location_ID": "site_id", "Latitude": "latitude", "Longitude": "longitude"})[
        ["site_id", "latitude", "longitude"]
    ].copy()
    loc23 = loc23[loc23["site_id"].isin(__harmonized["site_id"].str.split('_').str[0].dropna().unique())].copy()
    loc23["source_dataset_id"] = ctx.dsid(idx)
    loc23["qc_flag"] = np.where(loc23["latitude"].isna() | loc23["longitude"].isna(), "g2", "g1")
    __locations.append(loc23)

    return DatasetResult(
        dataset_id=ctx.dsid(idx),
        harmonized_data=__harmonized,
        location_data=pd.concat(__locations, ignore_index=True) if __locations else pd.DataFrame()
    )
