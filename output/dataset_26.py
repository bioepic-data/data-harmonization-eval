"""
Dataset 26 harmonization.

Dataset: ess-dive-f782da867133296-20230504T211008637996
DOI: doi:10.15485/1671826

Soil bulk density and texture data collected during field survey associated
with NEON AOP survey, East River, CO 2018. Discrete soil-core sampling
campaign. Volumetric water content ("water content %vol") was measured on the
surface (2.5-7.5 cm) samples only; subsurface (50-55 cm) samples have no
water-content measurement and are therefore dropped from the harmonized output.

This module follows the modular expert-code pattern (common.py + dataset_NN.py)
and exposes a harmonize(ctx) -> DatasetResult function. A standalone runner is
included at the bottom so it can be executed directly inside the fold
workspace.
"""

from __future__ import annotations

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
    """Harmonize dataset 26."""
    idx = 26
    __locations = []

    f26 = as_list(ctx.map_json[idx]["data_payload_files"])[0]

    ddf26 = ctx.read_ds_csv(idx, f26)

    x = ddf26.copy()

    # Collection date is a campaign date (e.g. "6/14/18"); East River, CO is
    # Mountain Standard Time (UTC-7, Etc/GMT+7), consistent with the other
    # Colorado East River datasets in this project.
    x["datetime_UTC"] = parse_local_to_utc(x["Collection date"], "%m/%d/%y", "Etc/GMT+7")

    x["site_id"] = x["SampleSiteCode"].astype(str)

    # Depth reported as a range (Top/Bottom sample depth, cm); approximate as
    # the midpoint and convert cm -> m. This range-derived depth is flagged d1.
    top = pd.to_numeric(x["Top sample depth_cm"], errors="coerce")
    bottom = pd.to_numeric(x["Bottom sample depth_cm"], errors="coerce")
    x["depth_m"] = ((top + bottom) / 2.0) / 100.0

    x["is_timeseries"] = False
    x["water_potential_kPa"] = np.nan
    x["gravimetric_water_content_gH2O_gs"] = np.nan

    # "water content %vol" is volumetric water content in percent -> m3/m3.
    x["volumetric_water_content_m3_m3"] = (
        pd.to_numeric(x["water content %vol"], errors="coerce") / 100.0
    )

    # Keep only rows with a measured volumetric water content (surface samples);
    # subsurface samples carry no moisture measurement.
    x = x[x["volumetric_water_content_m3_m3"].notna()].copy()

    # Replicate: number repeated measurements within the same
    # site_id + depth_m + collection date (a/b duplicates exist for a few
    # subsurface sites; surface samples are single, hence replicate 1).
    x = x.sort_values(["site_id", "depth_m", "datetime_UTC", "SampleID"])
    x["replicate"] = (
        x.groupby(["site_id", "depth_m", "datetime_UTC"]).cumcount() + 1
    )

    __harmonized = ensure_harmonized_cols(x)

    # ------------------------------------------------------------------
    # Location: no per-site coordinates are available in the data payload,
    # any package ancillary file, or the cached ESS-DIVE metadata (only a
    # watershed-level bounding box is given). Coordinates are therefore
    # unresolvable -> emit every site_id with empty lat/lon and qc_flag g2.
    # ------------------------------------------------------------------
    loc26 = pd.DataFrame({"site_id": sorted(x["site_id"].unique())})
    loc26["latitude"] = np.nan
    loc26["longitude"] = np.nan
    loc26["source_dataset_id"] = ctx.dsid(idx)
    loc26 = add_loc_qc(loc26)
    __locations.append(loc26)

    return DatasetResult(
        dataset_id=ctx.dsid(idx),
        harmonized_data=__harmonized,
        location_data=pd.concat(__locations, ignore_index=True) if __locations else pd.DataFrame(),
    )


if __name__ == "__main__":
    import json
    from pathlib import Path
    from dataclasses import dataclass

    OUT_DIR = Path("output")
    BASE_DIR = Path("inputs/raw")
    MAP_ENTRY_PATH = OUT_DIR / "sm_data_harmonization_mapping_entry.json"

    @dataclass
    class FoldContext:
        """Minimal Context for standalone fold execution.

        map_json is keyed by the dataset's canonical index (from MANIFEST.json),
        not by list position. Reads raw package files directly from
        inputs/raw/<dataset_identifier>/.
        """

        map_json: dict
        base_dir: Path = BASE_DIR

        def dsid(self, idx: int) -> str:
            return self.map_json[idx]["dataset_identifier"]

        def ds_path(self, idx: int) -> Path:
            return self.base_dir / self.dsid(idx)

        def read_ds_csv(self, idx: int, filename: str, encoding="utf-8", **kwargs) -> pd.DataFrame:
            return pd.read_csv(self.ds_path(idx) / filename, encoding=encoding, **kwargs)

    with open(MAP_ENTRY_PATH, "r", encoding="utf-8") as fh:
        entry = json.load(fh)
    map_json = {entry["index"]: entry}

    ctx = FoldContext(map_json=map_json)
    result = harmonize(ctx)

    dsid = result.dataset_id
    harmonized = result.harmonized_data.sort_values(
        by=["datetime_UTC", "site_id", "depth_m", "replicate"]
    )
    harmonized.to_csv(OUT_DIR / f"{dsid}_harmonized.csv", index=False)
    result.location_data.to_csv(OUT_DIR / f"{dsid}_location.csv", index=False)

    print(f"Wrote {dsid}_harmonized.csv ({len(harmonized)} rows)")
    print(f"Wrote {dsid}_location.csv ({len(result.location_data)} rows)")
