"""Ablate per-dataset blocks from the expert harmonization monolith.

The expert script ``data/gold/expert_code/harmonize_ess-dive_soilmoisture_data.py``
is organized as a sequence of Jupyter-style ``# %%`` cells. Nineteen of those
cells are per-dataset harmonization blocks, each anchored by a single
``idx = N`` line whose ``N`` is the dataset's index in the gold mapping JSON.
Every other cell (config, shared helpers, the location-deduplication footer)
carries no ``idx =`` assignment.

Grouped leave-one-cluster-out evaluation needs an *executable* copy of this
script with a chosen set of dataset blocks removed, so the held-out cluster is
absent from both the agent's exemplar context and any regenerated exemplar
outputs. The blocks only append to shared accumulators and the sole cross-block
dependency is ``REF_IDX = 0`` (index 0 is never a hold-out target), so dropping
a block's cell leaves the remaining script runnable.

This module performs that splice by whole cell, keyed on ``idx = N``. Requiring
each requested hold-out to correspond to a real block automatically rejects
``REF_IDX`` (0) and the excluded datasets (11-14, 19-22), which carry no block —
so no coupling to ``cv_folds.yaml`` is needed.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

import typer

CELL_RE = re.compile(r"^# %%(\[markdown\])?\s*$")
IDX_RE = re.compile(r"^idx\s*=\s*(\d+)\s*$")

DEFAULT_INPUT = Path("data/gold/expert_code/harmonize_ess-dive_soilmoisture_data.py")
DEFAULT_MAPPING = Path("data/gold/sm_data_harmonization_mapping.json")


def split_cells(source: str) -> list[str]:
    """Split monolith source into ``# %%`` cells, losslessly.

    Each returned chunk begins with its ``# %%`` marker line, and concatenating
    the chunks reproduces ``source`` exactly.

    >>> cells = split_cells("# %%\\na = 1\\n# %%\\nb = 2\\n")
    >>> len(cells)
    2
    >>> "".join(cells) == "# %%\\na = 1\\n# %%\\nb = 2\\n"
    True
    """
    lines = source.splitlines(keepends=True)
    cells: list[str] = []
    current: list[str] = []
    for line in lines:
        if CELL_RE.match(line) and current:
            cells.append("".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        cells.append("".join(current))
    return cells


def cell_index(cell: str) -> Optional[int]:
    """Return the dataset index a cell harmonizes, or ``None`` for other cells.

    >>> cell_index("# %%\\nidx = 7\\nf7 = read(idx)\\n")
    7
    >>> cell_index("# %%\\nimport pandas as pd\\n") is None
    True
    """
    for line in cell.splitlines():
        m = IDX_RE.match(line)
        if m:
            return int(m.group(1))
    return None


def block_indices(source: str) -> list[int]:
    """All dataset indices that have a block in ``source`` (sorted ascending)."""
    found = (cell_index(c) for c in split_cells(source))
    return sorted(i for i in found if i is not None)


def ablate(source: str, holdout: set[int]) -> str:
    """Return ``source`` with the held-out dataset blocks removed.

    Only whole ``# %%`` cells whose ``idx = N`` is in ``holdout`` are dropped;
    every other cell (config, helpers, footer, other datasets) is preserved
    verbatim, so the result stays executable.

    Raises ``ValueError`` if any requested index has no block in ``source`` —
    this is what rejects ``REF_IDX`` (0) and the excluded datasets.
    """
    present = set(block_indices(source))
    missing = sorted(holdout - present)
    if missing:
        raise ValueError(
            f"no dataset block for index/indices {missing}; "
            f"available blocks: {sorted(present)}"
        )
    kept = [c for c in split_cells(source) if cell_index(c) not in holdout]
    result = "".join(kept)
    remaining = set(block_indices(result))
    expected = present - holdout
    assert remaining == expected, (
        f"ablation removed the wrong blocks: kept {sorted(remaining)}, "
        f"expected {sorted(expected)}"
    )
    return result


def resolve_holdout(tokens: list[str], mapping_path: Optional[Path]) -> set[int]:
    """Resolve hold-out tokens (integer indices or ``dataset_identifier``s).

    Integer-looking tokens are used directly; everything else is looked up as a
    ``dataset_identifier`` in the gold mapping JSON.
    """
    ident_to_idx: dict[str, int] = {}
    if mapping_path is not None and mapping_path.exists():
        mapping = json.loads(mapping_path.read_text())
        ident_to_idx = {
            e["dataset_identifier"]: e["index"]
            for e in mapping
            if e.get("dataset_identifier") is not None
        }
    out: set[int] = set()
    for raw in tokens:
        tok = raw.strip()
        if not tok:
            continue
        if tok.isdigit():
            out.add(int(tok))
        elif tok in ident_to_idx:
            out.add(ident_to_idx[tok])
        else:
            raise ValueError(
                f"hold-out token {tok!r} is neither an integer index nor a known "
                f"dataset_identifier in {mapping_path}"
            )
    return out


app = typer.Typer(
    add_completion=False,
    help="Ablate per-dataset blocks from the expert harmonization monolith.",
)


@app.command()
def main(
    holdout: str = typer.Option(
        ...,
        "--holdout",
        help="Comma-separated dataset indices or dataset_identifiers to remove.",
    ),
    input: Path = typer.Option(
        DEFAULT_INPUT, "--input", "-i", help="Path to the expert monolith."
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Write ablated script here (default: stdout)."
    ),
    mapping: Path = typer.Option(
        DEFAULT_MAPPING, "--mapping", help="Gold mapping JSON for identifier resolution."
    ),
) -> None:
    """Write an executable copy of the monolith with the hold-out blocks removed."""
    source = input.read_text()
    holdout_idx = resolve_holdout(holdout.split(","), mapping)
    ablated = ablate(source, holdout_idx)
    if output is None:
        typer.echo(ablated, nl=False)
    else:
        output.write_text(ablated)
        typer.echo(
            f"wrote {output} (removed blocks {sorted(holdout_idx)}; "
            f"{len(block_indices(ablated))} blocks remain)",
            err=True,
        )


if __name__ == "__main__":
    app()
