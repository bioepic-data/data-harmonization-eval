"""Run Skill 1 (curator) under controlled conditions.

This module provides the interface for invoking the curator skill
with specified exemplar pools and recording outputs in a reproducible way.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.schemas.skill1_bundle import CuratorBundle

from .skill_invoker import SkillInvoker


def invoke_curator(
    identifier: str,
    exemplar_pool: list[int],
    skill_version: str,
    model_id: str,
    random_seed: int,
    output_dir: Path,
    api_key: Optional[str] = None,
) -> CuratorBundle:
    """Run Skill 1 on a single identifier.

    Args:
        identifier: DOI or ESS-DIVE package ID
        exemplar_pool: List of dataset indices visible as references
            (critical for CV: held-out dataset must NOT be in pool)
        skill_version: Version of curator skill to use
        model_id: Exact model identifier for reproducibility
        random_seed: Random seed for stochastic generation
        output_dir: Directory to write bundle JSON
        api_key: Optional Anthropic API key (defaults to ANTHROPIC_API_KEY env var)

    Returns:
        Validated CuratorBundle with all fields populated

    Raises:
        ValueError: If API key not provided or skill invocation fails
        pydantic.ValidationError: If output doesn't match CuratorBundle schema
    """
    # Setup paths
    project_root = Path(__file__).parent.parent.parent
    skills_dir = project_root / "skills"
    data_dir = project_root / "data"

    # Initialize skill invoker
    invoker = SkillInvoker(
        skills_dir=skills_dir,
        data_dir=data_dir,
        api_key=api_key,
    )

    # Build curator prompt
    user_prompt = f"""Evaluate this ESS-DIVE soil moisture dataset for inclusion in the harmonization pipeline:

**Dataset Identifier**: {identifier}

Your task:
1. Retrieve package metadata (check local cache in data/external/ess-dive_meta/ first, then ESS-DIVE API if needed)
2. Inspect all files in the package
3. Make an INCLUDE/EXCLUDE/FLAG_FOR_REVIEW decision based on the criteria in your system prompt
4. Extract all required information for the curator bundle

**Available exemplar datasets (indices)**: {exemplar_pool}

When selecting a similar dataset reference, choose from this exemplar pool based on structural similarity.

**Output your complete curator bundle as a JSON object matching the CuratorBundle schema.**
Include all required fields:
- package_id, doi, curator_decision
- data_payload_files (with filename, columns, row_count_estimate)
- location_metadata_files, sensor_metadata_files
- location_resolution (with site_coordinates)
- time_series_inference (is_timeseries, interval_min, reasoning)
- experimental_context (manipulation_detected, recommendation)
- similar_dataset_reference (index from exemplar pool, reason)
- open_questions (if any uncertainties)

If EXCLUDE, provide clear exclusion_reason.
If FLAG_FOR_REVIEW, document specific open_questions.
"""

    # Create output directory
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Invoke skill with output validation
    result = invoker.invoke_skill(
        skill_name="essdive_sm_curator",
        user_prompt=user_prompt,
        model_id=model_id,
        temperature=1.0,  # Allow natural variation
        max_tokens=16384,  # Curator needs space for file inspections
        output_schema=CuratorBundle,
        exemplar_pool=exemplar_pool,
    )

    # Extract validated bundle
    bundle = result["parsed_output"]

    # Add metadata
    bundle.skill_version = skill_version
    bundle.run_id = SkillInvoker.generate_run_id(identifier, random_seed)
    bundle.timestamp = datetime.now(timezone.utc).isoformat()

    # Save bundle
    bundle_path = output_dir / f"{bundle.package_id}_{bundle.run_id}.json"
    bundle_path.write_text(bundle.model_dump_json(indent=2))

    # Save full API response for audit trail
    transcript_path = output_dir / f"{bundle.package_id}_{bundle.run_id}_transcript.json"
    transcript_path.write_text(json.dumps({
        "user_prompt": user_prompt,
        "model_id": model_id,
        "exemplar_pool": exemplar_pool,
        "usage": result["run_metadata"]["usage"],
        "response_text": result["response_text"],
    }, indent=2))

    return bundle


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
