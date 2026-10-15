"""
Dataset 18 harmonization.

Dataset: ess-dive-b924878d23c9dd7-20250214T163427929
DOI: doi:10.15485/1577267
"""

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
    """Harmonize dataset 18."""
    idx = 18
    __locations = []

    f18 = as_list(ctx.map_json[idx]["data_payload_files"])[0]
    m18 = as_list(ctx.map_json[idx]["location_metadata_files"])[0]

    ddf18 = ctx.read_ds_csv(idx, f18, encoding="latin1")
    mdf18 = ctx.read_ds_csv(idx, m18, encoding="latin1")

    x = ddf18.copy()
    x["datetime_UTC"] = parse_local_to_utc(x["Date_Collected"], "%m/%d/%Y", "Etc/GMT+7")
    x["site_id"] = (
        x["Field_Site"].fillna('').astype(str) + "_" +
        x["Plot"].fillna('').astype(str) + "_" +
        x["Topographic_Position"].fillna('').astype(str)
        ).str.replace(r"_$", "", regex=True).str.replace(r" ", "_", regex=True)

    x["depth_m"] = np.select(
        [
            x["Depth_Increment"].eq("0-5 cm"),
            x["Depth_Increment"].isin(["5-15 cm", "15-May"]),
            x["Depth_Increment"].eq("15 cm +"),
        ],
        [0.025, 0.10, 0.15],
        default=np.nan,
    )
    x["is_timeseries"] = False
    x["water_potential_kPa"] = np.nan
    x["volumetric_water_content_m3_m3"] = np.nan
    x["gravimetric_water_content_gH2O_gs"] = pd.to_numeric(x["Soil Water Content (g H2O per gram  soil)"], errors="coerce")
    x["replicate"] = x["Replicate"]

    __harmonized = ensure_harmonized_cols(x)

    loc18 = mdf18.copy()
    loc18["site_id"] = (loc18["Field_Site"].fillna('').astype(str) + "_" +
        loc18["Plot"].fillna('').astype(str) + "_" +
        loc18["Topographic_Position"].fillna('').astype(str)
        ).str.replace(r"_$", "", regex=True).str.replace(r" ", "_", regex=True)
    loc18["latitude"] = pd.to_numeric(loc18["Latitude"].astype(str).str.extract(r"([-+]?\d*\.?\d+)")[0], errors="coerce")
    loc18["longitude"] = pd.to_numeric(loc18["Longitude"].astype(str).str.extract(r"([-+]?\d*\.?\d+)")[0], errors="coerce")
    loc18["source_dataset_id"] = ctx.dsid(idx)
    loc18 = loc18[["site_id", "latitude", "longitude", "source_dataset_id"]].drop_duplicates()
    loc18 = add_loc_qc(loc18)
    __locations.append(loc18)

    return DatasetResult(
        dataset_id=ctx.dsid(idx),
        harmonized_data=__harmonized,
        location_data=pd.concat(__locations, ignore_index=True) if __locations else pd.DataFrame()
    )
