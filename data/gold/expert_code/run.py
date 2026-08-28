"""
Main orchestrator for soil moisture data harmonization.

Runs all dataset harmonizers, performs cross-dataset location deduplication,
and writes outputs.

Supports holdout for leave-one-cluster-out cross-validation.

Usage:
    python run.py                           # Run all datasets
    python run.py --holdout 5,10            # Hold out datasets 5 and 10
    python run.py --no-write                # Smoke test without writing
    python run.py --out-dir /custom/path    # Custom output directory
"""

import sys
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from common import (
    Context,
    harmonize_locations,
    write_outputs,
    DEFAULT_BASE_DIR,
    DEFAULT_OUT_DIR,
    DEFAULT_MAPPING_JSON
)
from inclusions import DATASET_INDICES, DATASETS


def run(holdout=None, base_dir=None, out_dir=None, mapping=None, write=True):
    """
    Run harmonization with optional holdout.

    Args:
        holdout: Set of dataset indices to hold out (for cross-validation)
        base_dir: Path to input data directory
        out_dir: Path to output directory
        mapping: Path to mapping JSON file
        write: Whether to write outputs (False for smoke testing)

    Returns:
        tuple: (results, loc_df) - list of DatasetResults and location DataFrame
    """
    # Use defaults if not specified
    base_dir = Path(base_dir or DEFAULT_BASE_DIR)
    out_dir = Path(out_dir or DEFAULT_OUT_DIR)
    mapping = Path(mapping or DEFAULT_MAPPING_JSON)
    holdout = set(holdout or [])

    # Validate holdout indices
    invalid = holdout - set(DATASET_INDICES)
    if invalid:
        raise ValueError(
            f"Invalid holdout indices: {invalid}. "
            f"Valid indices are: {sorted(DATASET_INDICES)}"
        )

    # Load context
    print(f"Loading mapping from: {mapping}")
    print(f"Reading input data from: {base_dir}")
    ctx = Context.load(mapping, base_dir)

    # Run non-held-out datasets
    active_indices = [idx for idx in DATASET_INDICES if idx not in holdout]
    print(f"\nRunning {len(active_indices)} datasets (holding out {len(holdout)})")

    if holdout:
        print(f"Held out: {sorted(holdout)}")

    results = []
    for idx in active_indices:
        print(f"  Processing dataset {idx:02d} ({ctx.dsid(idx)})...")
        try:
            result = DATASETS[idx](ctx)
            results.append(result)
            print(f"    → {len(result.harmonized_data)} rows, {len(result.location_data)} locations")
        except Exception as e:
            print(f"    ERROR: {e}")
            raise

    # Cross-dataset location deduplication
    print(f"\nPerforming cross-dataset location deduplication...")
    loc_data_list = [r.location_data for r in results]
    loc_df = harmonize_locations(loc_data_list)

    # Write outputs
    if write:
        print(f"\nWriting outputs to: {out_dir}")
        write_outputs(results, loc_df, out_dir)
    else:
        print("\n--no-write specified, skipping output")

    print("\n✓ Harmonization complete")
    return results, loc_df


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Harmonize ESS-DIVE soil moisture datasets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py                          # Run all datasets
  python run.py --holdout 5,10           # Hold out datasets 5 and 10
  python run.py --no-write               # Smoke test without writing
  python run.py --out-dir /custom/path   # Custom output directory
        """
    )

    parser.add_argument(
        "--holdout",
        help="Comma-separated dataset indices to hold out (e.g., '5,10')"
    )
    parser.add_argument(
        "--base-dir",
        help=f"Input data directory (default: {DEFAULT_BASE_DIR})"
    )
    parser.add_argument(
        "--out-dir",
        help=f"Output directory (default: {DEFAULT_OUT_DIR})"
    )
    parser.add_argument(
        "--mapping",
        help=f"Mapping JSON path (default: {DEFAULT_MAPPING_JSON})"
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Don't write outputs (for smoke testing)"
    )

    args = parser.parse_args()

    # Parse holdout indices
    holdout = []
    if args.holdout:
        try:
            holdout = [int(x.strip()) for x in args.holdout.split(",")]
        except ValueError:
            print(f"ERROR: Invalid holdout format: '{args.holdout}'")
            print("Expected comma-separated integers (e.g., '5,10')")
            sys.exit(1)

    # Run harmonization
    try:
        run(
            holdout=holdout,
            base_dir=args.base_dir,
            out_dir=args.out_dir,
            mapping=args.mapping,
            write=not args.no_write
        )
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
