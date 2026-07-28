"""Run the expert harmonization over a chosen set of datasets.

This is the modular replacement for running the monolith. Because each dataset
is an independent module that only *returns* its harmonized + location frames
(no shared-global accumulators), holding a cluster out is just::

    python run.py --holdout 1,2,3,6,16,27

No cell-splicing needed: the held-out modules are simply not run, and the rest
stay runnable (the only cross-block dependency is the reference dataset 0, which
is never a hold-out target).

Run from anywhere; the script puts its own directory on ``sys.path`` so the
sibling modules (``common``, ``datasets``, ``dataset_NN``) import cleanly.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import Context, harmonize_locations, write_outputs  # noqa: E402
from datasets import DATASET_INDICES, DATASETS  # noqa: E402


def run(
    holdout: set[int] | None = None,
    base_dir: Path | None = None,
    out_dir: Path | None = None,
    mapping_path: Path | None = None,
    write: bool = True,
):
    """Harmonize every dataset except those in ``holdout``.

    Returns ``(harmonized_ids, harmonized_data, loc_data)``. Mirrors the
    monolith's end-to-end behavior: per-dataset frames are accumulated in
    order, the location dedup/QA pass runs, and (when ``write``) the per-dataset
    and concatenated-location CSVs are written.
    """
    holdout = set(holdout or set())
    unknown = sorted(holdout - set(DATASET_INDICES))
    if unknown:
        raise ValueError(
            f"hold-out index/indices {unknown} have no dataset module; "
            f"available datasets: {DATASET_INDICES}"
        )

    ctx = Context.load(base_dir=base_dir, out_dir=out_dir, mapping_path=mapping_path)

    results = [DATASETS[idx](ctx) for idx in DATASET_INDICES if idx not in holdout]
    harmonized_ids = [r.dataset_id for r in results]
    harmonized_data = [r.harmonized for r in results]
    loc_data = [loc for r in results for loc in r.locations]

    # Dedup/QA pass (as in the expert script, its frame is reported, not written).
    harmonize_locations(loc_data)

    if write:
        write_outputs(ctx.out_dir, harmonized_ids, harmonized_data, loc_data)

    return harmonized_ids, harmonized_data, loc_data


def _parse_holdout(raw: str) -> set[int]:
    return {int(tok) for tok in raw.split(",") if tok.strip()}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--holdout",
        default="",
        help="Comma-separated dataset indices to leave out (e.g. '1,2,3,6,16,27').",
    )
    parser.add_argument("--base-dir", type=Path, default=None, help="Override raw dataset base dir.")
    parser.add_argument("--out-dir", type=Path, default=None, help="Override output dir.")
    parser.add_argument("--mapping", type=Path, default=None, help="Override mapping JSON path.")
    parser.add_argument(
        "--no-write", action="store_true", help="Run without writing CSVs (smoke test)."
    )
    args = parser.parse_args(argv)

    holdout = _parse_holdout(args.holdout)
    ids, _, _ = run(
        holdout=holdout,
        base_dir=args.base_dir,
        out_dir=args.out_dir,
        mapping_path=args.mapping,
        write=not args.no_write,
    )
    kept = [i for i in DATASET_INDICES if i not in holdout]
    print(f"harmonized {len(ids)} datasets (kept indices {kept}); held out {sorted(holdout)}")


if __name__ == "__main__":
    main()
