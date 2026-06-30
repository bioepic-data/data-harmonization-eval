"""Run Skill 2 (harmonizer) under controlled conditions.

This module provides the interface for invoking the harmonizer skill
with a curator bundle and recording outputs.
"""
from __future__ import annotations
from pathlib import Path
import json
import hashlib
from datetime import datetime
from typing import Optional

from src.schemas.skill1_bundle import CuratorBundle
from src.schemas.skill2_mapping import Skill2Output, HarmonizationMapping


def invoke_harmonizer(
    bundle: CuratorBundle,
    exemplar_pool: list[int],
    skill_version: str,
    model_id: str,
    random_seed: int,
    output_dir: Path,
) -> Skill2Output:
    """Run Skill 2 from a curator bundle.

    PLACEHOLDER: Wire to actual skill invocation.

    Args:
        bundle: Input curator bundle (validated)
        exemplar_pool: Dataset indices visible as code exemplars
        skill_version: Version of harmonizer skill to use
        model_id: Exact model identifier for reproducibility
        random_seed: Random seed for stochastic generation
        output_dir: Directory to write outputs

    Returns:
        Skill2Output with generated code and mapping JSON

    Implementation notes:
        - Must dereference bundle.similar_dataset_reference to actual code
        - Must restrict exemplar code to only datasets in exemplar_pool
        - Must validate mapping JSON against HarmonizationMapping schema
        - Must capture full conversation transcript
    """
    # PLACEHOLDER: Actual implementation would:
    # 1. Load harmonizer skill from skills/wfsfa_sm_harmonization/SKILL.md
    # 2. Load exemplar code/mappings from gold directory (filtered to pool)
    # 3. Invoke Claude API with skill prompt + bundle
    # 4. Parse output into python_code and mapping_json
    # 5. Validate mapping against schema
    # 6. Save outputs

    raise NotImplementedError(
        "invoke_harmonizer must be connected to actual Claude API/SDK. "
        "See skills/wfsfa_sm_harmonization/SKILL.md for skill definition."
    )

    # Expected return structure:
    # output = Skill2Output(
    #     package_id=bundle.package_id,
    #     python_code=generated_code,
    #     mapping_json=HarmonizationMapping(**generated_mapping),
    #     skill_version=skill_version,
    #     run_id=generate_run_id(bundle.package_id, random_seed),
    #     timestamp=datetime.utcnow().isoformat(),
    #     input_bundle_hash=hash_bundle(bundle),
    # )
    #
    # # Save outputs
    # code_path = output_dir / f"{output.package_id}_{output.run_id}.py"
    # mapping_path = output_dir / f"{output.package_id}_{output.run_id}_mapping.json"
    #
    # code_path.write_text(output.python_code)
    # mapping_path.write_text(output.mapping_json.model_dump_json(indent=2))
    #
    # return output


def run_skill2_oracle(
    gold_bundle: CuratorBundle,
    exemplar_pool: list[int],
    config: dict,
    output_dir: Path,
    run_index: int = 0,
) -> dict:
    """Run Skill 2 with oracle (gold) curator input.

    This isolates harmonizer quality from curator errors.

    Args:
        gold_bundle: Expert-validated curator bundle (ground truth)
        exemplar_pool: Dataset indices available as code exemplars
        config: Experiment configuration
        output_dir: Where to save outputs
        run_index: Index of this stochastic run

    Returns:
        Dict with outputs and metadata for scoring
    """
    run_dir = output_dir / f"run_{run_index}"
    run_dir.mkdir(parents=True, exist_ok=True)

    try:
        output = invoke_harmonizer(
            bundle=gold_bundle,
            exemplar_pool=exemplar_pool,
            skill_version=config["experiment"]["skill2_version"],
            model_id=config["experiment"]["model_id"],
            random_seed=config["experiment"]["random_seed"] + run_index,
            output_dir=run_dir,
        )

        return {
            "identifier": gold_bundle.package_id,
            "mode": "skill2_oracle",
            "run_index": run_index,
            "success": True,
            "output": output.model_dump(),
            "code_path": str(run_dir / f"{output.package_id}_{output.run_id}.py"),
            "mapping_path": str(run_dir / f"{output.package_id}_{output.run_id}_mapping.json"),
            "error": None,
        }

    except Exception as e:
        return {
            "identifier": gold_bundle.package_id,
            "mode": "skill2_oracle",
            "run_index": run_index,
            "success": False,
            "output": None,
            "code_path": None,
            "mapping_path": None,
            "error": str(e),
        }


def hash_bundle(bundle: CuratorBundle) -> str:
    """Compute deterministic hash of a curator bundle."""
    content = bundle.model_dump_json(sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()[:12]


def generate_run_id(package_id: str, seed: int) -> str:
    """Generate deterministic run ID from package and seed."""
    content = f"{package_id}_{seed}"
    return hashlib.sha256(content.encode()).hexdigest()[:12]
