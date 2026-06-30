# Running Harmonization Evaluation Experiments

This guide explains how to run the evaluation experiments now that the harness is wired to the Claude API.

## Prerequisites

### 1. Install Dependencies

```bash
pip install -e .
```

This installs the project with all required dependencies, including the `anthropic` SDK.

### 2. Set Up API Key

You need an Anthropic API key with access to Claude models. Set it as an environment variable:

```bash
export ANTHROPIC_API_KEY='your-api-key-here'
```

Or pass it directly to the functions (not recommended for production).

### 3. Prepare Data

Ensure the following directories are populated:
- `data/gold/sm_data_harmonization_mapping.json` - Reference mappings
- `data/gold/expert_code/harmonize_sm/` - Expert harmonization code
- `data/gold/harmonized_outputs/` - Expert harmonized CSV files (for scoring)

## Architecture Overview

### Two-Stage Pipeline

```
┌─────────────┐
│  Dataset    │
│  Identifier │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────┐
│  Skill 1: Curator               │
│  (essdive_sm_curator)           │
│  ┌──────────────────────────┐  │
│  │ - Retrieves metadata     │  │
│  │ - Inspects files         │  │
│  │ - Makes INCLUDE/EXCLUDE  │  │
│  │ - Extracts site info     │  │
│  │ - Selects similar exemplar│ │
│  └──────────────────────────┘  │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────┐
│  CuratorBundle      │
│  (validated schema) │
└──────┬──────────────┘
       │ (if INCLUDE)
       ▼
┌─────────────────────────────────┐
│  Skill 2: Harmonizer            │
│  (essdive_sm_harmonizer)        │
│  ┌──────────────────────────┐  │
│  │ - Generates Python code  │  │
│  │ - Creates mapping JSON   │  │
│  │ - Follows exemplar pattern│ │
│  └──────────────────────────┘  │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────┐
│  Skill2Output       │
│  - python_code      │
│  - mapping_json     │
│  - metadata         │
└─────────────────────┘
```

### Key Components

**`src/harness/skill_invoker.py`**
- Core infrastructure for invoking skills via Claude API
- Loads skill definitions from `skills/` directory
- Manages context files and exemplar filtering
- Validates outputs against Pydantic schemas

**`src/harness/run_skill1.py`**
- `invoke_curator()`: Invokes curator skill on a dataset identifier
- Validates output as `CuratorBundle`
- Saves bundle + transcript for audit

**`src/harness/run_skill2.py`**
- `invoke_harmonizer()`: Invokes harmonizer skill with curator bundle
- Loads exemplar code from gold directory
- Extracts Python code and mapping JSON
- Validates against `Skill2Output` schema

**`src/harness/run_pipeline.py`**
- `run_end_to_end()`: Orchestrates full pipeline
- Handles curator → harmonizer flow
- Manages EXCLUDE/FLAG_FOR_REVIEW cases

## Running Experiments

### Example 1: Single End-to-End Run

```python
from pathlib import Path
from src.harness.run_pipeline import run_end_to_end

# Configuration
config = {
    "experiment": {
        "skill1_version": "0.1",
        "skill2_version": "0.3",
        "model_id": "claude-sonnet-4-5",
        "random_seed": 42,
    }
}

# Test on dataset 1 (held-out from exemplar pool)
result = run_end_to_end(
    identifier="doi:10.15485/2566877",  # Dataset 1
    exemplar_pool=[0, 2, 3, 4, 5, 6, 7, 8, 9, 10],  # All except 1
    config=config,
    output_dir=Path("output/test_run"),
    run_index=0,
)

print(f"Success: {result['success']}")
if result.get('curator_success'):
    print(f"Curator decision: {result['bundle']['curator_decision']}")
if result.get('harmonizer_success'):
    print(f"Code saved to: {result['code_path']}")
    print(f"Mapping saved to: {result['mapping_path']}")
```

### Example 2: Isolated Curator Test

Test curator skill only (faster, cheaper):

```python
from pathlib import Path
from src.harness.run_skill1 import invoke_curator

bundle = invoke_curator(
    identifier="doi:10.15485/2566877",
    exemplar_pool=[0, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    skill_version="0.1",
    model_id="claude-sonnet-4-5",
    random_seed=42,
    output_dir=Path("output/curator_test"),
)

print(f"Decision: {bundle.curator_decision}")
print(f"Data files found: {len(bundle.data_payload_files)}")
print(f"Similar to dataset: {bundle.similar_dataset_reference.index if bundle.similar_dataset_reference else 'None'}")
```

### Example 3: Oracle Harmonizer Test

Test harmonizer with gold curator bundle (isolates harmonizer quality):

```python
from pathlib import Path
from src.schemas.skill1_bundle import CuratorBundle
from src.harness.run_skill2 import run_skill2_oracle

# Load gold curator bundle (you'd create this from expert labels)
gold_bundle = CuratorBundle(
    package_id="ess-dive-beca0be9bb38ece-20250516T122010234",
    doi="doi:10.15485/2566877",
    curator_decision="INCLUDE",
    # ... other fields from expert ground truth
)

result = run_skill2_oracle(
    gold_bundle=gold_bundle,
    exemplar_pool=[0, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    config=config,
    output_dir=Path("output/oracle_test"),
    run_index=0,
)

if result['success']:
    print(f"Code: {result['code_path']}")
    print(f"Mapping: {result['mapping_path']}")
```

### Example 4: Cross-Validation Loop

Run leave-one-out cross-validation:

```python
from pathlib import Path
from src.harness.run_pipeline import run_end_to_end

all_datasets = list(range(1, 28))  # Dataset indices 1-27
config = {
    "experiment": {
        "skill1_version": "0.1",
        "skill2_version": "0.3",
        "model_id": "claude-sonnet-4-5",
        "random_seed": 42,
    }
}

results = []
for held_out in all_datasets:
    # Create exemplar pool (all except held-out)
    exemplar_pool = [idx for idx in all_datasets if idx != held_out]
    
    # Get DOI for held-out dataset
    # (you'd look this up from mapping JSON)
    doi = f"doi:10.15485/PLACEHOLDER_{held_out}"  # Replace with actual lookup
    
    print(f"\n=== Testing dataset {held_out} ===")
    print(f"Exemplar pool: {exemplar_pool}")
    
    result = run_end_to_end(
        identifier=doi,
        exemplar_pool=exemplar_pool,
        config=config,
        output_dir=Path(f"output/cv/dataset_{held_out:02d}"),
        run_index=0,
    )
    
    results.append({
        "dataset": held_out,
        "success": result["success"],
        "curator_decision": result.get("bundle", {}).get("curator_decision"),
        "harmonizer_attempted": result.get("harmonizer_attempted"),
    })

# Summary
successes = sum(1 for r in results if r["success"])
print(f"\n=== Summary ===")
print(f"Total: {len(results)}")
print(f"Successful: {successes}")
print(f"Failed: {len(results) - successes}")
```

## Output Structure

Each run creates:

```
output/<run_name>/
├── curator/
│   ├── <package_id>_<run_id>.json        # CuratorBundle
│   └── <package_id>_<run_id>_transcript.json  # Full API call
├── harmonizer/
│   ├── <package_id>_<run_id>.py          # Generated Python code
│   ├── <package_id>_<run_id>_mapping.json  # Generated mapping
│   └── <package_id>_<run_id>_transcript.json  # Full API call
└── result.json                            # Run summary
```

## Configuration Options

### Model Selection

- `claude-sonnet-4-5`: Latest Sonnet (recommended for experiments)
- `claude-opus-4-8`: More capable, slower, expensive
- `claude-haiku-4-5`: Faster, cheaper, less capable

### Temperature

- `1.0`: Default, allows natural variation (recommended for production diversity)
- `0.0`: More deterministic (useful for debugging)
- Higher temps increase stochasticity across runs

### Random Seed

- Used for `run_id` generation (deterministic hashing)
- Different seeds → different run IDs but same skill behavior at temp=1.0

## Cost Estimation

Rough token usage per dataset:

**Curator (Skill 1):**
- Input: ~20K tokens (skill prompt + mapping examples + metadata)
- Output: ~2K tokens (curator bundle)
- **Total: ~22K tokens per run**

**Harmonizer (Skill 2):**
- Input: ~40K tokens (skill prompt + curator bundle + exemplar code)
- Output: ~4K tokens (Python code + mapping JSON)
- **Total: ~44K tokens per run**

**End-to-end: ~66K tokens per dataset**

For 19-dataset cross-validation with 5 stochastic runs each:
- **19 datasets × 5 runs = 95 runs**
- **95 × 66K = ~6.3M tokens**

At Claude Sonnet 4.5 pricing (~$3/M input, ~$15/M output):
- Input: 6.3M × 0.7 × $3/M ≈ $13
- Output: 6.3M × 0.3 × $15/M ≈ $28
- **Total: ~$41 for full Phase A evaluation**

## Troubleshooting

### "No API key found"
Set `ANTHROPIC_API_KEY` environment variable or pass `api_key` parameter.

### "Skill definition not found"
Check that `skills/essdive_sm_curator/SKILL.md` and `skills/essdive_sm_harmonizer/SKILL.md` exist.

### "Could not extract valid CuratorBundle"
The skill output didn't match the schema. Check transcript JSON to see raw response. May need to refine skill prompt.

### "No Python code block found"
Harmonizer didn't produce properly formatted code block. Check transcript. Skill prompt may need adjustment.

### ValidationError on mapping JSON
Generated mapping doesn't match `HarmonizationMapping` schema. Common issues:
- Missing required fields (index, dataset_identifier, doi)
- Malformed harmonization_mappings structure
- Check transcript to see what was generated

## Next Steps

1. **Test on single dataset** to verify wiring
2. **Run small CV experiment** (3-5 datasets)
3. **Implement scoring metrics** (compare outputs to gold)
4. **Scale to full evaluation** (19 datasets × 5 runs)
5. **Analyze error patterns** and iterate on skill prompts

## Contact

For issues with the harness implementation, check:
- `src/harness/skill_invoker.py` - Core invocation logic
- `src/schemas/` - Schema definitions
- `skills/*/SKILL.md` - Skill prompt definitions
