"""Tests for the leave-one-cluster-out run-environment builder."""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from src.folds.build_env import (
    MAPPING_REL,
    MONOLITH_REL,
    app,
    build_env,
    default_name,
    filter_mapping,
)

# Synthetic monolith: header + three dataset blocks + footer (mirrors the real
# `# %%` / `idx = N` structure) so the suite needs no corpus.
MONOLITH = """\
# %%
acc = []

# %%
# Dataset 1
idx = 1
acc.append(("ds1", idx))

# %%
# Dataset 2
idx = 2
acc.append(("ds2", idx))

# %%
# Dataset 5
idx = 5
acc.append(("ds5", idx))

# %%
print(acc)  # footer
"""

MAPPING = [
    {"index": 1, "dataset_identifier": "ess-dive_a", "doi": "doi:1"},
    {"index": 2, "dataset_identifier": "ess-dive_b", "doi": "doi:2"},
    {"index": 5, "dataset_identifier": "ess-dive_c", "doi": "doi:5"},
]


@pytest.fixture
def sources(tmp_path):
    """Write a synthetic monolith, mapping, and skills dir; return their paths."""
    mono = tmp_path / "monolith.py"
    mono.write_text(MONOLITH)
    mapping = tmp_path / "mapping.json"
    mapping.write_text(json.dumps(MAPPING))
    skills = tmp_path / "skills"
    (skills / "essdive_sm_curator").mkdir(parents=True)
    (skills / "essdive_sm_curator" / "SKILL.md").write_text("curator")
    return mono, mapping, skills


def test_filter_mapping_drops_holdout_keeps_index():
    out = filter_mapping(MAPPING, {2})
    assert [e["index"] for e in out] == [1, 5]


def test_default_name_is_sorted():
    assert default_name({5, 1, 2}) == "holdout-1-2-5"


def test_build_env_layout_and_content(tmp_path, sources):
    mono, mapping, skills = sources
    env = build_env({2}, env_root=tmp_path / ".runs", monolith_path=mono,
                     mapping_path=mapping, skills_dir=skills)

    # ablated monolith at the harmonizer's read path, holdout block gone, parseable
    py = (env / MONOLITH_REL).read_text()
    assert "ds2" not in py and "ds1" in py and "ds5" in py
    ast.parse(py)

    # filtered mapping at the exemplar read path, holdout entry gone
    mp = json.loads((env / MAPPING_REL).read_text())
    assert [e["index"] for e in mp] == [1, 5]

    # skills copied; manifest + instructions written
    assert (env / "skills" / "essdive_sm_curator" / "SKILL.md").exists()
    manifest = json.loads((env / "MANIFEST.json").read_text())
    assert manifest["holdout_indices"] == [2]
    assert manifest["holdout_identifiers"] == ["ess-dive_b"]
    assert manifest["exemplar_indices"] == [1, 5]
    instr = (env / "AGENT_INSTRUCTIONS.md").read_text()
    assert "ess-dive_b" in instr  # held-out id named for the trace audit


def test_build_env_metadata_symlink(tmp_path, sources):
    mono, mapping, skills = sources
    meta = tmp_path / "meta"
    meta.mkdir()
    (meta / "x.json").write_text("{}")
    env = build_env({1}, env_root=tmp_path / ".runs", monolith_path=mono,
                    mapping_path=mapping, skills_dir=skills, metadata_dir=meta)
    link = env / "data" / "external" / "ess-dive_meta"
    assert link.is_symlink() and (link / "x.json").exists()


def test_build_env_rejects_non_block_holdout(tmp_path, sources):
    mono, mapping, skills = sources
    with pytest.raises(ValueError):
        build_env({99}, env_root=tmp_path / ".runs", monolith_path=mono,
                  mapping_path=mapping, skills_dir=skills)


def test_build_env_overwrites_existing(tmp_path, sources):
    mono, mapping, skills = sources
    kw = dict(env_root=tmp_path / ".runs", monolith_path=mono, mapping_path=mapping, skills_dir=skills)
    first = build_env({2}, name="cfg", **kw)
    (first / "stale.txt").write_text("old")
    second = build_env({1}, name="cfg", **kw)
    assert first == second
    assert not (second / "stale.txt").exists()  # rebuilt clean


def test_cli_builds_env(tmp_path, sources):
    mono, mapping, skills = sources
    result = CliRunner().invoke(app, [
        "--holdout", "2", "--name", "cli", "--env-root", str(tmp_path / ".runs"),
        "--monolith", str(mono), "--mapping", str(mapping), "--skills", str(skills),
    ])
    assert result.exit_code == 0, result.output
    assert (tmp_path / ".runs" / "cli" / MONOLITH_REL).exists()
