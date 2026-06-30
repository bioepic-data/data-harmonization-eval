"""End-to-end runner: identifier -> curator -> harmonizer.

Each function is a thin wrapper around the actual skill invocation.
The point of this scaffold is to fix the DATA CONTRACT and LOGGING,
so every run is reproducible and scorable.
"""
from __future__ import annotations
from pathlib import Path
import json
from datetime import datetime

from src.schemas.skill1_bundle import CuratorBundle
from .run_skill1 import invoke_curator
from .run_skill2 import invoke_harmonizer


def run_end_to_end(
    identifier: str,
    exemplar_pool: list[int],
    config: dict,
    output_dir: Path,
    run_index: int = 0,
) -> dict:
    """Run complete pipeline: curator -> harmonizer.

    Args:
        identifier: DOI or package ID to process
        exemplar_pool: Dataset indices available as exemplars/references
        config: Experiment configuration
        output_dir: Where to save all outputs
        run_index: Index of this stochastic run

    Returns:
        Dict with all outputs and metadata for scoring
    """
    run_dir = output_dir / f"run_{run_index}"
    run_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "identifier": identifier,
        "mode": "end_to_end",
        "run_index": run_index,
        "exemplar_pool": exemplar_pool,
        "timestamp": datetime.utcnow().isoformat(),
    }

    # Stage 1: Curator
    try:
        bundle = invoke_curator(
            identifier=identifier,
            exemplar_pool=exemplar_pool,
            skill_version=config["experiment"]["skill1_version"],
            model_id=config["experiment"]["model_id"],
            random_seed=config["experiment"]["random_seed"] + run_index,
            output_dir=run_dir / "curator",
        )

        result["curator_success"] = True
        result["bundle"] = bundle.model_dump()
        result["bundle_path"] = str(run_dir / "curator" / f"{bundle.package_id}_{bundle.run_id}.json")

    except Exception as e:
        result["curator_success"] = False
        result["curator_error"] = str(e)
        result["harmonizer_attempted"] = False
        result["success"] = False
        return result

    # Stage 2: Harmonizer (only if curator said INCLUDE)
    if bundle.curator_decision == "INCLUDE":
        try:
            output = invoke_harmonizer(
                bundle=bundle,
                exemplar_pool=exemplar_pool,
                skill_version=config["experiment"]["skill2_version"],
                model_id=config["experiment"]["model_id"],
                random_seed=config["experiment"]["random_seed"] + run_index + 1000,
                output_dir=run_dir / "harmonizer",
            )

            result["harmonizer_success"] = True
            result["harmonizer_attempted"] = True
            result["output"] = output.model_dump()
            result["code_path"] = str(run_dir / "harmonizer" / f"{output.package_id}_{output.run_id}.py")
            result["mapping_path"] = str(run_dir / "harmonizer" / f"{output.package_id}_{output.run_id}_mapping.json")
            result["success"] = True

        except Exception as e:
            result["harmonizer_success"] = False
            result["harmonizer_attempted"] = True
            result["harmonizer_error"] = str(e)
            result["success"] = False

    elif bundle.curator_decision == "EXCLUDE":
        # Correct exclusion is also a success
        result["harmonizer_attempted"] = False
        result["success"] = True
        result["exclusion_reason"] = bundle.exclusion_reason

    elif bundle.curator_decision == "FLAG_FOR_REVIEW":
        # Deferral; scored separately for calibration
        result["harmonizer_attempted"] = False
        result["success"] = True
        result["flagged"] = True
        result["open_questions"] = bundle.open_questions

    # Save complete result
    result_path = run_dir / "result.json"
    result_path.write_text(json.dumps(result, indent=2, default=str))

    return result
