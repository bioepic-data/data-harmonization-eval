"""Build a self-contained run environment for one leave-one-cluster-out config.

Grouped leave-one-cluster-out evaluates the curator+harmonizer agent on a
held-out cluster of datasets while the *other* datasets serve as exemplars. To
keep the held-out cluster's reference answer out of the agent's reach, we
materialize a per-config sandbox under ``.runs/<name>/`` containing only:

* the **skills** (curator + harmonizer), copied verbatim;
* the **ablated mapping JSON** — the gold mapping with the held-out cluster's
  entries removed, written to the path the skills read for exemplars
  (``data/processed/ess-dive_wfsfa_soil_datasets/sm_data_harmonization_mapping.json``);
* the **ablated monolith** — the expert harmonization script with the held-out
  blocks spliced out (see :mod:`src.folds.ablate_monolith`), written to the path
  the harmonizer reads as a code-pattern reference
  (``notebooks/harmonize_ess-dive_soilmoisture_data.py``).

Isolation is by *absence*: the two answer-bearing artifacts in the env have the
held-out cluster removed, and they sit at the exact relative paths the skills
resolve, so the skill picks up the ablated copy rather than the original. Shared
*inputs* are deliberately NOT treated as leakage and stay where they are:

* raw per-dataset CSVs at ``~/ess-dive_wfsfa_soil_datasets/<dsid>/`` — read by
  generated code via an absolute home path, so they need no env copy;
* cached ESS-DIVE metadata — optionally symlinked in via ``metadata_dir`` (the
  curator reads it to evaluate a dataset; seeing a dataset's own metadata is the
  task input, not the answer).

The agent can in principle escape the sandbox (``../`` or absolute paths); the
backstop is instruction (``AGENT_INSTRUCTIONS.md``) plus a post-hoc trace audit
against the held-out ``dataset_identifier``s recorded in ``MANIFEST.json``.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Optional

import typer

from src.folds.ablate_monolith import (
    DEFAULT_INPUT as DEFAULT_MONOLITH,
    DEFAULT_MAPPING,
    ablate,
    block_indices,
    resolve_holdout,
)

DEFAULT_SKILLS = Path("skills")
DEFAULT_ENV_ROOT = Path(".runs")

# Where each artifact lands inside the env, matching the skills' read paths.
MONOLITH_REL = Path("notebooks/harmonize_ess-dive_soilmoisture_data.py")
MAPPING_REL = Path("data/processed/ess-dive_wfsfa_soil_datasets/sm_data_harmonization_mapping.json")
METADATA_REL = Path("data/external/ess-dive_meta")


def filter_mapping(mapping: list[dict], holdout: set[int]) -> list[dict]:
    """Drop the held-out cluster's entries from the gold mapping.

    Entries keep their canonical ``index`` field; only held-out datasets are
    removed, so the result is the exemplar set the agent is allowed to see.

    >>> filter_mapping([{"index": 1}, {"index": 2}, {"index": 3}], {2})
    [{'index': 1}, {'index': 3}]
    """
    return [e for e in mapping if e.get("index") not in holdout]


def default_name(holdout: set[int]) -> str:
    """Derive a stable config directory name from the hold-out indices.

    >>> default_name({6, 2, 16})
    'holdout-2-6-16'
    """
    return "holdout-" + "-".join(str(i) for i in sorted(holdout))


def build_env(
    holdout: set[int],
    name: Optional[str] = None,
    env_root: Path = DEFAULT_ENV_ROOT,
    monolith_path: Path = DEFAULT_MONOLITH,
    mapping_path: Path = DEFAULT_MAPPING,
    skills_dir: Path = DEFAULT_SKILLS,
    metadata_dir: Optional[Path] = None,
) -> Path:
    """Materialize ``.runs/<name>/`` for one leave-one-cluster-out config.

    Returns the env directory. Overwrites an existing env of the same name.
    """
    mapping = json.loads(Path(mapping_path).read_text())
    source = Path(monolith_path).read_text()

    # ablate() raises if a hold-out index has no block (rejects REF_IDX 0 and
    # the excluded datasets) — fail loudly before writing anything.
    ablated_py = ablate(source, holdout)
    filtered = filter_mapping(mapping, holdout)

    env = Path(env_root) / (name or default_name(holdout))
    if env.exists():
        shutil.rmtree(env)
    env.mkdir(parents=True)

    (env / MONOLITH_REL).parent.mkdir(parents=True, exist_ok=True)
    (env / MONOLITH_REL).write_text(ablated_py)

    (env / MAPPING_REL).parent.mkdir(parents=True, exist_ok=True)
    (env / MAPPING_REL).write_text(json.dumps(filtered, indent=2))

    shutil.copytree(skills_dir, env / "skills")

    if metadata_dir is not None:
        (env / METADATA_REL).parent.mkdir(parents=True, exist_ok=True)
        (env / METADATA_REL).symlink_to(Path(metadata_dir).resolve(), target_is_directory=True)

    idx_to_dsid = {e["index"]: e.get("dataset_identifier") for e in mapping}
    held_ids = [idx_to_dsid.get(i) for i in sorted(holdout)]
    manifest = {
        "name": env.name,
        "holdout_indices": sorted(holdout),
        "holdout_identifiers": held_ids,
        "exemplar_indices": block_indices(ablated_py),
        "n_exemplars": len(filtered),
        "sources": {
            "monolith": str(monolith_path),
            "mapping": str(mapping_path),
            "skills": str(skills_dir),
        },
    }
    (env / "MANIFEST.json").write_text(json.dumps(manifest, indent=2))
    (env / "AGENT_INSTRUCTIONS.md").write_text(_instructions(held_ids))
    return env


def _instructions(held_ids: list) -> str:
    ids = "\n".join(f"- `{i}`" for i in held_ids if i)
    return (
        "# Run environment — leave-one-cluster-out\n\n"
        "Harmonize the held-out dataset(s) below using ONLY:\n"
        "- the skills in `skills/`,\n"
        "- the exemplars in `data/processed/.../sm_data_harmonization_mapping.json` "
        "and the code patterns in `notebooks/harmonize_ess-dive_soilmoisture_data.py` "
        "(both have the held-out cluster removed),\n"
        "- the shared raw inputs under `~/ess-dive_wfsfa_soil_datasets/` and the "
        "cached metadata under `data/external/ess-dive_meta/`.\n\n"
        "Do NOT look up the held-out dataset's existing harmonized output, expert "
        "code, or mapping entry from any other location. The held-out datasets are:\n\n"
        f"{ids}\n"
    )


app = typer.Typer(add_completion=False, help="Build a leave-one-cluster-out run environment.")


@app.command()
def main(
    holdout: str = typer.Option(..., "--holdout", help="Comma-separated indices or dataset_identifiers to hold out."),
    name: Optional[str] = typer.Option(None, "--name", help="Env dir name (default: holdout-<ids>)."),
    env_root: Path = typer.Option(DEFAULT_ENV_ROOT, "--env-root", help="Parent dir for run environments."),
    monolith: Path = typer.Option(DEFAULT_MONOLITH, "--monolith", help="Expert monolith to ablate."),
    mapping: Path = typer.Option(DEFAULT_MAPPING, "--mapping", help="Gold mapping JSON."),
    skills: Path = typer.Option(DEFAULT_SKILLS, "--skills", help="Skills dir to copy."),
    metadata_dir: Optional[Path] = typer.Option(None, "--metadata-dir", help="Cached ESS-DIVE metadata to symlink in."),
) -> None:
    """Assemble `.runs/<name>/` for one hold-out config."""
    holdout_idx = resolve_holdout(holdout.split(","), mapping)
    env = build_env(
        holdout_idx, name=name, env_root=env_root, monolith_path=monolith,
        mapping_path=mapping, skills_dir=skills, metadata_dir=metadata_dir,
    )
    typer.echo(f"built {env} (held out {sorted(holdout_idx)}; "
               f"{len(block_indices((env / MONOLITH_REL).read_text()))} exemplar blocks remain)")


if __name__ == "__main__":
    app()
