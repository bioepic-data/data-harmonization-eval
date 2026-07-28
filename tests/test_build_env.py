"""Tests for the leave-one-cluster-out run-environment builder."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from src.folds.build_env import (
    HARMONIZER_REL,
    MAPPING_REL,
    app,
    build_env,
    default_name,
    filter_mapping,
)

MAPPING = [
    {"index": 1, "dataset_identifier": "ess-dive_a", "doi": "doi:1"},
    {"index": 2, "dataset_identifier": "ess-dive_b", "doi": "doi:2"},
    {"index": 5, "dataset_identifier": "ess-dive_c", "doi": "doi:5"},
]


@pytest.fixture
def sources(tmp_path):
    """A synthetic modular harmonizer package + mapping + skills dir."""
    pkg = tmp_path / "harmonize_sm"
    pkg.mkdir()
    (pkg / "common.py").write_text("SHARED = 1\n")
    for i in (1, 2, 5):  # indices must be in expert_harmonizer.DATASET_INDICES
        (pkg / f"dataset_{i:02d}.py").write_text(f"# dataset {i}\nIDX = {i}\n")
    mapping = tmp_path / "mapping.json"
    mapping.write_text(json.dumps(MAPPING))
    skills = tmp_path / "skills"
    (skills / "essdive_sm_curator").mkdir(parents=True)
    (skills / "essdive_sm_curator" / "SKILL.md").write_text("curator")
    return pkg, mapping, skills


def test_filter_mapping_drops_holdout_keeps_index():
    assert [e["index"] for e in filter_mapping(MAPPING, {2})] == [1, 5]


def test_default_name_is_sorted():
    assert default_name({5, 1, 2}) == "holdout-1-2-5"


def test_build_env_layout_and_content(tmp_path, sources):
    pkg, mapping, skills = sources
    env = build_env({2}, env_root=tmp_path / ".runs", package_dir=pkg,
                    mapping_path=mapping, skills_dir=skills)

    # held-out-free modular code at the harmonizer's read path
    hdir = env / HARMONIZER_REL
    assert (hdir / "common.py").exists()
    assert (hdir / "dataset_01.py").exists()
    assert (hdir / "dataset_05.py").exists()
    assert not (hdir / "dataset_02.py").exists()  # held out -> not copied

    # filtered mapping at the exemplar read path, holdout entry gone
    mp = json.loads((env / MAPPING_REL).read_text())
    assert [e["index"] for e in mp] == [1, 5]

    # skills copied; manifest + instructions written
    assert (env / "skills" / "essdive_sm_curator" / "SKILL.md").exists()
    manifest = json.loads((env / "MANIFEST.json").read_text())
    assert manifest["holdout_indices"] == [2]
    assert manifest["holdout_identifiers"] == ["ess-dive_b"]
    assert manifest["exemplar_indices"] == [1, 5]
    assert "ess-dive_b" in (env / "AGENT_INSTRUCTIONS.md").read_text()


def test_build_env_metadata_symlink(tmp_path, sources):
    pkg, mapping, skills = sources
    meta = tmp_path / "meta"
    meta.mkdir()
    (meta / "x.json").write_text("{}")
    env = build_env({1}, env_root=tmp_path / ".runs", package_dir=pkg,
                    mapping_path=mapping, skills_dir=skills, metadata_dir=meta)
    link = env / "data" / "external" / "ess-dive_meta"
    assert link.is_symlink() and (link / "x.json").exists()


def test_build_env_rejects_holdout_without_module(tmp_path, sources):
    pkg, mapping, skills = sources
    with pytest.raises(ValueError):
        build_env({3}, env_root=tmp_path / ".runs", package_dir=pkg,
                  mapping_path=mapping, skills_dir=skills)  # no dataset_03.py


def test_build_env_overwrites_existing(tmp_path, sources):
    pkg, mapping, skills = sources
    kw = dict(env_root=tmp_path / ".runs", package_dir=pkg, mapping_path=mapping, skills_dir=skills)
    first = build_env({2}, name="cfg", **kw)
    (first / "stale.txt").write_text("old")
    second = build_env({1}, name="cfg", **kw)
    assert first == second
    assert not (second / "stale.txt").exists()  # rebuilt clean


def test_cli_builds_env(tmp_path, sources):
    pkg, mapping, skills = sources
    result = CliRunner().invoke(app, [
        "--holdout", "2", "--name", "cli", "--env-root", str(tmp_path / ".runs"),
        "--package", str(pkg), "--mapping", str(mapping), "--skills", str(skills),
    ])
    assert result.exit_code == 0, result.output
    assert (tmp_path / ".runs" / "cli" / HARMONIZER_REL / "dataset_01.py").exists()
    assert not (tmp_path / ".runs" / "cli" / HARMONIZER_REL / "dataset_02.py").exists()


# --- Against the real modular harmonizer, when present ---

PKG = Path("data/gold/expert_code/harmonize_sm")
needs_pkg = pytest.mark.skipif(not PKG.exists(), reason="modular expert harmonizer not present")


@needs_pkg
def test_real_build_env_holds_out_cluster(tmp_path):
    holdout = {1, 2, 3, 6, 16, 27}  # cluster_1 "sg_ph_micromet"
    env = build_env(holdout, env_root=tmp_path / ".runs")
    hdir = env / HARMONIZER_REL
    assert (hdir / "common.py").exists()
    for i in holdout:
        assert not (hdir / f"dataset_{i:02d}.py").exists()
    for i in (4, 5, 7, 8, 9, 10, 15, 17, 18, 23, 24, 25, 26):
        assert (hdir / f"dataset_{i:02d}.py").exists()
    mp = json.loads((env / MAPPING_REL).read_text())
    assert not any(e["index"] in holdout for e in mp)


@needs_pkg
def test_real_build_env_rejects_ref_idx_and_excluded(tmp_path):
    for bad in ({0}, {11}, {19}):
        with pytest.raises(ValueError):
            build_env(bad, env_root=tmp_path / ".runs")
