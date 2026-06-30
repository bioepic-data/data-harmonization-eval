# Harness Implementation Summary

This document summarizes the implementation of the skill invocation infrastructure for the data harmonization evaluation framework.

## What Was Implemented

### Core Infrastructure

**`src/harness/skill_invoker.py`** - New file
- `SkillInvoker` class: Manages Claude API invocations for skills
- Key features:
  - Loads skill definitions from `skills/*/SKILL.md` files
  - Parses YAML frontmatter and extracts system prompts
  - Prepares context files (auto-filters mapping JSON by exemplar pool)
  - Invokes Claude API with proper parameters
  - Validates outputs against Pydantic schemas
  - Handles JSON extraction from various response formats

### Skill 1 (Curator) Wiring

**`src/harness/run_skill1.py`** - Updated
- `invoke_curator()` now fully implemented (was placeholder)
- Builds curator-specific prompts
- Invokes `essdive_sm_curator` skill via API
- Validates output as `CuratorBundle`
- Saves bundle JSON + full transcript for audit
- Returns validated bundle ready for Skill 2

### Skill 2 (Harmonizer) Wiring

**`src/harness/run_skill2.py`** - Updated
- `invoke_harmonizer()` now fully implemented (was placeholder)
- Loads exemplar code from `data/gold/expert_code/`
- Prioritizes similar dataset code (from curator bundle)
- Invokes `essdive_sm_harmonizer` skill via API
- Extracts Python code and mapping JSON separately
- Validates both outputs against schemas
- Saves code + mapping + transcript

### Pipeline Orchestration

**`src/harness/run_pipeline.py`** - Already complete
- `run_end_to_end()` orchestrates curator → harmonizer flow
- Handles INCLUDE/EXCLUDE/FLAG_FOR_REVIEW branches
- No changes needed (placeholders now wired up)

### Dependencies

**`pyproject.toml`** - Updated
- Added `anthropic>=0.18.0` to dependencies

### Documentation

**`RUNNING_EXPERIMENTS.md`** - New file
- Comprehensive guide for running experiments
- Architecture diagram
- Example scripts for different experiment types
- Cost estimation
- Troubleshooting guide

**`test_harness.py`** - New file
- Validation test suite
- Tests skill loading, context preparation, schemas, gold data
- Can run without API key to verify infrastructure
- Returns actionable next steps

## Key Design Decisions

### 1. Skills as Self-Contained Definitions

Skills are defined in `skills/*/SKILL.md` with:
- YAML frontmatter (metadata, version, context dependencies)
- System prompt (after `# SYSTEM PROMPT` marker)

This makes skills:
- Version-controlled
- Human-readable
- Easy to iterate on
- Decoupled from harness code

### 2. Exemplar Pool Filtering

The `exemplar_pool` parameter controls which datasets the skill can see:
- **Curator**: Filters mapping JSON to only show exemplar indices
- **Harmonizer**: Filters exemplar code files to only show available datasets

This is **critical for cross-validation**: held-out dataset must NOT be in pool.

### 3. Output Validation

All skill outputs are validated against Pydantic schemas:
- **Skill 1**: `CuratorBundle` (defined in `src/schemas/skill1_bundle.py`)
- **Skill 2**: `Skill2Output` with embedded `HarmonizationMapping`

Benefits:
- Catches malformed outputs early
- Provides clear error messages
- Ensures downstream scoring can proceed
- Documents exact contract between skills

### 4. Audit Trail

Every invocation saves:
- **Bundle/output JSON**: Validated result
- **Transcript JSON**: Full API call (prompt, response, usage)

This enables:
- Debugging when outputs don't match expected format
- Cost analysis (token usage tracking)
- Skill prompt iteration (see what worked/didn't work)
- Reproducibility verification

### 5. Dual Output Extraction (Skill 2)

Harmonizer produces TWO artifacts in one response:
1. Python code block
2. JSON mapping block

The implementation:
- Extracts Python from ```python blocks
- Extracts JSON from ```json blocks or raw JSON objects
- Validates JSON against `HarmonizationMapping` schema
- Packages both in `Skill2Output`

This reduces API calls (one invocation vs. two separate calls).

## Usage Pattern

### For Single Dataset Test

```python
from pathlib import Path
from src.harness.run_skill1 import invoke_curator

bundle = invoke_curator(
    identifier="doi:10.15485/2566877",
    exemplar_pool=[0, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    skill_version="0.1",
    model_id="claude-sonnet-4-5",
    random_seed=42,
    output_dir=Path("output/test"),
)

print(f"Decision: {bundle.curator_decision}")
```

### For Cross-Validation Loop

```python
from pathlib import Path
from src.harness.run_pipeline import run_end_to_end

for held_out in range(1, 28):
    exemplar_pool = [i for i in range(1, 28) if i != held_out]
    
    result = run_end_to_end(
        identifier=f"doi:10.15485/...",  # lookup DOI
        exemplar_pool=exemplar_pool,
        config=config,
        output_dir=Path(f"output/cv/dataset_{held_out:02d}"),
        run_index=0,
    )
```

### For Running from Another Claude Instance

The entire experiment can be orchestrated by another Claude instance:

```python
# Claude instance orchestrating the evaluation
import subprocess

# 1. Set up environment
subprocess.run(["export", "ANTHROPIC_API_KEY=sk-..."])

# 2. Run validation
result = subprocess.run(["python", "test_harness.py"])
if result.returncode != 0:
    raise RuntimeError("Harness validation failed")

# 3. Run cross-validation
result = subprocess.run(["python", "run_cv_experiment.py"])

# 4. Analyze results
# ... scoring logic ...
```

Or invoke directly as a Python subprocess with proper context.

## Testing the Implementation

### Step 1: Validate Infrastructure

```bash
python test_harness.py
```

This checks:
- ✓ Skills can be loaded
- ✓ Context files are accessible
- ✓ Schemas are valid
- ✓ Gold data is present

### Step 2: Test with Real API (Optional)

```bash
export ANTHROPIC_API_KEY='your-key'
python -c "
from pathlib import Path
from src.harness.run_skill1 import invoke_curator

bundle = invoke_curator(
    identifier='doi:10.15485/2566877',
    exemplar_pool=[0, 2, 3],
    skill_version='0.1',
    model_id='claude-sonnet-4-5',
    random_seed=42,
    output_dir=Path('output/api_test'),
)
print(f'Success! Decision: {bundle.curator_decision}')
"
```

## File Changes Summary

### New Files
- `src/harness/skill_invoker.py` (353 lines)
- `RUNNING_EXPERIMENTS.md` (340 lines)
- `test_harness.py` (310 lines)
- `HARNESS_IMPLEMENTATION.md` (this file)

### Modified Files
- `src/harness/run_skill1.py` (replaced placeholder with real implementation)
- `src/harness/run_skill2.py` (replaced placeholder with real implementation)
- `pyproject.toml` (added anthropic dependency)

### Unchanged (Already Complete)
- `src/harness/run_pipeline.py`
- `src/schemas/skill1_bundle.py`
- `src/schemas/skill2_mapping.py`
- `skills/essdive_sm_curator/SKILL.md`
- `skills/essdive_sm_harmonizer/SKILL.md`

## Next Steps

1. **Validate**: Run `python test_harness.py` to verify infrastructure

2. **Test API**: Try a single curator invocation with real API key

3. **Create gold curator bundles**: Build `ExpertCuratorLabels` for all 19 datasets
   - Needed for Skill 1 evaluation metrics
   - Can be derived from existing `sm_data_harmonization_mapping.json`

4. **Implement scoring**: 
   - `src/scoring/skill1_metrics.py` - Curator evaluation
   - `src/scoring/skill2_metrics.py` - Harmonizer evaluation

5. **Run small pilot**: Test 3-5 datasets with exemplar pool filtering

6. **Full cross-validation**: 19 datasets × 5 stochastic runs

7. **Analysis**: Error patterns, success rates, skill prompt iteration

## Cost Considerations

At current skill prompt sizes:
- **Curator**: ~22K tokens/run (~$0.05/run)
- **Harmonizer**: ~44K tokens/run (~$0.10/run)
- **End-to-end**: ~$0.15/dataset

Full Phase A (19 datasets × 5 runs):
- **~$14 total** (very affordable)

Costs scale linearly with:
- Number of datasets
- Number of stochastic runs per dataset
- Context size (exemplar pool, skill prompts)

## Architecture Benefits

### Modularity
- Skills are independent, versioned documents
- Harness is generic (works with any SKILL.md)
- Schemas enforce contracts

### Reproducibility
- Deterministic run IDs (hash of identifier + seed)
- Full transcripts saved
- Model, temperature, seed all logged

### Debuggability
- Transcripts show exact prompts + responses
- Schema validation provides clear error messages
- Exemplar filtering is explicit and verifiable

### Extensibility
- New skills: just add `skills/<name>/SKILL.md`
- New schemas: add to `src/schemas/`
- New metrics: add to `src/scoring/`

## Known Limitations

1. **Simple YAML parser**: `skill_invoker.py` uses basic YAML parsing
   - Works for current skill frontmatter
   - Could use `pyyaml` for complex YAML features

2. **Single-turn invocations**: Each skill gets one prompt → one response
   - No back-and-forth conversation
   - Could extend to multi-turn if needed

3. **No caching**: Each invocation makes fresh API call
   - Could cache skill definitions
   - Could use Claude's prompt caching feature

4. **Error recovery**: If skill output is malformed, invocation fails
   - Could add retry logic
   - Could add output repair prompts

These are intentional simplifications for v1. Can extend as needed.

## Questions?

For implementation questions:
- Check `src/harness/skill_invoker.py` docstrings
- Review `RUNNING_EXPERIMENTS.md` examples
- Run `python test_harness.py` to validate setup
