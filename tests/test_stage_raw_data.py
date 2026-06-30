"""Tests for the raw-data staging tool (no network or rclone needed)."""
from __future__ import annotations

import json
import subprocess
from unittest.mock import call, patch

import pytest
from typer.testing import CliRunner

from src.folds.stage_raw_data import (
    DriveFile,
    _copy_public_drive_declared_files,
    _folder_id_from_url,
    _load_drive_urls,
    _load_mapping,
    _match_folder_to_entry,
    _parse_drive_folder_links,
    app,
    match_all_drive_folders,
    stage_all,
)

MAPPING = [
    {
        "index": 0,
        "dataset_identifier": "ess-dive_ref",
        "doi": "doi:10.15485/1660962",
        "archive_repository": "ESS-DIVE",
        "data_payload_files": None,
        "location_metadata_files": ["data/East_Taylor_foo.csv"],
    },
    {
        "index": 1,
        "dataset_identifier": "ess-dive_a",
        "doi": "doi:10.15485/0001",
        "archive_repository": "ESS-DIVE",
        "data_payload_files": ["a1.csv", "a2.csv"],
        "location_metadata_files": None,
    },
    {
        "index": 2,
        "dataset_identifier": "ess-dive_b",
        "doi": "doi:10.15485/0002",
        "archive_repository": "ESS-DIVE",
        "data_payload_files": ["b1.csv", "b2.csv", "b3.csv"],
        "location_metadata_files": None,
    },
]

DRIVE_URLS = [
    "https://drive.google.com/drive/folders/folder_A",
    "https://drive.google.com/drive/folders/folder_B",
]


@pytest.fixture
def sources(tmp_path):
    mapping_path = tmp_path / "mapping.json"
    mapping_path.write_text(json.dumps(MAPPING))
    urls_path = tmp_path / "urls.csv"
    urls_path.write_text("\n".join(DRIVE_URLS) + "\n")
    return mapping_path, urls_path


def test_folder_id_from_url():
    assert _folder_id_from_url(DRIVE_URLS[0]) == "folder_A"
    assert _folder_id_from_url(DRIVE_URLS[1]) == "folder_B"


def test_folder_id_from_url_invalid():
    with pytest.raises(ValueError):
        _folder_id_from_url("https://drive.google.com/not-a-folder/x")


def test_load_mapping(sources):
    mapping_path, _ = sources
    data = _load_mapping(mapping_path)
    assert len(data) == 3
    assert data[0]["index"] == 0


def test_load_drive_urls(sources):
    _, urls_path = sources
    urls = _load_drive_urls(urls_path)
    assert urls == DRIVE_URLS


def test_match_folder_to_entry_exact():
    folder_files = ["a1.csv", "a2.csv", "README.md"]
    entry = _match_folder_to_entry(folder_files, MAPPING, already_matched=set())
    assert entry is not None
    assert entry["index"] == 1


def test_match_folder_to_entry_with_data_prefix():
    folder_files = ["data/a1.csv", "data/a2.csv", "metadata/science-metadata.xml"]
    entry = _match_folder_to_entry(folder_files, MAPPING, already_matched=set())
    assert entry is not None
    assert entry["index"] == 1


def test_match_folder_to_entry_best_match():
    folder_files = ["b1.csv", "b2.csv", "b3.csv"]
    entry = _match_folder_to_entry(folder_files, MAPPING, already_matched=set())
    assert entry is not None
    assert entry["index"] == 2


def test_match_folder_to_entry_skips_already_matched():
    folder_files = ["a1.csv", "a2.csv"]
    entry = _match_folder_to_entry(folder_files, MAPPING, already_matched={1})
    assert entry is None


def test_match_folder_to_entry_no_payload_entries_ignored():
    folder_files = ["East_Taylor_foo.csv"]
    entry = _match_folder_to_entry(folder_files, MAPPING, already_matched=set())
    assert entry is None


def test_match_folder_to_entry_no_match():
    folder_files = ["unknown_file.csv"]
    entry = _match_folder_to_entry(folder_files, MAPPING, already_matched=set())
    assert entry is None


def test_match_all_drive_folders_dry_run(sources):
    mapping_path, urls_path = sources
    mapping = _load_mapping(mapping_path)
    urls = _load_drive_urls(urls_path)
    result = match_all_drive_folders(urls, mapping, dry_run=True, verbose=False)
    assert isinstance(result, dict)


def test_parse_public_drive_folder_links():
    html = """
    <html><body>
      <a href="https://drive.google.com/file/d/1abcdefghijklmnopqrstuvwxyz/view">a1.csv</a>
      <a href="https://drive.google.com/drive/folders/2abcdefghijklmnopqrstuvwxyz">nested</a>
    </body></html>
    """
    files, folders = _parse_drive_folder_links(html)
    assert files == [DriveFile(file_id="1abcdefghijklmnopqrstuvwxyz", path="a1.csv")]
    assert folders == [("2abcdefghijklmnopqrstuvwxyz", "nested")]


def test_copy_public_drive_declared_files_downloads_only_declared(tmp_path):
    entry = MAPPING[1]
    dest = tmp_path / "dest"
    entries = [
        DriveFile(file_id="id_a1", path="a1.csv"),
        DriveFile(file_id="id_a2", path="data/a2.csv"),
        DriveFile(file_id="ignored", path="README.md"),
    ]

    with patch("src.folds.stage_raw_data._list_public_drive_folder_entries", return_value=entries):
        with patch("src.folds.stage_raw_data._download_public_drive_file") as download:
            _copy_public_drive_declared_files("folder_A", entry, dest, verbose=False)

    assert download.call_args_list == [
        call("id_a1", dest / "a1.csv", dry_run=False),
        call("id_a2", dest / "a2.csv", dry_run=False),
    ]


def test_stage_all_auto_falls_back_to_public_when_rclone_unavailable(tmp_path):
    with patch(
        "src.folds.stage_raw_data._list_drive_folder",
        side_effect=subprocess.CalledProcessError(1, ["rclone", "ls"]),
    ):
        with patch("src.folds.stage_raw_data._list_public_drive_folder", return_value=["a1.csv", "a2.csv"]):
            with patch("src.folds.stage_raw_data._copy_public_drive_declared_files") as copy_public:
                staged = stage_all(
                    MAPPING,
                    DRIVE_URLS,
                    tmp_path,
                    indices={1},
                    drive_method="auto",
                    verbose=False,
                )

    assert staged == [tmp_path / "ess-dive_a"]
    copy_public.assert_called_once()


def test_cli_dry_run(sources):
    mapping_path, urls_path = sources
    with patch("src.folds.stage_raw_data._list_drive_folder", return_value=[]):
        with patch("src.folds.stage_raw_data._copy_drive_folder"):
            with patch("src.folds.stage_raw_data._download_essdive_files"):
                result = CliRunner().invoke(app, [
                    "--mapping", str(mapping_path),
                    "--drive-urls", str(urls_path),
                    "--dry-run",
                    "--dest", "/tmp/test_stage_dest",
                ])
    assert result.exit_code == 0, result.output


def test_cli_indices_filter(sources):
    mapping_path, urls_path = sources
    calls = []
    with patch("src.folds.stage_raw_data._list_drive_folder", return_value=["a1.csv", "a2.csv"]):
        with patch("src.folds.stage_raw_data._copy_drive_folder", side_effect=lambda *a, **kw: calls.append(a)):
            with patch("src.folds.stage_raw_data._download_essdive_files"):
                result = CliRunner().invoke(app, [
                    "--mapping", str(mapping_path),
                    "--drive-urls", str(urls_path),
                    "--indices", "1",
                    "--dest", "/tmp/test_stage_dest2",
                    "--dry-run",
                ])
    assert result.exit_code == 0, result.output
