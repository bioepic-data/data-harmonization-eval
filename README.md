# Evaluating an LLM Agent Workflow for Environmental Data Harmonization

## Overview
This repository evaluates an AI curator-and-harmonizer workflow on soil-moisture
data published through DOE ESS-DIVE. Its active evaluation method is
**leave-one-cluster-out ablation**: each agent run receives a self-contained
environment with the held-out datasets removed from its exemplar mapping and
expert-code references.

The repository builds and audits those isolated environments. It does not
currently contain an automated, in-repository scoring or aggregation pipeline;
gold-based comparison is performed outside the agent environment.

## Motivation

Harmonizing heterogeneous soil moisture datasets into a common schema is a
labor-intensive task requiring domain expertise: deciding whether a dataset
qualifies, locating the right files, resolving coordinates, inferring sampling
design, and writing correct, well-documented transformation code. We have built
a set of LLM "skills" that automate this workflow: a **curator** (Skill 1)
that evaluates a dataset from its identifier and prepares structured inputs, and
a **harmonizer** (Skill 2) that produces transformation code and a documented
change-mapping. This study formally evaluates how well this agent pair performs
on data it has not seen.

## Ground Truth

Nineteen WFSFA soil moisture datasets have been harmonized by a domain expert,
each with (a) the harmonized output, (b) documented Python transformation code,
and (c) a structured change-mapping JSON. The gold code is held under
`data/gold/expert_code/`; 50-row output examples are under
`data/gold/expert_snippets/`; and the mapping is
`data/gold/sm_data_harmonization_mapping.json`.

## Leave-One-Cluster-Out Workflow

```
gold mapping + expert code + skills
              │
              ▼
        build_env.py
              │
              ▼
 isolated fold workspace
 ablated references + held-out raw inputs
              │
              └──── AI agent runs ───────────┘
                            │
                            ▼
                 output/ artifacts + tool trace
                            │
                            ▼
                  invigilator audit (post-run)
                            │
                            ▼
             external gold-based scoring and analysis
```

### What the fold modules do

- `src/folds/stage_raw_data.py` stages raw ESS-DIVE inputs into the fold's
  `inputs/raw/<dataset_identifier>/` directory. Raw held-out data are task
  inputs and are permitted.
- `src/folds/expert_harmonizer.py` resolves holdouts and determines which expert
  modules remain available as exemplars.
- `src/folds/build_env.py` creates an answer-free environment outside the
  repository, copies the skills,
  filters held-out entries from the mapping, copies only non-held-out expert-code
  modules, and writes `MANIFEST.json` plus `AGENT_INSTRUCTIONS.md`.
- `src/folds/invigilator.py` audits an agent tool-call JSONL trace after the run.
  It permits access only inside the fold environment, then flags reads outside
  that boundary.

The fold environment intentionally excludes the held-out answer. Gold-output
comparison must therefore happen outside the environment, after the agent run.

### AI-agent prompt and outputs

The agent must start in the generated fold directory, read its manifest and
instructions, use only its ablated references plus raw inputs, and write all
deliverables under `output/`:

```text
You are running a leave-one-cluster-out harmonization evaluation.

cd /tmp/data-harmonization-eval-runs/<fold-id>

Read AGENT_INSTRUCTIONS.md and MANIFEST.json. Harmonize the held-out dataset(s)
using only skills/, the filtered mapping, the non-held-out expert-code patterns,
and raw inputs under inputs/raw/. Write harmonized CSVs, generated transformation code,
the change-mapping JSON, and decision notes to output/. Do not read root gold
data, root processed data, or any other fold environment.
```

`AGENT_INSTRUCTIONS.md` supplies the exact held-out identifiers and allowed
paths for each fold. The GitHub workflow uses the same instruction pattern for
the configured Claude agent.

## Repository Structure

```
wfsfa-harmonization-eval/
├── config/
│   └── cv_folds.yaml            # Cluster definitions and holdout membership
│
├── data/
│   ├── gold/                    # Read-only reference material
│   │   ├── expert_code/         # common.py + dataset_NN.py modules
│   │   ├── expert_snippets/     # Short ideal-output examples
│   │   └── sm_data_harmonization_mapping.json
│   └── raw_cache/               # Source URLs and local raw-data cache
│
├── skills/                      # Curator and harmonizer AI skill instructions
│
├── src/
│   ├── folds/                   # Stage, build, and audit fold environments
│   └── schemas/                 # Target schema and agent-output models
│
├── .github/workflows/run-eval.yml # Manually dispatched Claude evaluation
├── examples/                    # LinkML validation examples
├── project/                     # Generated LinkML artifacts
└── tests/                       # Fold, staging, audit, and schema tests
```

## LinkML Target Schema

The canonical 9-column harmonized schema is also defined declaratively in
[`src/schemas/target_schema.yaml`](src/schemas/target_schema.yaml), a
[LinkML](https://linkml.io) schema equivalent to `target_schema.py`. It is the
single source of truth for two committed, generated artifacts:

- `project/pydantic/target_schema.py` — Pydantic v2 models (`gen-pydantic`)
- `project/jsonschema/target_schema.schema.json` — JSON Schema (`gen-json-schema`)

Example instances live under `examples/`: everything in `examples/valid/` must
validate against the schema, and every counter-example in `examples/invalid/`
must fail (one per constraint — missing required field, out-of-range value,
wrong type, and the "at least one moisture variable" rule).

```bash
pip install -e ".[linkml]"   # install the LinkML toolchain

make gen      # regenerate the pydantic + JSON Schema artifacts
make test     # lint the schema + validate all examples + run pytest checks
```

CI (`.github/workflows/linkml.yml`) runs the same checks and fails if the
committed artifacts under `project/` drift from the schema. The pytest wrapper
(`tests/test_target_schema_examples.py`) runs as part of the normal test suite
when `linkml` is installed and is skipped otherwise.

## Installation

```bash
# Clone repository
cd ~/Repos/wfsfa-harmonization-eval

# Install dependencies
pip install -e .

# Or with poetry
poetry install
```

## Usage

### Run a fold locally

```bash
# Create an isolated environment for a cluster or a comma-separated holdout.
uv run python -m src.folds.build_env \
  --holdout 15,26 \
  --name fold-02-holdout-15-26

# Optionally stage held-out raw inputs into the fold environment.
uv run python -m src.folds.stage_raw_data --indices 15,26 \
  --dest /tmp/data-harmonization-eval-runs/fold-02-holdout-15-26/inputs/raw \
  --drive-method public
```

Give the AI agent the prompt in [AI-agent prompt and outputs](#ai-agent-prompt-and-outputs),
substituting the fold name. The agent writes its deliverables to:

```text
/tmp/data-harmonization-eval-runs/fold-02-holdout-15-26/output/
```

If your agent provider records tool calls as JSONL, audit the run afterward:

```bash
uv run python -m src.folds.invigilator \
  --trace path/to/agent-trace.jsonl \
  --env /tmp/data-harmonization-eval-runs/fold-02-holdout-15-26
```

### Run through GitHub Actions

In GitHub Actions, run **Run Harmonization Eval** manually. Supply a dataset
index, dataset identifier, comma-separated indices, or a cluster ID/name from
`config/cv_folds.yaml`. The workflow builds the fold, optionally stages raw
data, starts the configured Claude agent with the fold-specific prompt, and
replaces the checkout with the answer-free fold workspace, then uploads it as
an `eval-<fold-id>` artifact.

### Results and scoring

The active workflow does not write to a shared `results/` directory or commit
run outputs. Local results remain under the isolated fold's `output/`; GitHub runs
are retained as workflow artifacts. Use a separate trusted process, outside the
fold environment, to compare those outputs with the held-out gold standard and
to aggregate performance metrics.

## Citation

(TBD - paper under preparation)

## License

MIT
