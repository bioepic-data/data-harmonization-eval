"""Cache ESS-DIVE package metadata for the WFSFA soil-moisture datasets.

The raw payload files staged by :mod:`src.folds.stage_raw_data` are the data a
dataset publishes; they frequently omit things the published *package record*
carries — most importantly spatial coverage. Agents have repeatedly reached for
``data/external/ess-dive_meta/`` and found nothing there, then recorded
coordinates as unresolvable.

This module fetches the package record for each dataset from the ESS-DIVE
packages API and caches one JSON document per dataset at::

    data/raw_cache/ess-dive_wfsfa_soil_metadata/<dataset_identifier>.json

The cache holds **every** dataset. Ablation happens at environment-build time:
:func:`src.folds.build_env.build_env` copies only the fold's target metadata
into the run environment, so a fold never sees another dataset's record. Keep
that split — a cache that is already ablated cannot serve a second fold, and an
environment that is not ablated leaks.

CLI usage::

    python -m src.folds.stage_metadata                 # all included datasets
    python -m src.folds.stage_metadata --indices 23    # one dataset
    python -m src.folds.stage_metadata --dry-run
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import requests
import typer

from src.folds.stage_raw_data import (
    ESSDIVE_PACKAGES_API,
    _essdive_package_id,
)

DEFAULT_MAPPING = Path("data/gold/sm_data_harmonization_mapping.json")
DEFAULT_METADATA_CACHE = Path("data/raw_cache/ess-dive_wfsfa_soil_metadata")


def metadata_filename(dataset_identifier: str) -> str:
    """Cache filename for a dataset's package record."""
    return f"{dataset_identifier}.json"


def fetch_package_metadata(
    dataset_identifier: str,
    doi: Optional[str],
    session: Optional[requests.Session] = None,
) -> dict:
    """Return the ESS-DIVE package record for one dataset.

    Tries the DOI-addressed endpoint first, then the identifier-addressed one,
    mirroring the fallback order in ``stage_raw_data._download_essdive_files``.
    """
    sess = session or requests.Session()
    urls: list[str] = []
    if doi:
        urls.append(f"{ESSDIVE_PACKAGES_API}/{doi if doi.startswith('doi:') else 'doi:' + doi}")
    urls.append(f"{ESSDIVE_PACKAGES_API}/{_essdive_package_id(dataset_identifier)}")

    last_error: Optional[Exception] = None
    for url in urls:
        try:
            resp = sess.get(url, timeout=120)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # noqa: BLE001 - try the next addressing scheme
            last_error = exc
    raise RuntimeError(
        f"could not fetch ESS-DIVE package metadata for {dataset_identifier}: {last_error}"
    )


def stage_metadata(
    indices: Optional[set[int]] = None,
    mapping_path: Path = DEFAULT_MAPPING,
    dest_dir: Path = DEFAULT_METADATA_CACHE,
    dry_run: bool = False,
) -> list[Path]:
    """Cache package metadata for the selected datasets. Returns written paths.

    Datasets the mapping excludes are skipped; a fetch failure for one dataset
    is reported and does not abort the rest, so a single retired DOI cannot
    block staging the other eighteen.
    """
    mapping = json.loads(Path(mapping_path).read_text())
    dest_dir = Path(dest_dir)
    written: list[Path] = []
    session = requests.Session()

    for entry in mapping:
        idx = entry.get("index")
        if indices is not None and idx not in indices:
            continue
        if entry.get("inclusion_decision") != "include":
            continue
        dsid = entry.get("dataset_identifier")
        if not dsid:
            continue
        out_path = dest_dir / metadata_filename(dsid)
        if dry_run:
            typer.echo(f"  [dry-run] fetch package metadata for idx {idx} → {out_path}")
            continue
        try:
            record = fetch_package_metadata(dsid, entry.get("doi"), session=session)
        except Exception as exc:  # noqa: BLE001 - report and continue
            typer.echo(f"  WARNING: idx {idx} ({dsid}): {exc}")
            continue
        dest_dir.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(record, indent=2) + "\n")
        typer.echo(f"  idx {idx}: {out_path} ({out_path.stat().st_size} bytes)")
        written.append(out_path)

    return written


app = typer.Typer(add_completion=False, help="Cache ESS-DIVE package metadata.")


@app.command()
def main(
    indices: Optional[str] = typer.Option(None, "--indices", help="Comma-separated dataset indices (default: all included)."),
    mapping: Path = typer.Option(DEFAULT_MAPPING, "--mapping", help="Gold mapping JSON."),
    dest: Path = typer.Option(DEFAULT_METADATA_CACHE, "--dest", help="Metadata cache directory."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be fetched."),
) -> None:
    """Fetch and cache ESS-DIVE package metadata."""
    idx_set = {int(i) for i in indices.split(",") if i.strip()} if indices else None
    written = stage_metadata(indices=idx_set, mapping_path=mapping, dest_dir=dest, dry_run=dry_run)
    typer.echo(f"cached {len(written)} package metadata record(s) in {dest}")


if __name__ == "__main__":
    app()
