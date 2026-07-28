# Evaluating an LLM Agent Workflow for Environmental Data Harmonization

## Overview
This repository stores a formal evaluation framework for an LLM agent workflow 
(curator + harmonizer) that automates environmental data harmonization. Evaluation 
case is the corpus of soil moisture data published on the US DOE ESS-DIVE repository. 
Combines retrospective leave-one-out cross-validation against expert ground truth with 
prospective blind evaluation on novel datasets.

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
and (c) a free-text + structured change-mapping JSON. These constitute our
reference standard.

## Design Overview

The study has two phases, and within each phase the skills are evaluated three ways.

### Phases

**Phase A — Retrospective cross-validation \[ground truth\]**
We perform grouped leave-one-out cross-validation over the 19 expert-harmonized
datasets. For each held-out dataset, the agent sees only the *other* datasets as
exemplars and must harmonize the held-out one from its identifier alone. Outputs
are scored against the expert's version. Because datasets may cluster by source,
lab, or instrument, we hold out whole clusters where appropriate ("grouped" CV)
to give an honest generalization estimate.

**Phase B — Prospective evaluation \[novel data\]**
Using all 19 as exemplars, the agent harmonizes genuinely new ESS-DIVE datasets.
In parallel and blind, the domain expert harmonizes the same datasets; their
output becomes the reference. This estimates real-world deployment performance.

Phase A also *validates our automated metrics* against expert judgment; if the
two agree well, we can lean on cheap automated scoring in Phase B.

### Evaluation Modes (both phases)

1. **Skill 1 in isolation** — curator output scored field-by-field against expert
   labels (decision, file selection, time-series inference, location resolution,
   exemplar match, calibration of FLAG/defer decisions).
2. **Skill 2 with oracle input** — harmonizer fed the *correct* curator bundle, so
   transformation quality is measured independently of curator errors.
3. **End-to-end** — full pipeline; errors propagate. The gap between (2) and (3)
   quantifies how much curator error degrades the output.

## Metrics

**Skill 1 (curator):** decision accuracy / precision / recall / F1; file-set
precision/recall/F1 (payload, location, sensor); time-series binary accuracy;
interval numeric error; manipulation-detection accuracy; qc_flag accuracy;
exemplar-selection quality.

**Skill 2 (harmonizer):**
- **Primary endpoint — output-data equivalence:** run agent and expert code on the
  same raw data, compare resulting tables cell-by-cell.
- Schema conformance and ontology/controlled-vocabulary validity.
- Semantic mapping accuracy (precision/recall over a controlled transformation-type
  vocabulary).
- Code executability (does it run and reproduce its claimed output).
- Documentation completeness (change-mapping covers all and only the actual
  transformations).

**End-to-end:** task success plus an **error-propagation taxonomy** classifying
each failure as (i) Skill-1 error propagated, (ii) Skill-2 error given correct
input, (iii) inter-skill spec inconsistency, or (iv) genuinely ambiguous case.

## Statistics

Data are nested: stochastic runs within datasets within source-clusters. We use
mixed-effects models (dataset and cluster as random effects) and cluster-level
bootstrap confidence intervals, reporting effect sizes with CIs rather than
relying on p-values given the small N (19). The error-propagation gap is reported
as a paired difference with a bootstrap CI. We report distribution across
stochastic repeats (variance, and pass@k where appropriate), not just means.

## Controls and Confounds

- **Baselines:** non-agentic single-call LLM; agent with exemplars removed
  (isolates the value of the 19 references); naive string-matching heuristic.
- **Similarity covariate:** each evaluation dataset's similarity to its nearest
  exemplar is computed and modeled, converting a leakage risk into a finding
  ("the agent generalizes up to similarity X, then degrades").
- **Reproducibility:** model version, skill version, and seeds are pinned per run.

## Repository Structure

```
wfsfa-harmonization-eval/
├── config/                      # Experiment configuration
│   ├── experiment.yaml          # Global settings, model params, paths
│   ├── cv_folds.yaml            # Cross-validation fold definitions
│   └── metrics_weights.yaml     # Composite metric weights
│
├── data/                        # Data directories
│   ├── gold/                    # 19 expert-harmonized datasets (READ-ONLY)
│   │   ├── harmonized_outputs/  # Expert harmonized CSVs
│   │   ├── expert_code/         # Expert Python code
│   │   └── expert_mappings.json # Expert change-mappings (ground truth)
│   ├── prospective/             # Novel datasets for Phase B
│   ├── raw_cache/               # Cached ESS-DIVE packages
│   └── cluster_metadata.csv     # Dataset clustering for grouped CV
│
├── src/                         # Core implementation
│   ├── schemas/                 # Pydantic data models
│   │   ├── skill1_bundle.py     # Curator output schema
│   │   ├── skill2_mapping.py    # Harmonizer output schema
│   │   ├── target_schema.py     # Target harmonized schema
│   │   └── target_schema.yaml   # LinkML version of the target schema
│   │
│   ├── harness/                 # Skill runners
│   │   ├── run_skill1.py        # Curator runner
│   │   ├── run_skill2.py        # Harmonizer runner
│   │   ├── run_pipeline.py      # End-to-end runner
│   │   ├── exemplar_selection.py # Exemplar matching logic
│   │   └── oracle.py            # Oracle bundle creation
│   │
│   ├── execution/               # Code execution
│   │   ├── sandbox.py           # Safe code execution
│   │   └── output_loader.py     # Load and compare outputs
│   │
│   ├── metrics/                 # ALL scoring logic (phase-agnostic)
│   │   ├── skill1_metrics.py    # Curator metrics
│   │   ├── skill2_output_equiv.py # PRIMARY: data equivalence
│   │   ├── skill2_structural.py # Schema conformance
│   │   ├── skill2_semantic.py   # Mapping accuracy
│   │   ├── skill2_executability.py # Code runs?
│   │   └── composite.py         # Weighted aggregation
│   │
│   └── analysis/                # Statistical analysis
│       ├── stats.py             # Bootstrap CIs, mixed models
│       ├── error_taxonomy.py    # Error source classification
│       ├── similarity.py        # Similarity covariate
│       └── irr.py               # Inter-rater reliability
│
├── experiments/                 # Experiment orchestration
│   ├── phase_a_crossval.py      # Phase A: cross-validation
│   ├── phase_b_prospective.py   # Phase B: novel data
│   └── metric_validation.py     # Validate automated vs expert scores
│
├── examples/                    # LinkML schema example instances
│   ├── valid/                   # Instances that MUST validate
│   └── invalid/                 # Counter-examples that MUST fail
│
├── project/                     # Generated LinkML artifacts (do not edit)
│   ├── pydantic/                # gen-pydantic output
│   └── jsonschema/              # gen-json-schema output
│
├── results/                     # Outputs
│   ├── raw_runs/                # Per-run outputs
│   ├── scored/                  # Scored metrics (tidy CSV)
│   ├── figures/                 # Plots
│   └── tables/                  # Summary tables
│
├── notebooks/                   # Analysis notebooks
│   ├── 01_explore_gold.ipynb
│   ├── 02_results_phaseA.ipynb
│   └── 03_results_phaseB.ipynb
│
└── tests/                       # Unit tests
    └── test_metrics.py          # Known-answer test cases
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

### Phase A: Cross-Validation

```bash
# Run all CV folds (all modes, all runs)
python experiments/phase_a_crossval.py

# Results written to:
#   results/scored/phase_a_results.csv
```

### Phase B: Prospective Evaluation

```bash
# Step 1: Run agent on novel datasets
python experiments/phase_b_prospective.py

# Step 2: Expert independently harmonizes same datasets
# (manual step)

# Step 3: Score agent vs expert
python experiments/phase_b_prospective.py --score \
    --agent-results results/scored/phase_b_agent_outputs.csv \
    --expert-harmonizations data/prospective/expert_blind/
```

### Metric Validation

```bash
# Correlate automated metrics vs expert rubric
python experiments/metric_validation.py
```

## Deliverables

1. **Tidy scored results** (CSV): one row per run with all metrics
2. **Phase-level summaries** (tables): mean ± CI per mode
3. **Metric validation** (correlation): automated vs expert rubric
4. **Error-propagation taxonomy** (table): failure attribution
5. **Similarity-performance relationship** (plot + regression)

## Citation

(TBD - paper under preparation)

## License

MIT