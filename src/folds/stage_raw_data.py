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
   ``data_payload_files``.  By default, the tool first tries ``rclone`` using
   the remote ``gdrive-bbop``.  If that remote is not configured, it falls back
   to public Google Drive folder listings and direct file downloads for the
   files declared in the mapping JSON.

2. **ESS-DIVE** — REF idx 0 (``doi:10.15485/1660962``, East Taylor) is
   downloaded from the current ESS-DIVE package API and its single CSV placed
   under a ``data/`` sub-directory so that the harmonizer's path
   (``data/East_Taylor_Watershed_...csv``) resolves correctly.

CLI usage::

    python -m src.folds.stage_raw_data
    python -m src.folds.stage_raw_data --dest ~/my_datasets --dry-run
    python -m src.folds.stage_raw_data --indices 0,1,2   # subset
"""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Literal, Optional
from urllib.parse import quote, unquote, urlencode

import requests
import typer

DEFAULT_MAPPING = Path("data/gold/sm_data_harmonization_mapping.json")
DEFAULT_DRIVE_URLS = Path("data/raw_cache/ess-dive_wfsfa_soil_dataset_urls.csv")
DEFAULT_DEST = Path.home() / "ess-dive_wfsfa_soil_datasets"

RCLONE_REMOTE = "gdrive-bbop"
ESSDIVE_PACKAGES_API = "https://api.ess-dive.lbl.gov/packages"
ESSDIVE_LEGACY_FILES_API = "https://data.ess-dive.lbl.gov/catalog/api/packages"
GOOGLE_DRIVE_EMBEDDED_VIEW = "https://drive.google.com/embeddedfolderview"
GOOGLE_DRIVE_DOWNLOAD = "https://drive.usercontent.google.com/download"
GOOGLE_DRIVE_UC_DOWNLOAD = "https://drive.google.com/uc"

REF_IDX = 0
DriveMethod = Literal["auto", "rclone", "public"]


@dataclass(frozen=True)
class DriveFile:
    """A file discovered from a public Google Drive folder listing."""

    file_id: str
    path: str


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


class _DriveFolderHTMLParser(HTMLParser):
    """Extract public Drive files and child folders from embeddedfolderview HTML."""

    def __init__(self) -> None:
        super().__init__()
        self._current_href: Optional[str] = None
        self._current_text: list[str] = []
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        if tag != "a":
            return
        attr_map = dict(attrs)
        href = attr_map.get("href")
        if href:
            self._current_href = href
            self._current_text = []

    def handle_data(self, data: str) -> None:
        if self._current_href is not None:
            self._current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or self._current_href is None:
            return
        text = unquote("".join(self._current_text).strip())
        if text:
            self.links.append((self._current_href, text))
        self._current_href = None
        self._current_text = []


def _sanitize_drive_filename(filename: str) -> str:
    """Return a local-safe filename while preserving normal ESS-DIVE names."""
    cleaned = filename.replace("\x00", "").replace("/", "_").replace("\\", "_").strip()
    return cleaned if cleaned not in {"", ".", ".."} else "_"


def _parse_drive_folder_links(html: str) -> tuple[list[DriveFile], list[tuple[str, str]]]:
    """Parse file and child-folder links from Google Drive embedded folder HTML."""
    parser = _DriveFolderHTMLParser()
    parser.feed(html)
    files: list[DriveFile] = []
    folders: list[tuple[str, str]] = []

    for href, text in parser.links:
        file_match = re.match(
            r"https://drive\.google\.com/file/d/([-\w]{25,})/view",
            href,
        )
        if file_match:
            files.append(DriveFile(file_id=file_match.group(1), path=_sanitize_drive_filename(text)))
            continue

        docs_match = re.match(r"https://docs\.google\.com/\w+/d/([-\w]{25,})/", href)
        if docs_match:
            files.append(DriveFile(file_id=docs_match.group(1), path=_sanitize_drive_filename(text)))
            continue

        folder_match = re.match(r"https://drive\.google\.com/drive/folders/([-\w]{25,})", href)
        if folder_match:
            folders.append((folder_match.group(1), _sanitize_drive_filename(text)))

    return files, folders


def _list_public_drive_folder_entries(
    folder_id: str,
    prefix: str = "",
    session: Optional[requests.Session] = None,
    dry_run: bool = False,
) -> list[DriveFile]:
    """Return recursive file entries for a public Google Drive folder.

    This uses the same anonymous embedded folder listing that browsers can load
    for "Anyone with the link" folders.  It avoids requiring a configured
    rclone Google Drive remote.
    """
    if dry_run:
        return []

    sess = session or requests.Session()
    resp = sess.get(
        GOOGLE_DRIVE_EMBEDDED_VIEW,
        params={"id": folder_id},
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36"
            )
        },
        timeout=60,
    )
    resp.raise_for_status()

    files, folders = _parse_drive_folder_links(resp.text)
    entries = [
        DriveFile(file_id=f.file_id, path=str(Path(prefix) / f.path) if prefix else f.path)
        for f in files
    ]
    for child_id, child_name in folders:
        child_prefix = str(Path(prefix) / child_name) if prefix else child_name
        entries.extend(
            _list_public_drive_folder_entries(
                child_id,
                prefix=child_prefix,
                session=sess,
                dry_run=dry_run,
            )
        )
    return entries


def _list_public_drive_folder(folder_id: str, dry_run: bool = False) -> list[str]:
    """Return recursive filenames from a public Google Drive folder."""
    return [entry.path for entry in _list_public_drive_folder_entries(folder_id, dry_run=dry_run)]


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


def _candidate_payload_paths(path: str) -> set[str]:
    """Return equivalent folder/mapping paths for matching package contents."""
    path = str(Path(path))
    candidates = {path, Path(path).name}
    if path.startswith("data/"):
        candidates.add(path.removeprefix("data/"))
    else:
        candidates.add(f"data/{path}")
    return candidates


def _wanted_entry_files(entry: dict) -> list[str]:
    """Return raw input files that need to exist for one mapping entry."""
    wanted: list[str] = []
    for key in ("data_payload_files", "location_metadata_files", "sensor_metadata_files"):
        value = entry.get(key)
        if isinstance(value, list):
            wanted.extend(str(item) for item in value if item)
    return wanted


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
    for filename in folder_files:
        folder_set.update(_candidate_payload_paths(filename))
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


def _find_drive_file_entry(entries: list[DriveFile], wanted_path: str) -> Optional[DriveFile]:
    """Find the Drive file entry that corresponds to a mapping path."""
    by_path = {entry.path: entry for entry in entries}
    for candidate in _candidate_payload_paths(wanted_path):
        if candidate in by_path:
            return by_path[candidate]

    basename = Path(wanted_path).name
    basename_matches = [entry for entry in entries if Path(entry.path).name == basename]
    if len(basename_matches) == 1:
        return basename_matches[0]
    return None


def _download_public_drive_file(file_id: str, out_path: Path, dry_run: bool = False) -> None:
    """Download one public Google Drive file by ID."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if dry_run:
        typer.echo(f"  [dry-run] download Google Drive file {file_id} → {out_path}")
        return

    urls = [
        f"{GOOGLE_DRIVE_DOWNLOAD}?{urlencode({'id': file_id, 'export': 'download', 'confirm': 't'})}",
        f"{GOOGLE_DRIVE_UC_DOWNLOAD}?{urlencode({'export': 'download', 'id': file_id})}",
    ]
    last_error: Optional[Exception] = None
    for url in urls:
        tmp_path = out_path.with_name(f"{out_path.name}.part")
        try:
            with requests.get(url, stream=True, timeout=120) as resp:
                resp.raise_for_status()
                first_bytes = b""
                with tmp_path.open("wb") as handle:
                    for chunk in resp.iter_content(chunk_size=1024 * 1024):
                        if not chunk:
                            continue
                        if not first_bytes:
                            first_bytes = chunk[:200].lstrip().lower()
                        handle.write(chunk)
            if first_bytes.startswith(b"<!doctype html") or first_bytes.startswith(b"<html"):
                raise RuntimeError("Google Drive returned HTML instead of file content")
            tmp_path.replace(out_path)
            return
        except Exception as exc:  # pragma: no cover - exercised by integration use.
            tmp_path.unlink(missing_ok=True)
            last_error = exc
    raise RuntimeError(f"failed to download Google Drive file {file_id}: {last_error}")


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


def _copy_public_drive_declared_files(
    folder_id: str,
    entry: dict,
    dest_dir: Path,
    dry_run: bool = False,
    verbose: bool = True,
) -> None:
    """Copy only the mapping-declared raw inputs from a public Drive folder."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    folder_entries = _list_public_drive_folder_entries(folder_id, dry_run=dry_run)
    if dry_run:
        for wanted_path in _wanted_entry_files(entry):
            _download_public_drive_file("<matched-file-id>", dest_dir / wanted_path, dry_run=True)
        return

    missing: list[str] = []
    for wanted_path in _wanted_entry_files(entry):
        out_path = dest_dir / wanted_path
        if out_path.exists() and out_path.stat().st_size > 0:
            continue
        drive_file = _find_drive_file_entry(folder_entries, wanted_path)
        if drive_file is None:
            missing.append(wanted_path)
            continue
        if verbose:
            typer.echo(f"  downloading {wanted_path}")
        _download_public_drive_file(drive_file.file_id, out_path, dry_run=dry_run)

    if missing:
        raise RuntimeError(
            f"public Drive folder {folder_id} is missing declared file(s): {', '.join(missing)}"
        )


def _resolve_drive_method(
    drive_method: DriveMethod,
    drive_urls: list[str],
    remote: str = RCLONE_REMOTE,
    dry_run: bool = False,
    verbose: bool = True,
) -> DriveMethod:
    """Choose a Drive access method, using public fallback when rclone is unavailable."""
    if drive_method != "auto" or dry_run or not drive_urls:
        return drive_method

    first_folder_id = _folder_id_from_url(drive_urls[0])
    try:
        _list_drive_folder(first_folder_id, remote=remote)
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        if verbose:
            typer.echo(
                f"WARNING: rclone remote {remote!r} is unavailable ({exc}); "
                "falling back to public Google Drive downloads.",
                err=True,
            )
        return "public"
    return "rclone"


def _list_drive_folder_by_method(
    folder_id: str,
    drive_method: DriveMethod,
    remote: str = RCLONE_REMOTE,
    dry_run: bool = False,
) -> list[str]:
    """List a Drive folder with the selected access method."""
    if drive_method == "public":
        return _list_public_drive_folder(folder_id, dry_run=dry_run)
    return _list_drive_folder(folder_id, remote=remote, dry_run=dry_run)


def _copy_drive_folder_by_method(
    folder_id: str,
    entry: dict,
    dest_dir: Path,
    drive_method: DriveMethod,
    remote: str = RCLONE_REMOTE,
    dry_run: bool = False,
    verbose: bool = True,
) -> None:
    """Copy a Drive folder using rclone or the public declared-file fallback."""
    if drive_method == "public":
        _copy_public_drive_declared_files(
            folder_id,
            entry,
            dest_dir,
            dry_run=dry_run,
            verbose=verbose,
        )
    else:
        _copy_drive_folder(folder_id, dest_dir, remote=remote, dry_run=dry_run)


def _essdive_package_id(dataset_identifier: str) -> str:
    """Convert a dataset_identifier to an ESS-DIVE package ID.

    ESS-DIVE uses the ``dataset_identifier`` directly as the package ID in
    their catalog API.
    """
    return dataset_identifier


def _download_url_to_path(url: str, out_path: Path, dry_run: bool = False) -> None:
    """Stream a URL to a local path."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if dry_run:
        typer.echo(f"  [dry-run] GET {url} → {out_path}")
        return
    with requests.get(url, stream=True, timeout=120) as resp:
        resp.raise_for_status()
        out_path.write_bytes(resp.content)


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

    wanted = set(location_metadata_files) if location_metadata_files else None
    doi_id = doi.replace("doi:", "")
    package_urls = []
    if doi_id:
        package_urls.append(f"{ESSDIVE_PACKAGES_API}/doi:{doi_id}")
    package_urls.append(f"{ESSDIVE_PACKAGES_API}/{_essdive_package_id(dataset_identifier)}")
    package_urls.append(f"{ESSDIVE_LEGACY_FILES_API}/{_essdive_package_id(dataset_identifier)}/files")

    if dry_run:
        for package_url in package_urls:
            typer.echo(f"  [dry-run] GET {package_url}")
        for rel_path in location_metadata_files or []:
            typer.echo(f"  [dry-run] would download {Path(rel_path).name} → {dest_dir / rel_path}")
        return

    last_error: Optional[Exception] = None
    for package_url in package_urls:
        try:
            resp = requests.get(package_url, timeout=60)
            if resp.status_code == 404:
                continue
            resp.raise_for_status()
            payload = resp.json()
            file_list = payload.get("dataset", {}).get("distribution", payload)
            if not isinstance(file_list, list):
                continue
            _download_matching_essdive_files(file_list, wanted, dest_dir, location_metadata_files)
            return
        except Exception as exc:  # pragma: no cover - depends on live API behavior.
            last_error = exc

    typer.echo("  ESS-DIVE package API lookup failed; trying DOI redirect fallback...")
    try:
        _download_essdive_doi_fallback(doi, dest_dir, location_metadata_files, dry_run=False)
    except Exception as exc:
        raise RuntimeError(f"failed to download ESS-DIVE files for {doi}: {last_error or exc}") from exc


def _download_matching_essdive_files(
    file_list: list[dict],
    wanted: Optional[set[str]],
    dest_dir: Path,
    location_metadata_files: Optional[list[str]],
) -> None:
    """Download ESS-DIVE file records that match requested mapping paths."""
    wanted_paths = location_metadata_files or []
    downloaded = 0
    for file_info in file_list:
        name = file_info.get("name", "")
        basename = Path(name).name
        if wanted is not None and not any(Path(w).name == basename for w in wanted):
            continue
        download_url = (
            file_info.get("contentUrl")
            or file_info.get("url")
            or file_info.get("downloadUrl")
        )
        if not download_url:
            continue
        rel_path = next((w for w in wanted_paths if Path(w).name == basename), f"data/{basename}")
        out_path = dest_dir / rel_path
        typer.echo(f"  downloading {name} → {out_path}")
        _download_url_to_path(download_url, out_path)
        downloaded += 1

    if wanted_paths and downloaded < len(wanted_paths):
        raise RuntimeError("ESS-DIVE response did not include all requested location metadata files")


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
    files_url = f"{ESSDIVE_PACKAGES_API}/{quote(pkg_id, safe=':')}"
    fresp = requests.get(files_url, timeout=60)
    fresp.raise_for_status()
    payload = fresp.json()
    file_list = payload.get("dataset", {}).get("distribution", payload)
    if not isinstance(file_list, list):
        legacy_url = f"{ESSDIVE_LEGACY_FILES_API}/{pkg_id}/files"
        legacy = requests.get(legacy_url, timeout=60)
        legacy.raise_for_status()
        file_list = legacy.json()

    wanted = set(location_metadata_files) if location_metadata_files else None
    _download_matching_essdive_files(file_list, wanted, dest_dir, location_metadata_files)


def stage_dataset(
    entry: dict,
    dest_root: Path,
    drive_urls: list[str],
    remote: str = RCLONE_REMOTE,
    drive_method: DriveMethod = "auto",
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

    resolved_method = _resolve_drive_method(
        drive_method,
        drive_urls,
        remote=remote,
        dry_run=dry_run,
        verbose=verbose,
    )
    matched_folder_id: Optional[str] = None
    already_matched: set[int] = set()

    for url in drive_urls:
        folder_id = _folder_id_from_url(url)
        try:
            folder_files = _list_drive_folder_by_method(
                folder_id,
                drive_method=resolved_method,
                remote=remote,
                dry_run=dry_run,
            )
        except (FileNotFoundError, subprocess.CalledProcessError, requests.RequestException) as exc:
            typer.echo(f"  WARNING: Drive listing failed for {url}: {exc}", err=True)
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
        typer.echo(f"  → {resolved_method} copy from folder {matched_folder_id}")
    _copy_drive_folder_by_method(
        matched_folder_id,
        entry,
        dest_dir,
        drive_method=resolved_method,
        remote=remote,
        dry_run=dry_run,
        verbose=verbose,
    )
    return dest_dir


def match_all_drive_folders(
    drive_urls: list[str],
    mapping: list[dict],
    remote: str = RCLONE_REMOTE,
    drive_method: DriveMethod = "auto",
    dry_run: bool = False,
    verbose: bool = True,
) -> dict[int, str]:
    """Match each Drive folder to its dataset entry by file-set intersection.

    Lists every folder once and greedily assigns each to the best-matching
    entry.  Returns ``{dataset_index: folder_id}``.
    """
    resolved_method = _resolve_drive_method(
        drive_method,
        drive_urls,
        remote=remote,
        dry_run=dry_run,
        verbose=verbose,
    )
    folder_contents: dict[str, list[str]] = {}
    for url in drive_urls:
        folder_id = _folder_id_from_url(url)
        if dry_run:
            folder_contents[folder_id] = []
            continue
        try:
            files = _list_drive_folder_by_method(
                folder_id,
                drive_method=resolved_method,
                remote=remote,
            )
        except (FileNotFoundError, subprocess.CalledProcessError, requests.RequestException) as exc:
            typer.echo(f"WARNING: Drive listing failed for {url}: {exc}", err=True)
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
    drive_method: DriveMethod = "auto",
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
        path = stage_dataset(
            entry,
            dest_root,
            drive_urls=[],
            remote=remote,
            drive_method=drive_method,
            dry_run=dry_run,
            verbose=verbose,
        )
        staged.append(path)

    if drive_entries:
        resolved_method = _resolve_drive_method(
            drive_method,
            drive_urls,
            remote=remote,
            dry_run=dry_run,
            verbose=verbose,
        )
        if verbose:
            typer.echo(
                f"\nBuilding Drive folder→dataset mapping for {len(drive_urls)} folders "
                f"using {resolved_method}..."
            )
        folder_map = match_all_drive_folders(
            drive_urls,
            drive_entries,
            remote=remote,
            drive_method=resolved_method,
            dry_run=dry_run,
            verbose=verbose,
        )

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
                typer.echo(f"  → {resolved_method} copy from folder {folder_id}")
            _copy_drive_folder_by_method(
                folder_id,
                entry,
                dest_dir,
                drive_method=resolved_method,
                remote=remote,
                dry_run=dry_run,
                verbose=verbose,
            )
            staged.append(dest_dir)

    return staged


app = typer.Typer(add_completion=False, help="Stage raw ESS-DIVE datasets to ~/ess-dive_wfsfa_soil_datasets/.")


@app.command()
def main(
    dest: Path = typer.Option(DEFAULT_DEST, "--dest", help="Root directory for staged datasets."),
    mapping: Path = typer.Option(DEFAULT_MAPPING, "--mapping", help="Gold mapping JSON."),
    drive_urls: Path = typer.Option(DEFAULT_DRIVE_URLS, "--drive-urls", help="File with one Drive folder URL per line."),
    remote: str = typer.Option(RCLONE_REMOTE, "--remote", help="rclone remote name for Google Drive."),
    drive_method: DriveMethod = typer.Option(
        "auto",
        "--drive-method",
        help="Google Drive access method: auto, rclone, or public.",
    ),
    indices: Optional[str] = typer.Option(None, "--indices", help="Comma-separated dataset indices to stage (default: all)."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print actions without executing rclone or downloading."),
    quiet: bool = typer.Option(False, "--quiet", help="Suppress per-dataset progress messages."),
) -> None:
    """Stage raw soil-moisture datasets to DEST/<dataset_identifier>/.

    Matches Google Drive folders to datasets by file-set content. By default,
    the tool uses rclone when the configured remote is available and otherwise
    falls back to anonymous public Drive folder listings plus direct downloads
    of the mapping-declared files. REF idx 0 is fetched directly from ESS-DIVE.

    Prerequisites:
    - For rclone mode, rclone must be installed and the remote configured:
      ``rclone config``.
    - Public mode requires the Drive folders to be readable by "Anyone with
      the link".
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
        drive_method=drive_method,
        dry_run=dry_run,
        verbose=not quiet,
    )

    typer.echo(f"\nDone. Staged {len(staged)} dataset(s) to {dest}")


if __name__ == "__main__":
    app()
