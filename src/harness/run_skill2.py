"""Run Skill 2 (harmonizer) under controlled conditions.

This module provides the interface for invoking the harmonizer skill
with a curator bundle and recording outputs.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.schemas.skill1_bundle import CuratorBundle
from src.schemas.skill2_mapping import HarmonizationMapping, Skill2Output

from .skill_invoker import SkillInvoker


def invoke_harmonizer(
    bundle: CuratorBundle,
    exemplar_pool: list[int],
    skill_version: str,
    model_id: str,
    random_seed: int,
    output_dir: Path,
    api_key: Optional[str] = None,
) -> Skill2Output:
    """Run Skill 2 from a curator bundle.

    Args:
        bundle: Input curator bundle (validated)
        exemplar_pool: Dataset indices visible as code exemplars
        skill_version: Version of harmonizer skill to use
        model_id: Exact model identifier for reproducibility
        random_seed: Random seed for stochastic generation
        output_dir: Directory to write outputs
        api_key: Optional Anthropic API key (defaults to ANTHROPIC_API_KEY env var)

    Returns:
        Skill2Output with generated code and mapping JSON

    Raises:
        ValueError: If API key not provided or skill invocation fails
        pydantic.ValidationError: If outputs don't match schemas
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

    # Load exemplar code snippets from gold directory
    exemplar_code_snippets = _load_exemplar_code(
        data_dir=data_dir,
        exemplar_pool=exemplar_pool,
        similar_index=bundle.similar_dataset_reference.index if bundle.similar_dataset_reference else None,
    )

    # Build harmonizer prompt
    user_prompt = f"""Generate harmonization code and mapping JSON for this dataset:

**Curator Bundle:**
```json
{bundle.model_dump_json(indent=2)}
```

**Available exemplar code from datasets (indices)**: {exemplar_pool}

{exemplar_code_snippets}

Your task:
1. Review the curator bundle and understand the dataset structure
2. Generate Python harmonization code following the modular pattern (uses common.py utilities)
3. Generate the complete JSON mapping entry documenting all transformations

**IMPORTANT PATTERNS TO FOLLOW:**

**Code structure:**
- Import from common.py: `as_list, parse_local_to_utc, interval_min, ensure_harmonized_cols, add_loc_qc, utm32613_to_latlon`
- Function signature: `def harmonize(ctx): ...`
- Return: `DatasetResult(__dataset_id, __harmonized, __locations)`
- Handle wide-to-long transformations for VWC/water potential
- Apply unit conversions (cm→m, %→fraction)
- Parse depth from column patterns
- Extract site_id from filename or columns
- Handle location lookup/reprojection

**Mapping JSON structure:**
- Include all harmonization_mappings fields: datetime, depth, latitude, longitude, replicate, site_id, volumetric_water_content, soil_water_potential, gravimetric_water_content
- Document transformation patterns with source_pattern, source_files, destination_variable, transformation, unit_conversion
- Use pattern_1, pattern_2, etc. for multiple patterns per variable

**Output format:**
Provide BOTH outputs in your response:

1. Python code block:
```python
# Your harmonization code here
```

2. JSON mapping block:
```json
{{
  "index": <assign next index>,
  "dataset_identifier": "{bundle.package_id}",
  "doi": "{bundle.doi}",
  ...
}}
```
"""

    # Create output directory
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Invoke skill (no output_schema - we'll parse manually due to dual outputs)
    result = invoker.invoke_skill(
        skill_name="essdive_sm_harmonizer",
        user_prompt=user_prompt,
        model_id=model_id,
        temperature=1.0,
        max_tokens=16384,  # Harmonizer needs space for code generation
        exemplar_pool=exemplar_pool,
    )

    response_text = result["response_text"]

    # Extract Python code
    python_code = _extract_python_code(response_text)
    if not python_code:
        raise ValueError("No Python code block found in response")

    # Extract and validate mapping JSON
    mapping_json = _extract_and_validate_mapping(response_text, bundle)

    # Create output object
    output = Skill2Output(
        package_id=bundle.package_id,
        python_code=python_code,
        mapping_json=mapping_json,
        skill_version=skill_version,
        run_id=SkillInvoker.generate_run_id(bundle.package_id, random_seed),
        timestamp=datetime.now(timezone.utc).isoformat(),
        input_bundle_hash=hash_bundle(bundle),
    )

    # Save outputs
    code_path = output_dir / f"{output.package_id}_{output.run_id}.py"
    mapping_path = output_dir / f"{output.package_id}_{output.run_id}_mapping.json"

    code_path.write_text(output.python_code)
    mapping_path.write_text(output.mapping_json.model_dump_json(indent=2))

    # Save full API response for audit trail
    transcript_path = output_dir / f"{output.package_id}_{output.run_id}_transcript.json"
    transcript_path.write_text(json.dumps({
        "user_prompt": user_prompt,
        "model_id": model_id,
        "exemplar_pool": exemplar_pool,
        "usage": result["run_metadata"]["usage"],
        "response_text": response_text,
    }, indent=2))

    return output


def _load_exemplar_code(
    data_dir: Path,
    exemplar_pool: list[int],
    similar_index: Optional[int] = None,
) -> str:
    """Load relevant exemplar code snippets.

    Args:
        data_dir: Path to data/ directory
        exemplar_pool: Available dataset indices
        similar_index: Index of similar dataset (prioritize this one)

    Returns:
        Formatted string with exemplar code snippets
    """
    gold_code_dir = data_dir / "gold" / "expert_code" / "harmonize_sm"

    snippets = []

    # Prioritize similar dataset if specified
    indices_to_show = []
    if similar_index is not None and similar_index in exemplar_pool:
        indices_to_show.append(similar_index)

    # Add 1-2 other diverse examples
    for idx in exemplar_pool:
        if idx != similar_index and len(indices_to_show) < 3:
            indices_to_show.append(idx)

    # Load code files
    for idx in indices_to_show:
        code_file = gold_code_dir / f"dataset_{idx:02d}.py"
        if code_file.exists():
            code = code_file.read_text()
            snippets.append(f"**Exemplar code from dataset {idx}:**\n```python\n{code}\n```\n")

    if not snippets:
        return "No exemplar code available."

    return "\n\n".join(snippets)


def _extract_python_code(response_text: str) -> Optional[str]:
    """Extract Python code block from response."""
    # Look for ```python blocks
    python_blocks = re.findall(
        r'```python\n(.*?)\n```',
        response_text,
        re.DOTALL
    )

    if python_blocks:
        return python_blocks[0].strip()

    # Fallback: look for any code block
    code_blocks = re.findall(
        r'```\n(.*?)\n```',
        response_text,
        re.DOTALL
    )

    for block in code_blocks:
        # Check if it looks like Python (has def, import, etc.)
        if any(keyword in block for keyword in ['def harmonize', 'import', 'from common import']):
            return block.strip()

    return None


def _extract_and_validate_mapping(response_text: str, bundle: CuratorBundle) -> HarmonizationMapping:
    """Extract and validate mapping JSON from response."""
    # Look for JSON blocks
    json_blocks = re.findall(
        r'```(?:json)?\n(\{.*?\})\n```',
        response_text,
        re.DOTALL
    )

    errors = []
    for candidate in json_blocks:
        try:
            data = json.loads(candidate)

            # Ensure required fields
            if "dataset_identifier" not in data:
                data["dataset_identifier"] = bundle.package_id
            if "doi" not in data:
                data["doi"] = bundle.doi
            if "archive_repository" not in data:
                data["archive_repository"] = "ESS-DIVE"

            return HarmonizationMapping(**data)
        except (json.JSONDecodeError, Exception) as e:
            errors.append(str(e))
            continue

    raise ValueError(
        f"Could not extract valid HarmonizationMapping from response.\n"
        f"Tried {len(json_blocks)} JSON candidates.\n"
        f"Errors: {errors[:3]}"
    )


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
