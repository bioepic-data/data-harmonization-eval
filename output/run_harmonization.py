"""
Fold runner for target dataset index 16.

Wires the shared expert library (data/gold/expert_code/common.py) to the
staged raw inputs under inputs/raw/<dataset_identifier>/ and executes the
dataset_16 harmonizer. Writes the harmonized CSV and location table to output/.
"""

from __future__ import annotations

import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
EXPERT_CODE = WORKSPACE / "data" / "gold" / "expert_code"
MAPPING_JSON = WORKSPACE / "output" / "sm_data_harmonization_mapping.json"
BASE_DIR = WORKSPACE / "inputs" / "raw"
OUT_DIR = WORKSPACE / "output"

# Make common.py and dataset_16.py importable.
sys.path.insert(0, str(OUT_DIR))
sys.path.insert(0, str(EXPERT_CODE))

from common import Context, harmonize_locations, write_outputs  # noqa: E402
import dataset_16  # noqa: E402


def main():
    ctx = Context.load(mapping_path=MAPPING_JSON, base_dir=BASE_DIR)
    # The mapping file holds only the target entry; the expert helpers address
    # entries positionally by canonical index, so place it at position 16.
    by_index = {e["index"]: e for e in ctx.map_json}
    max_idx = max(by_index)
    ctx.map_json = [by_index.get(i, {}) for i in range(max_idx + 1)]

    result = dataset_16.harmonize(ctx)
    loc_df = harmonize_locations([result.location_data])
    write_outputs([result], loc_df, OUT_DIR)

    df = result.harmonized_data
    print("\n=== Harmonized summary ===")
    print("rows:", len(df))
    print("sites:", sorted(df["site_id"].unique().tolist()))
    print("depths (m):", sorted(df["depth_m"].dropna().unique().tolist()))
    print("VWC non-null:", int(df["volumetric_water_content_m3_m3"].notna().sum()))
    print("WP  non-null:", int(df["water_potential_kPa"].notna().sum()))
    print("datetime range:", df["datetime_UTC"].min(), "->", df["datetime_UTC"].max())


if __name__ == "__main__":
    main()
