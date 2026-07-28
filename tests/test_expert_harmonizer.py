"""Tests for the modular expert harmonizer's leave-one-cluster-out helpers."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest
from typer.testing import CliRunner

from src.folds.expert_harmonizer import (
    DATASET_INDICES,
    app,
    assemble_source,
    block_indices,
    kept_indices,
    kept_module_paths,
    resolve_holdout,
)

PACKAGE = Path("data/gold/expert_code/harmonize_sm")
needs_pkg = pytest.mark.skipif(not PACKAGE.exists(), reason="expert package not present")

# The expert harmonizes these 19 datasets; 0 (reference) and 11-14, 19-22
# (globally excluded) have no module.
EXPERT_TARGETS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 16, 17, 18, 23, 24, 25, 26, 27]
CLUSTER_1 = {1, 2, 3, 6, 16, 27}  # "sg_ph_micromet"


# --- pure helpers (no scientific stack needed) ---


@pytest.mark.parametrize(
    "tokens,expected",
    [(["1", "5"], {1, 5}), (["1"], {1}), ([" 5 ", ""], {5})],
)
def test_resolve_holdout_integer_tokens(tokens, expected):
    assert resolve_holdout(tokens, None) == expected


def test_resolve_holdout_identifier_tokens(tmp_path):
    mp = tmp_path / "mapping.json"
    mp.write_text('[{"index": 5, "dataset_identifier": "ess-dive_abc"}]')
    assert resolve_holdout(["ess-dive_abc"], mp) == {5}


def test_resolve_holdout_unknown_token_raises(tmp_path):
    mp = tmp_path / "mapping.json"
    mp.write_text("[]")
    with pytest.raises(ValueError):
        resolve_holdout(["not-an-index"], mp)


# --- against the real modular package ---


@needs_pkg
def test_block_indices_match_expert_targets():
    assert block_indices() == EXPERT_TARGETS
    assert DATASET_INDICES == EXPERT_TARGETS


@needs_pkg
def test_kept_indices_removes_only_the_holdout():
    assert kept_indices(CLUSTER_1) == [i for i in EXPERT_TARGETS if i not in CLUSTER_1]


@needs_pkg
@pytest.mark.parametrize("bad", [{0}, {11}, {19}, {1, 12}])
def test_kept_indices_rejects_ref_and_excluded(bad):
    with pytest.raises(ValueError):
        kept_indices(bad)


@needs_pkg
def test_kept_module_paths_drop_holdout_keep_common_and_rest():
    paths = kept_module_paths(CLUSTER_1)
    names = [p.name for p in paths]
    assert names[0] == "common.py"  # shared library always included
    for i in CLUSTER_1:
        assert f"dataset_{i:02d}.py" not in names
    for i in set(EXPERT_TARGETS) - CLUSTER_1:
        assert f"dataset_{i:02d}.py" in names
    # every kept module is independently valid Python
    for p in paths:
        ast.parse(p.read_text())


@needs_pkg
def test_assemble_source_excludes_holdout_code_keeps_rest():
    out = assemble_source(CLUSTER_1)
    assert "common.py" in out
    assert "dataset_27.py" not in out  # held out
    assert "idx = 27" not in out
    assert "dataset_05.py" in out  # kept
    assert "idx = 5" in out


@needs_pkg
def test_cli_source_writes_holdout_free_code(tmp_path):
    out = tmp_path / "kept.py"
    result = CliRunner().invoke(
        app, ["source", "--holdout", "1,2,3,6,16,27", "--mapping", "/nonexistent", "-o", str(out)]
    )
    assert result.exit_code == 0, result.output
    text = out.read_text()
    assert "dataset_27.py" not in text and "dataset_05.py" in text


@needs_pkg
def test_cli_kept_lists_remaining_modules():
    result = CliRunner().invoke(
        app, ["kept", "--holdout", "1,2,3,6,16,27", "--mapping", "/nonexistent"]
    )
    assert result.exit_code == 0, result.output
    assert "common.py" in result.output
    assert "dataset_27.py" not in result.output
    assert "dataset_18.py" in result.output
