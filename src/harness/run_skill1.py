"""Run Skill 1 (curator) under controlled conditions.

This module provides the interface for invoking the curator skill
with specified exemplar pools and recording outputs in a reproducible way.
"""
from __future__ import annotations
from pathlib import Path
import json
import hashlib
from datetime import datetime
from typing import Optional

from src.schemas.skill1_bundle import CuratorBundle


def invoke_curator(
    identifier: str,
    exemplar_pool: list[int],
    skill_version: str,
    model_id: str,
    random_seed: int,
    output_dir: Path,
) -> CuratorBundle:
    """Run Skill 1 on a single identifier.

    PLACEHOLDER: Wire to actual skill invocation (Claude API/SDK).

    Args:
        identifier: DOI or ESS-DIVE package ID
        exemplar_pool: List of dataset indices visible as references
            (critical for CV: held-out dataset must NOT be in pool)
        skill_version: Version of curator skill to use
        model_id: Exact model identifier for reproducibility
        random_seed: Random seed for stochastic generation
        output_dir: Directory to write bundle JSON

    Returns:
        Validated CuratorBundle

    Implementation notes:
        - Must restrict skill's access to only datasets in exemplar_pool
        - Must set model parameters (temp, seed) for reproducibility
        - Must capture full conversation transcript for auditing
        - Must validate output against CuratorBundle schema
    """
    # PLACEHOLDER: Actual implementation would:
    # 1. Load curator skill from skills/essdive_sm_curator/SKILL.md
    # 2. Filter mapping JSON to only include exemplar_pool datasets
    # 3. Invoke Claude API with skill prompt + identifier
    # 4. Parse output into CuratorBundle structure
    # 5. Validate against schema
    # 6. Save to output_dir

    raise NotImplementedError(
        "invoke_curator must be connected to actual Claude API/SDK. "
        "See skills/essdive_sm_curator/SKILL.md for skill definition."
    )

    # Expected return structure:
    # bundle = CuratorBundle(
    #     package_id=...,
    #     doi=...,
    #     curator_decision=...,
    #     # ... all other fields
    #     skill_version=skill_version,
    #     run_id=generate_run_id(identifier, random_seed),
    #     timestamp=datetime.utcnow().isoformat(),
    # )
    #
    # # Save bundle
    # bundle_path = output_dir / f"{bundle.package_id}_{bundle.run_id}.json"
    # bundle_path.write_text(bundle.model_dump_json(indent=2))
    #
    # return bundle


def run_skill1_isolated(
    identifier: str,
    exemplar_pool: list[int],
    config: dict,
    output_dir: Path,
    run_index: int = 0,
) -> dict:
    """Run Skill 1 in isolation mode for evaluation.

    Args:
        identifier: DOI or package ID to curate
        exemplar_pool: Dataset indices available as exemplars
        config: Experiment configuration dict
        output_dir: Where to save outputs
        run_index: Index of this stochastic run (0-4 typically)

    Returns:
        Dict with bundle and metadata for scoring
    """
    # Create run-specific output directory
    run_dir = output_dir / f"run_{run_index}"
    run_dir.mkdir(parents=True, exist_ok=True)

    try:
        bundle = invoke_curator(
            identifier=identifier,
            exemplar_pool=exemplar_pool,
            skill_version=config["experiment"]["skill1_version"],
            model_id=config["experiment"]["model_id"],
            random_seed=config["experiment"]["random_seed"] + run_index,
            output_dir=run_dir,
        )

        return {
            "identifier": identifier,
            "mode": "skill1_isolated",
            "run_index": run_index,
            "success": True,
            "bundle": bundle.model_dump(),
            "bundle_path": str(run_dir / f"{bundle.package_id}_{bundle.run_id}.json"),
            "error": None,
        }

    except Exception as e:
        return {
            "identifier": identifier,
            "mode": "skill1_isolated",
            "run_index": run_index,
            "success": False,
            "bundle": None,
            "bundle_path": None,
            "error": str(e),
        }


def generate_run_id(identifier: str, seed: int) -> str:
    """Generate deterministic run ID from identifier and seed."""
    content = f"{identifier}_{seed}"
    return hashlib.sha256(content.encode()).hexdigest()[:12]
