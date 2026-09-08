"""
Dataset 27 harmonization.

Dataset: ess-dive-c37aaf9ed6d4c0d-20230504T205923265966

Fold evaluation harmonizer for the ER-PHS field datasets. Each of the four
payload CSVs is a single-station hourly time series from an in-situ soil
station. Columns S1-S4 report volumetric water content (m3/m3) and column S5
reports soil water potential (kPa). The station identifier is parsed from the
source filename (ER-PHS1 .. ER-PHS4). Depth is not reported for the individual
sensors in the payload and no ancillary sensor-depth metadata file is present
in the package, so depth_m is left as NA. No location metadata file, cached
ESS-DIVE metadata, or approved location registry is present in the workspace,
so coordinates are unresolvable and receive qc_flag "g2".
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

# Sentinel used in the payload water-potential column for missing readings.
MISSING_SENTINEL = -9999


def harmonize(ctx):
    """Harmonize dataset 27."""
    idx = 27
    __locations = []

    f27 = as_list(ctx.map_json[idx]["data_payload_files"])

    parts = []
    for fname in f27:
        d = ctx.read_ds_csv(idx, fname, encoding="utf-8-sig")

        site = re.search(r"(ER-PHS\d+)", fname)
        site_id = site.group(1) if site else fname

        x = pd.DataFrame()
        x["datetime_UTC"] = parse_local_to_utc(d["Time"], "%m/%d/%Y %H:%M", "America/Denver")
        x["site_id"] = site_id

        vwc_cols = [c for c in d.columns if re.search(r"_wc_", c)]
        wp_cols = [c for c in d.columns if re.search(r"_wp_", c)]

        # Volumetric water content sensors (S1-S4): each sensor is a replicate.
        vwc_parts = []
        for i, c in enumerate(vwc_cols, start=1):
            v = pd.to_numeric(d[c], errors="coerce")
            v = v.where(v > MISSING_SENTINEL, np.nan)
            p = x.copy()
            p["replicate"] = i
            p["volumetric_water_content_m3_m3"] = v
            p["water_potential_kPa"] = np.nan
            vwc_parts.append(p)

        # Soil water potential sensor(s) (S5).
        wp_parts = []
        for i, c in enumerate(wp_cols, start=1):
            v = pd.to_numeric(d[c], errors="coerce")
            v = v.where(v > MISSING_SENTINEL, np.nan)
            p = x.copy()
            p["replicate"] = i
            p["volumetric_water_content_m3_m3"] = np.nan
            p["water_potential_kPa"] = v
            wp_parts.append(p)

        long = pd.concat(vwc_parts + wp_parts, ignore_index=True)
        long["depth_m"] = np.nan
        long["is_timeseries"] = True
        long["gravimetric_water_content_gH2O_gs"] = np.nan

        # Drop rows where both moisture measurements are missing.
        long = long[
            long["volumetric_water_content_m3_m3"].notna()
            | long["water_potential_kPa"].notna()
        ].copy()

        parts.append(long)

    combined = pd.concat(parts, ignore_index=True)
    __harmonized = ensure_harmonized_cols(combined)

    # No location metadata file, cached package metadata, or approved location
    # registry is available in the workspace -> coordinates unresolvable (g2).
    loc27 = pd.DataFrame(
        {
            "site_id": __harmonized["site_id"].dropna().unique(),
            "latitude": np.nan,
            "longitude": np.nan,
        }
    )
    loc27["source_dataset_id"] = ctx.dsid(idx)
    loc27 = add_loc_qc(loc27)
    __locations.append(loc27)

    return DatasetResult(
        dataset_id=ctx.dsid(idx),
        harmonized_data=__harmonized,
        location_data=pd.concat(__locations, ignore_index=True) if __locations else pd.DataFrame(),
    )
