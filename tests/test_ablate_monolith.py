"""Tests for the monolith block-ablation splicer."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest
from typer.testing import CliRunner

from src.folds.ablate_monolith import (
    app,
    ablate,
    block_indices,
    cell_index,
    resolve_holdout,
    split_cells,
)

# A miniature stand-in with the same shape as the expert script: a header cell,
# two dataset blocks anchored by ``idx = N``, an excluded-comment cell, and a
# footer cell. Keeps the test suite independent of the full corpus.
SYNTHETIC = """\
# %%
acc = []  # header / shared accumulator

# %%
# =============================================================
# Dataset 1
# =============================================================
idx = 1
acc.append(("ds1", idx))

# %%
# Dataset 2-3 excluded

# %%
# =============================================================
# Dataset 5
# =============================================================
idx = 5
acc.append(("ds5", idx))

# %%
# footer
print(acc)
"""


def test_split_cells_is_lossless():
    assert "".join(split_cells(SYNTHETIC)) == SYNTHETIC


def test_block_indices_finds_only_dataset_cells():
    assert block_indices(SYNTHETIC) == [1, 5]


def test_cell_index_none_for_non_dataset_cell():
    assert cell_index("# %%\nimport os\n") is None


def test_ablate_removes_only_the_holdout_block():
    out = ablate(SYNTHETIC, {1})
    assert block_indices(out) == [5]
    assert "ds1" not in out
    assert "ds5" in out
    assert "header" in out and "footer" in out  # surrounding cells preserved
    ast.parse(out)  # still valid Python


def test_ablate_rejects_index_without_a_block():
    with pytest.raises(ValueError):
        ablate(SYNTHETIC, {2})  # 2 is only an excluded comment, no block


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


def test_cli_writes_ablated_file(tmp_path):
    src = tmp_path / "mono.py"
    src.write_text(SYNTHETIC)
    out = tmp_path / "ablated.py"
    result = CliRunner().invoke(
        app, ["--holdout", "1", "--input", str(src), "--output", str(out)]
    )
    assert result.exit_code == 0, result.output
    text = out.read_text()
    assert "ds1" not in text and "ds5" in text


# --- Against the real expert monolith, when present ---

GOLD = Path("data/gold/expert_code/harmonize_ess-dive_soilmoisture_data.py")
EXPERT_TARGETS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 16, 17, 18, 23, 24, 25, 26, 27]
needs_gold = pytest.mark.skipif(not GOLD.exists(), reason="gold expert code not present")


@needs_gold
def test_real_monolith_has_19_dataset_blocks():
    assert block_indices(GOLD.read_text()) == EXPERT_TARGETS


@needs_gold
def test_real_ablation_of_cluster_stays_parseable_and_keeps_scaffold():
    src = GOLD.read_text()
    holdout = {1, 2, 3, 6, 16, 27}  # cluster_1 "sg_ph_micromet"
    out = ablate(src, holdout)
    assert set(block_indices(out)) == set(EXPERT_TARGETS) - holdout
    ast.parse(out)  # syntactically valid
    assert "REF_IDX = 0" in out  # shared reference dataset preserved
    assert "Location deduplication" in out  # footer preserved
    assert "idx = 27" not in out  # held-out anchor gone


@needs_gold
def test_real_ablation_rejects_ref_idx_and_excluded():
    src = GOLD.read_text()
    for bad in ({0}, {11}, {19}):
        with pytest.raises(ValueError):
            ablate(src, bad)
