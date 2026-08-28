"""Resolve a workflow-dispatch target into an isolated fold specification."""
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


_SAFE_INPUT = re.compile(r"[A-Za-z0-9._,-]+")
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class ResolvedFold:
    """Values consumed by the GitHub Actions evaluation workflow."""

    holdout: str
    target: str
    env_name: str
    stage_indices: str


def resolve_fold(raw: str, name_input: str, config: dict[str, Any]) -> ResolvedFold:
    """Resolve one dispatch input against the targeted grouped-CV configuration.

    A configured numeric target stages one dataset while removing its complete
    reference holdout from exemplars. Cluster IDs/names and comma-separated
    values retain the legacy multi-target behavior.
    """
    raw = raw.strip()
    if not raw:
        raise ValueError("`holdout` input is required")
    if not _SAFE_INPUT.fullmatch(raw):
        raise ValueError("`holdout` must contain only letters, digits, dots, underscores, hyphens, and commas")

    clusters = config.get("clusters", {}) or {}
    folds = config.get("folds", []) or []
    holdout = target = raw
    cluster_id: str | None = None
    fold_id: int | None = None

    if raw.isdigit():
        configured = next((f for f in folds if f.get("target_dataset") == int(raw)), None)
        if configured is not None:
            target = str(configured["target_dataset"])
            reference_holdout = configured.get("reference_holdout_datasets")
            if not isinstance(reference_holdout, list) or not reference_holdout:
                raise ValueError(f"configured target {raw} has no reference_holdout_datasets")
            holdout = ",".join(str(i) for i in reference_holdout)
            cluster_id = configured.get("held_out_cluster")
            fold_id = configured.get("fold_id")

    for cid, cluster in clusters.items():
        if raw in {cid, str(cluster.get("name", "")).strip()}:
            holdout = target = ",".join(str(i) for i in cluster.get("datasets", []))
            cluster_id = cid
            fold_id = None
            break

    requested_name = name_input.strip()
    env_name = requested_name or (
        f"fold-{fold_id:02d}-target-{target}" if fold_id is not None else cluster_id or f"holdout-{raw}"
    )
    env_name = _SAFE_NAME.sub("-", env_name).strip("-") or "run"
    stage_indices = ",".join(token for token in target.split(",") if token.isdigit())
    return ResolvedFold(holdout=holdout, target=target, env_name=env_name, stage_indices=stage_indices)


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve a targeted grouped-CV workflow input.")
    parser.add_argument("--input", required=True, dest="raw")
    parser.add_argument("--name", default="")
    parser.add_argument("--config", type=Path, default=Path("config/cv_folds.yaml"))
    args = parser.parse_args()
    config = yaml.safe_load(args.config.read_text()) or {}
    try:
        resolved = resolve_fold(args.raw, args.name, config)
    except ValueError as exc:
        parser.error(str(exc))
    for key, value in vars(resolved).items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
