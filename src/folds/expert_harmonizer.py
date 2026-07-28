"""Leave-one-cluster-out over the *modular* expert harmonizer.

The expert harmonization used to be one 1200-line monolith, and grouped LOO was
done by text-splicing per-dataset ``# %%`` cells out of it (the old
``ablate_monolith``). The harmonizer is now a small package — a shared
``common`` library plus one ``dataset_NN.py`` per dataset — so holding a cluster
out no longer needs any splicing:

* **Executable** (regenerate exemplar outputs without the held-out datasets):
  :func:`run` calls the package runner, which simply doesn't run the held-out
  modules.
* **Code context** (show the agent held-out-free reference code):
  :func:`kept_module_paths` returns ``common.py`` plus the kept ``dataset_NN.py``
  files — the patterns to feed as exemplars.

Requiring each hold-out to be a real dataset module automatically rejects the
reference dataset (0) and the globally-excluded datasets (11-14, 19-22), so
there is no coupling to ``cv_folds.yaml``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Optional

import typer

PACKAGE_DIR = Path("data/gold/expert_code/harmonize_sm")
DEFAULT_MAPPING = Path("data/gold/sm_data_harmonization_mapping.json")

# Datasets the expert harmonizes, in module order. Kept in sync with
# ``harmonize_sm/datasets.py``; :func:`block_indices` validates it against disk.
DATASET_INDICES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 16, 17, 18, 23, 24, 25, 26, 27]


def dataset_module_path(idx: int, package_dir: Path = PACKAGE_DIR) -> Path:
    """Path to the per-dataset module for ``idx`` (whether or not it exists)."""
    return package_dir / f"dataset_{idx:02d}.py"


def block_indices(package_dir: Path = PACKAGE_DIR) -> list[int]:
    """Dataset indices that actually have a module on disk (sorted ascending)."""
    found = []
    for idx in DATASET_INDICES:
        if dataset_module_path(idx, package_dir).exists():
            found.append(idx)
    return sorted(found)


def _validate_holdout(holdout: set[int], package_dir: Path) -> None:
    present = set(block_indices(package_dir))
    missing = sorted(holdout - present)
    if missing:
        raise ValueError(
            f"no dataset module for index/indices {missing}; "
            f"available datasets: {sorted(present)}"
        )


def kept_indices(holdout: Iterable[int], package_dir: Path = PACKAGE_DIR) -> list[int]:
    """Dataset indices that remain after removing ``holdout`` (sorted).

    Raises ``ValueError`` if any hold-out index has no module — this is what
    rejects the reference dataset (0) and the excluded datasets (11-14, 19-22).
    """
    holdout = set(holdout)
    _validate_holdout(holdout, package_dir)
    return [i for i in block_indices(package_dir) if i not in holdout]


def kept_module_paths(holdout: Iterable[int], package_dir: Path = PACKAGE_DIR) -> list[Path]:
    """``common.py`` + the kept ``dataset_NN.py`` files, for exemplar code context.

    This is the modular replacement for the old "ablated monolith" text: the set
    of reference code patterns the agent should see when the hold-out cluster is
    removed.
    """
    paths = [package_dir / "common.py"]
    paths += [dataset_module_path(i, package_dir) for i in kept_indices(holdout, package_dir)]
    return paths


def assemble_source(holdout: Iterable[int], package_dir: Path = PACKAGE_DIR) -> str:
    """Concatenate the kept modules into one annotated text block (read-only).

    Convenience for tools that want a single string of the held-out-free expert
    code (e.g. to drop into a prompt). It is reference material, not a runnable
    script — execution goes through :func:`run`.
    """
    chunks = []
    for path in kept_module_paths(holdout, package_dir):
        chunks.append(f"# ===== {path.name} =====\n{path.read_text()}")
    return "\n\n".join(chunks)


def resolve_holdout(tokens: Iterable[str], mapping_path: Optional[Path]) -> set[int]:
    """Resolve hold-out tokens (integer indices or ``dataset_identifier``s).

    Integer-looking tokens are used directly; everything else is looked up as a
    ``dataset_identifier`` in the gold mapping JSON.
    """
    ident_to_idx: dict[str, int] = {}
    if mapping_path is not None and Path(mapping_path).exists():
        mapping = json.loads(Path(mapping_path).read_text())
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


def run(
    holdout: Iterable[int],
    *,
    base_dir: Optional[Path] = None,
    out_dir: Optional[Path] = None,
    mapping_path: Optional[Path] = None,
    write: bool = True,
):
    """Execute the modular harmonizer with ``holdout`` removed.

    Delegates to ``harmonize_sm/run.py``; imported lazily so this module stays
    importable without the scientific stack.
    """
    import importlib.util
    import sys

    holdout = set(holdout)
    _validate_holdout(holdout, PACKAGE_DIR)

    runner_path = PACKAGE_DIR / "run.py"
    sys.path.insert(0, str(PACKAGE_DIR.resolve()))
    spec = importlib.util.spec_from_file_location("harmonize_sm_run", runner_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run(
        holdout=holdout,
        base_dir=base_dir,
        out_dir=out_dir,
        mapping_path=mapping_path,
        write=write,
    )


app = typer.Typer(
    add_completion=False,
    help="Leave-one-cluster-out over the modular expert harmonizer.",
)


@app.command("kept")
def cmd_kept(
    holdout: str = typer.Option(..., "--holdout", help="Comma-separated indices or identifiers."),
    mapping: Path = typer.Option(DEFAULT_MAPPING, "--mapping", help="Gold mapping JSON."),
) -> None:
    """List the module files that remain after removing the hold-out datasets."""
    holdout_idx = resolve_holdout(holdout.split(","), mapping)
    for path in kept_module_paths(holdout_idx):
        typer.echo(str(path))


@app.command("source")
def cmd_source(
    holdout: str = typer.Option(..., "--holdout", help="Comma-separated indices or identifiers."),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Write here (default stdout)."),
    mapping: Path = typer.Option(DEFAULT_MAPPING, "--mapping", help="Gold mapping JSON."),
) -> None:
    """Emit the held-out-free expert code (common + kept datasets) as one block."""
    holdout_idx = resolve_holdout(holdout.split(","), mapping)
    text = assemble_source(holdout_idx)
    if output is None:
        typer.echo(text, nl=False)
    else:
        output.write_text(text)
        typer.echo(
            f"wrote {output} (held out {sorted(holdout_idx)}; "
            f"{len(kept_indices(holdout_idx))} datasets remain)",
            err=True,
        )


@app.command("run")
def cmd_run(
    holdout: str = typer.Option("", "--holdout", help="Comma-separated indices or identifiers."),
    mapping: Path = typer.Option(DEFAULT_MAPPING, "--mapping", help="Gold mapping JSON."),
    no_write: bool = typer.Option(False, "--no-write", help="Run without writing CSVs."),
) -> None:
    """Run the harmonizer with the hold-out datasets removed."""
    holdout_idx = resolve_holdout(holdout.split(","), mapping) if holdout.strip() else set()
    ids, _, _ = run(holdout_idx, write=not no_write)
    typer.echo(
        f"harmonized {len(ids)} datasets; held out {sorted(holdout_idx)}", err=True
    )


if __name__ == "__main__":
    app()
