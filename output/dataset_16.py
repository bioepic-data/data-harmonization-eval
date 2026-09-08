"""
Dataset 16 harmonization.

Dataset: ess-dive-b3d271f19a94e8d-20260114T204512119
DOI: doi:10.15485/2566877 (not resolvable inside fold workspace; see notes)

WFSFA East River / Snodgrass ecohydrology sensor towers (Wu et al.).
Wide-format hourly sensor-tower payloads (one file per site) with soil water
content (SWC_H_V_R, % VWC) and soil water potential (SWP_H_V_R, kPa) columns.
Sensor depths are not encoded in the payload column names; they are recorded in
the instrument metadata file as the HEIGHT field (negative = below surface).
"""

from __future__ import annotations

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
    """Harmonize dataset 16."""
    idx = 16

    entry = ctx.map_json[idx]
    data_files = as_list(entry["data_payload_files"])
    loc_files = as_list(entry["location_metadata_files"])
    sensor_files = as_list(entry["sensor_metadata_files"])

    # --- Instrument metadata: build (site_id, variable) -> depth_m lookup ---
    inst = pd.concat([ctx.read_ds_csv(idx, f) for f in sensor_files], ignore_index=True)
    soil = inst[inst["VARIABLE"].str.match(r"^(SWC|SWP)_")].copy()
    # HEIGHT is signed height above ground; soil sensors are negative (below surface).
    soil["depth_m"] = -pd.to_numeric(soil["HEIGHT"], errors="coerce")
    depth_lookup = (
        soil.groupby(["SITE_ID", "VARIABLE"])["depth_m"].first().to_dict()
    )

    # --- Site metadata: coordinates in decimal degrees ---
    site = pd.concat([ctx.read_ds_csv(idx, f) for f in loc_files], ignore_index=True)

    __harmonized_parts = []
    for f in data_files:
        # site_id embedded in filename: data_<SITE_ID>_v1-1.csv
        m = re.search(r"data_(.+?)_v", f.split("/")[-1])
        site_id = m.group(1)

        df = ctx.read_ds_csv(idx, f, na_values=[-9999.0, 9999.0])

        value_cols = [c for c in df.columns if re.match(r"^(SWC|SWP)_\d", c)]
        x = df[["TIMESTAMP_START"] + value_cols].copy()
        x["datetime_UTC"] = parse_local_to_utc(
            x["TIMESTAMP_START"], "%Y-%m-%d %H:%M:%S", "Etc/GMT+7"
        )
        x = x.drop(columns=["TIMESTAMP_START"])

        long = x.melt(
            id_vars=["datetime_UTC"],
            value_vars=value_cols,
            var_name="variable",
            value_name="value",
        )
        long["value"] = pd.to_numeric(long["value"], errors="coerce")

        # Depth from instrument metadata; drop sensors without a known depth.
        long["depth_m"] = long["variable"].map(
            lambda v: depth_lookup.get((site_id, v), np.nan)
        )

        # Variable family (SWC -> VWC, SWP -> water potential) and position suffix.
        parts = long["variable"].str.extract(r"^(SWC|SWP)_(\d+)_(\d+)_(\d+)$")
        long["var_family"] = parts[0]
        # replicate: horizontal/vertical/replicate index triple -> integer replicate
        long["replicate"] = pd.to_numeric(parts[3], errors="coerce").astype("Int64")

        # Pivot so VWC and water potential share depth/time/replicate rows.
        wide = (
            long.pivot_table(
                index=["datetime_UTC", "depth_m", "replicate"],
                columns="var_family",
                values="value",
                aggfunc="first",
            )
            .reset_index()
        )
        if "SWC" in wide.columns:
            # % VWC -> m3/m3
            wide["volumetric_water_content_m3_m3"] = wide["SWC"] / 100.0
        else:
            wide["volumetric_water_content_m3_m3"] = np.nan
        if "SWP" in wide.columns:
            # source already kPa (negative matric potential)
            wide["water_potential_kPa"] = wide["SWP"]
        else:
            wide["water_potential_kPa"] = np.nan

        wide["site_id"] = site_id
        wide["is_timeseries"] = True
        wide["gravimetric_water_content_gH2O_gs"] = np.nan

        # Drop rows lacking a resolvable depth or any measurement value.
        wide = wide[wide["depth_m"].notna()]
        keep = wide["volumetric_water_content_m3_m3"].notna() | wide["water_potential_kPa"].notna()
        wide = wide[keep]

        __harmonized_parts.append(ensure_harmonized_cols(wide))

    __harmonized = pd.concat(__harmonized_parts, ignore_index=True)

    # --- Locations ---
    loc = site.rename(
        columns={
            "SITE_ID": "site_id",
            "LOCATION_LAT": "latitude",
            "LOCATION_LONG": "longitude",
        }
    )[["site_id", "latitude", "longitude"]].copy()
    loc["source_dataset_id"] = ctx.dsid(idx)
    loc = add_loc_qc(loc)

    return DatasetResult(
        dataset_id=ctx.dsid(idx),
        harmonized_data=__harmonized,
        location_data=loc,
    )
