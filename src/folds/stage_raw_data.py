"""Stage raw ESS-DIVE soil-moisture datasets to ``~/ess-dive_wfsfa_soil_datasets/``.

The evaluation harness expects each dataset's raw files at:

    ``~/ess-dive_wfsfa_soil_datasets/<dataset_identifier>/``

with REF idx 0 (the East Taylor point-location lookup) placed under a ``data/``
sub-directory to match the harmonizer's hard-coded read path.

There are two sources:

1. **Google Drive** — 19 dataset folders shared via Drive, listed in
   ``data/raw_cache/ess-dive_wfsfa_soil_dataset_urls.csv``.  The CSV has no
   header and no index column; the folder order does NOT correspond to the
   dataset index order, so each folder is matched to its dataset entry by
   comparing the folder's file listing against each mapping entry's
   ``data_payload_files``.  Fetched with ``rclone copy`` using the remote
   ``gdrive-bbop`` (must be configured in advance via ``rclone config``).

2. **ESS-DIVE** — REF idx 0 (``doi:10.15485/1660962``, East Taylor) is not on
   Drive.  It is downloaded directly from the ESS-DIVE file API and its single
   CSV placed under a ``data/`` sub-directory so that the harmonizer's path
   (``data/East_Taylor_Watershed_…csv``) resolves correctly.

CLI usage::

    python -m src.folds.stage_raw_data
    python -m src.folds.stage_raw_data --dest ~/my_datasets --dry-run
    python -m src.folds.stage_raw_data --indices 0,1,2   # subset
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import requests
import typer

DEFAULT_MAPPING = Path("data/gold/sm_data_harmonization_mapping.json")
DEFAULT_DRIVE_URLS = Path("data/raw_cache/ess-dive_wfsfa_soil_dataset_urls.csv")
DEFAULT_DEST = Path.home() / "ess-dive_wfsfa_soil_datasets"

RCLONE_REMOTE = "gdrive-bbop"
ESSDIVE_FILES_API = "https://data.ess-dive.lbl.gov/catalog/api/packages"

REF_IDX = 0


def _load_mapping(mapping_path: Path) -> list[dict]:
    return json.loads(mapping_path.read_text())


def _load_drive_urls(urls_path: Path) -> list[str]:
    """Return one Drive folder URL per line (skip blank lines)."""
    lines = urls_path.read_text().splitlines()
    return [ln.strip() for ln in lines if ln.strip()]


def _folder_id_from_url(url: str) -> str:
    """Extract the Google Drive folder ID from a sharing URL.

    >>> _folder_id_from_url("https://drive.google.com/drive/folders/1PdhJng9xqg2sfxfutlXM1R8CdD9U08mm")
    '1PdhJng9xqg2sfxfutlXM1R8CdD9U08mm'
    """
    m = re.search(r"/folders/([A-Za-z0-9_-]+)", url)
    if not m:
        raise ValueError(f"cannot parse folder ID from URL: {url!r}")
    return m.group(1)


def _list_drive_folder(folder_id: str, remote: str = RCLONE_REMOTE, dry_run: bool = False) -> list[str]:
    """Return filenames in a Drive folder via ``rclone ls``."""
    if dry_run:
        return []
    remote_path = f"{remote}:{folder_id}"
    result = subprocess.run(
        ["rclone", "ls", remote_path],
        capture_output=True, text=True, check=True,
    )
    files = []
    for line in result.stdout.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2:
            files.append(parts[1])
    return files


def _match_folder_to_entry(
    folder_files: list[str],
    mapping: list[dict],
    already_matched: set[int],
) -> Optional[dict]:
    """Return the mapping entry whose ``data_payload_files`` best matches the folder.

    Matching is by set intersection: the entry with the most ``data_payload_files``
    found in the folder (and at least one match) wins.  Entries that have no
    ``data_payload_files`` (e.g. REF idx 0) are skipped.  Already-matched
    entries are excluded to prevent double-assignment.
    """
    folder_set = set(folder_files)
    best_entry: Optional[dict] = None
    best_count = 0
    for entry in mapping:
        if entry.get("index") in already_matched:
            continue
        payload = entry.get("data_payload_files")
        if not payload:
            continue
        matches = sum(1 for f in payload if f in folder_set)
        if matches > best_count:
            best_count = matches
            best_entry = entry
    return best_entry if best_count > 0 else None


def _copy_drive_folder(
    folder_id: str,
    dest_dir: Path,
    remote: str = RCLONE_REMOTE,
    dry_run: bool = False,
) -> None:
    """Copy a Drive folder into ``dest_dir`` using rclone."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    remote_path = f"{remote}:{folder_id}"
    cmd = ["rclone", "copy", remote_path, str(dest_dir), "--progress"]
    if dry_run:
        typer.echo(f"  [dry-run] rclone copy {remote_path} {dest_dir}")
        return
    subprocess.run(cmd, check=True)


def _essdive_package_id(dataset_identifier: str) -> str:
    """Convert a dataset_identifier to an ESS-DIVE package ID.

    ESS-DIVE uses the ``dataset_identifier`` directly as the package ID in
    their catalog API.
    """
    return dataset_identifier


def _download_essdive_files(
    dataset_identifier: str,
    doi: str,
    dest_dir: Path,
    location_metadata_files: Optional[list[str]],
    dry_run: bool = False,
) -> None:
    """Download files for REF idx 0 from the ESS-DIVE file API.

    The harmonizer reads the point-location CSV at
    ``data/East_Taylor_…csv`` relative to the dataset root, so files are
    placed under a ``data/`` sub-directory of ``dest_dir``.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    data_subdir = dest_dir / "data"
    data_subdir.mkdir(parents=True, exist_ok=True)

    pkg_id = _essdive_package_id(dataset_identifier)
    files_url = f"{ESSDIVE_FILES_API}/{pkg_id}/files"

    if dry_run:
        typer.echo(f"  [dry-run] GET {files_url}")
        typer.echo(f"  [dry-run] would download files to {data_subdir}")
        return

    resp = requests.get(files_url, timeout=60)
    if resp.status_code == 404:
        typer.echo(f"  ESS-DIVE API returned 404 for {pkg_id}; trying DOI fallback download…")
        _download_essdive_doi_fallback(doi, dest_dir, location_metadata_files, dry_run=False)
        return
    resp.raise_for_status()
    file_list = resp.json()

    wanted = set(location_metadata_files) if location_metadata_files else None
    for file_info in file_list:
        name = file_info.get("name", "")
        if wanted is not None:
            basename = Path(name).name
            if not any(Path(w).name == basename for w in wanted):
                continue
        download_url = file_info.get("url") or file_info.get("downloadUrl")
        if not download_url:
            continue
        out_path = data_subdir / Path(name).name
        typer.echo(f"  downloading {name} → {out_path}")
        with requests.get(download_url, stream=True, timeout=120) as r:
            r.raise_for_status()
            out_path.write_bytes(r.content)


def _download_essdive_doi_fallback(
    doi: str,
    dest_dir: Path,
    location_metadata_files: Optional[list[str]],
    dry_run: bool = False,
) -> None:
    """Fallback: fetch ESS-DIVE package via DOI redirect, then download files."""
    data_subdir = dest_dir / "data"
    data_subdir.mkdir(parents=True, exist_ok=True)

    doi_id = doi.replace("doi:", "")
    doi_url = f"https://doi.org/{doi_id}"
    if dry_run:
        typer.echo(f"  [dry-run] would resolve DOI {doi_url} and download files to {data_subdir}")
        return

    resp = requests.get(doi_url, allow_redirects=True, timeout=60)
    resp.raise_for_status()
    pkg_url = resp.url
    pkg_id = pkg_url.rstrip("/").split("/")[-1]
    files_url = f"{ESSDIVE_FILES_API}/{pkg_id}/files"
    fresp = requests.get(files_url, timeout=60)
    fresp.raise_for_status()
    file_list = fresp.json()

    wanted = set(location_metadata_files) if location_metadata_files else None
    for file_info in file_list:
        name = file_info.get("name", "")
        if wanted is not None:
            basename = Path(name).name
            if not any(Path(w).name == basename for w in wanted):
                continue
        download_url = file_info.get("url") or file_info.get("downloadUrl")
        if not download_url:
            continue
        out_path = data_subdir / Path(name).name
        typer.echo(f"  downloading {name} → {out_path}")
        with requests.get(download_url, stream=True, timeout=120) as r:
            r.raise_for_status()
            out_path.write_bytes(r.content)


def stage_dataset(
    entry: dict,
    dest_root: Path,
    drive_urls: list[str],
    remote: str = RCLONE_REMOTE,
    dry_run: bool = False,
    verbose: bool = True,
) -> Path:
    """Stage one dataset entry to ``dest_root/<dataset_identifier>/``.

    For Drive-sourced datasets the folder is identified by matching
    ``data_payload_files`` against each Drive folder's file listing.
    For REF idx 0 (no Drive copy) the files are fetched from ESS-DIVE.
    Returns the destination directory.
    """
    dsid = entry["dataset_identifier"]
    idx = entry["index"]
    dest_dir = dest_root / dsid

    if verbose:
        typer.echo(f"[{idx}] {dsid}")

    if idx == REF_IDX:
        if verbose:
            typer.echo("  → ESS-DIVE direct download (REF idx 0)")
        _download_essdive_files(
            dsid,
            entry.get("doi", ""),
            dest_dir,
            entry.get("location_metadata_files"),
            dry_run=dry_run,
        )
        return dest_dir

    payload = entry.get("data_payload_files")
    if not payload:
        if verbose:
            typer.echo("  → no data_payload_files, skipping")
        return dest_dir

    matched_folder_id: Optional[str] = None
    already_matched: set[int] = set()

    for url in drive_urls:
        folder_id = _folder_id_from_url(url)
        try:
            folder_files = _list_drive_folder(folder_id, remote=remote, dry_run=dry_run)
        except subprocess.CalledProcessError as exc:
            typer.echo(f"  WARNING: rclone ls failed for {url}: {exc}", err=True)
            continue
        if dry_run:
            if verbose:
                typer.echo(f"  [dry-run] would match against folder {folder_id}")
            matched_folder_id = folder_id
            break
        match = _match_folder_to_entry(folder_files, [entry], already_matched)
        if match is not None:
            matched_folder_id = folder_id
            break

    if matched_folder_id is None:
        typer.echo(f"  WARNING: no Drive folder matched idx {idx} ({dsid})", err=True)
        return dest_dir

    if verbose:
        typer.echo(f"  → rclone copy from folder {matched_folder_id}")
    _copy_drive_folder(matched_folder_id, dest_dir, remote=remote, dry_run=dry_run)
    return dest_dir


def match_all_drive_folders(
    drive_urls: list[str],
    mapping: list[dict],
    remote: str = RCLONE_REMOTE,
    dry_run: bool = False,
    verbose: bool = True,
) -> dict[int, str]:
    """Match each Drive folder to its dataset entry by file-set intersection.

    Lists every folder once and greedily assigns each to the best-matching
    entry.  Returns ``{dataset_index: folder_id}``.
    """
    folder_contents: dict[str, list[str]] = {}
    for url in drive_urls:
        folder_id = _folder_id_from_url(url)
        if dry_run:
            folder_contents[folder_id] = []
            continue
        try:
            files = _list_drive_folder(folder_id, remote=remote)
        except subprocess.CalledProcessError as exc:
            typer.echo(f"WARNING: rclone ls failed for {url}: {exc}", err=True)
            folder_contents[folder_id] = []
        else:
            folder_contents[folder_id] = files

    assignment: dict[int, str] = {}
    already_matched: set[int] = set()

    for folder_id, files in folder_contents.items():
        entry = _match_folder_to_entry(files, mapping, already_matched)
        if entry is not None:
            assignment[entry["index"]] = folder_id
            already_matched.add(entry["index"])
        elif not dry_run and verbose:
            typer.echo(f"WARNING: no mapping entry matched folder {folder_id}", err=True)

    return assignment


def stage_all(
    mapping: list[dict],
    drive_urls: list[str],
    dest_root: Path,
    indices: Optional[set[int]] = None,
    remote: str = RCLONE_REMOTE,
    dry_run: bool = False,
    verbose: bool = True,
) -> list[Path]:
    """Stage all (or selected) datasets to ``dest_root``.

    First builds the Drive folder→entry mapping in one pass (to avoid listing
    each folder multiple times), then copies each matched folder.
    REF idx 0 is downloaded from ESS-DIVE regardless.

    Returns list of staged destination directories.
    """
    if verbose:
        typer.echo(f"Staging to {dest_root}" + (" [DRY RUN]" if dry_run else ""))

    entries = [e for e in mapping if indices is None or e["index"] in indices]

    ref_entries = [e for e in entries if e["index"] == REF_IDX]
    drive_entries = [e for e in entries if e["index"] != REF_IDX and e.get("data_payload_files")]

    staged: list[Path] = []

    for entry in ref_entries:
        path = stage_dataset(entry, dest_root, drive_urls=[], remote=remote, dry_run=dry_run, verbose=verbose)
        staged.append(path)

    if drive_entries:
        if verbose:
            typer.echo(f"\nBuilding Drive folder→dataset mapping for {len(drive_urls)} folders…")
        folder_map = match_all_drive_folders(drive_urls, drive_entries, remote=remote, dry_run=dry_run, verbose=verbose)

        for entry in drive_entries:
            idx = entry["index"]
            dsid = entry["dataset_identifier"]
            dest_dir = dest_root / dsid
            if verbose:
                typer.echo(f"[{idx}] {dsid}")
            folder_id = folder_map.get(idx)
            if folder_id is None:
                typer.echo(f"  WARNING: no Drive folder matched idx {idx}", err=True)
                continue
            if verbose:
                typer.echo(f"  → rclone copy from folder {folder_id}")
            _copy_drive_folder(folder_id, dest_dir, remote=remote, dry_run=dry_run)
            staged.append(dest_dir)

    return staged


app = typer.Typer(add_completion=False, help="Stage raw ESS-DIVE datasets to ~/ess-dive_wfsfa_soil_datasets/.")


@app.command()
def main(
    dest: Path = typer.Option(DEFAULT_DEST, "--dest", help="Root directory for staged datasets."),
    mapping: Path = typer.Option(DEFAULT_MAPPING, "--mapping", help="Gold mapping JSON."),
    drive_urls: Path = typer.Option(DEFAULT_DRIVE_URLS, "--drive-urls", help="File with one Drive folder URL per line."),
    remote: str = typer.Option(RCLONE_REMOTE, "--remote", help="rclone remote name for Google Drive."),
    indices: Optional[str] = typer.Option(None, "--indices", help="Comma-separated dataset indices to stage (default: all)."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print actions without executing rclone or downloading."),
    quiet: bool = typer.Option(False, "--quiet", help="Suppress per-dataset progress messages."),
) -> None:
    """Stage raw soil-moisture datasets to DEST/<dataset_identifier>/.

    Matches Google Drive folders to datasets by file-set content, then copies
    via rclone. REF idx 0 is fetched directly from ESS-DIVE.

    Prerequisites:
    - rclone must be installed and the remote configured: ``rclone config``
    - The remote name defaults to ``gdrive-bbop``; override with ``--remote``
    """
    mapping_data = _load_mapping(mapping)
    url_list = _load_drive_urls(drive_urls)

    idx_filter: Optional[set[int]] = None
    if indices is not None:
        idx_filter = {int(i.strip()) for i in indices.split(",") if i.strip()}

    staged = stage_all(
        mapping_data,
        url_list,
        dest_root=dest,
        indices=idx_filter,
        remote=remote,
        dry_run=dry_run,
        verbose=not quiet,
    )

    typer.echo(f"\nDone. Staged {len(staged)} dataset(s) to {dest}")


if __name__ == "__main__":
    app()
