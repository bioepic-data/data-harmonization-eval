"""Fold runner for target dataset index 27.

Loads the common helper library from the expert package, builds a Context that
resolves the canonical dataset index against the fold mapping JSON, points the
base directory at the staged raw inputs, and writes harmonized outputs under
output/.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
EXPERT_CODE = WORKSPACE / "data" / "gold" / "expert_code"
OUT_DIR = WORKSPACE / "output"
BASE_DIR = WORKSPACE / "inputs" / "raw"
MAP_JSON_PATH = OUT_DIR / "sm_data_harmonization_mapping.json"

sys.path.insert(0, str(EXPERT_CODE))
sys.path.insert(0, str(OUT_DIR))

from common import Context, write_outputs, harmonize_locations  # noqa: E402
import dataset_27  # noqa: E402


def main():
    with open(MAP_JSON_PATH, "r", encoding="utf-8") as f:
        entries = json.load(f)
    map_by_index = {e["index"]: e for e in entries}

    ctx = Context(map_json=map_by_index, base_dir=BASE_DIR, out_dir=OUT_DIR)

    result = dataset_27.harmonize(ctx)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_csv = OUT_DIR / f"{result.dataset_id}_harmonized.csv"
    df = result.harmonized_data.sort_values(
        by=["datetime_UTC", "site_id", "depth_m", "replicate"]
    )
    df.to_csv(out_csv, index=False)
    print(f"Wrote {out_csv.name}: {len(df)} rows")

    loc = result.location_data.copy()
    loc.to_csv(OUT_DIR / f"{result.dataset_id}_location.csv", index=False)
    print(f"Wrote {result.dataset_id}_location.csv: {len(loc)} rows")

    print("\nSummary:")
    print(" sites:", sorted(df["site_id"].dropna().unique().tolist()))
    print(" rows with VWC:", df["volumetric_water_content_m3_m3"].notna().sum())
    print(" rows with WP :", df["water_potential_kPa"].notna().sum())
    print(" datetime range:", df["datetime_UTC"].min(), "->", df["datetime_UTC"].max())


if __name__ == "__main__":
    main()
