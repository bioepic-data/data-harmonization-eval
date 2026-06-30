# Methods

> **Status:** Drafted from the locked evaluation design (`config/`, `src/`, `skills/`).
> All numbers, fold counts, and model identifiers are placeholders pending the
> final experimental run and should be reconciled against `config/experiment.yaml`
> and `config/cv_folds.yaml` before submission.

## 1. Overview

We evaluate a two-agent large language model (LLM) workflow that automates the
harmonization of heterogeneous soil-moisture datasets into a single analysis-ready
schema. The workflow is a *curator* agent (Skill 1) followed by a *harmonizer*
agent (Skill 2). The curator ingests a dataset identifier, retrieves and inspects
the package, makes an inclusion/exclusion decision, and emits a structured bundle;
the harmonizer consumes that bundle and emits (a) executable Python transformation
code and (b) a documented change-mapping. We measure how well this pair reproduces
the work of a domain expert, both retrospectively (cross-validation against a fixed
gold standard) and prospectively (blind comparison on previously unseen datasets).

The design has three deliberate properties:

1. **Output-centric scoring.** The primary endpoint is *output-data equivalence* —
   the harmonized table produced by the agent's code is compared cell-by-cell with
   the table produced by the expert's code on the *same* raw inputs. Two correct
   harmonizations score identically even if the underlying Python differs entirely,
   so we measure *what the code does*, not how it is written.
2. **Decomposable error attribution.** Each skill is scored in isolation and the
   pipeline is scored end-to-end, allowing us to separate curator error from
   harmonizer error and to quantify error propagation between the two agents.
3. **Honest generalization estimates.** Cross-validation holds out whole
   source/instrument clusters, and a per-dataset similarity covariate converts the
   in-context-exemplar leakage risk into a measured effect rather than an
   uncontrolled confound.

## 2. The agent pair under evaluation

Both agents are implemented as Anthropic *Agent Skills* — versioned instruction
bundles (system prompt plus reference context) invoked inside an agentic
tool-using loop. Skill versions are pinned per run (`skill1_version`,
`skill2_version` in `config/experiment.yaml`).

### 2.1 Skill 1 — Curator (`essdive_sm_curator`)

Given one or more DOIs / ESS-DIVE package identifiers, the curator:

- normalizes identifiers and retrieves package metadata (local cache first, then
  the ESS-DIVE API);
- classifies each file into *data payload*, *location metadata*, *sensor metadata*,
  or *documentation*;
- inspects payload headers to locate timestamp, moisture (VWC / GWC / water
  potential), depth, site, and replicate columns;
- resolves site coordinates through a fixed fallback cascade (payload → ancillary
  file → package metadata → external location registry → unresolvable), assigning a
  `qc_flag` recommendation;
- infers time-series vs. discrete sampling and, for time series, a sampling
  interval;
- detects experimental manipulations (warming, irrigation, fertilization, etc.) and
  recommends include / exclude / flag;
- selects the most structurally similar gold exemplar; and
- emits a structured **curator bundle** (`src/schemas/skill1_bundle.py`) with an
  `INCLUDE` / `EXCLUDE` / `FLAG_FOR_REVIEW` decision and a list of open questions.

### 2.2 Skill 2 — Harmonizer (`wfsfa_sm_harmonization`)

Given a curator bundle (or an operator-supplied equivalent), the harmonizer:

- re-confirms the inclusion decision under a strict rule set;
- maps each source variable to the target schema, including unit conversions;
- resolves location, depth encoding, timestamp format/timezone, and replicate
  encoding;
- generates a Python code block following fixed conventions (shared helper
  functions, wide-to-long reshaping, UTC conversion, column-order enforcement); and
- emits a JSON **change-mapping** entry (`src/schemas/skill2_mapping.py`)
  documenting every transformation with source pattern, destination variable,
  transformation description, and unit conversion.

### 2.3 Target schema

Every harmonized table must contain exactly nine columns
(`src/schemas/target_schema.py`):

`datetime_UTC`, `site_id`, `depth_m`, `replicate`, `is_timeseries`,
`interval_min`, `volumetric_water_content_m3_m3`,
`gravimetric_water_content_gH2O_gs`, `water_potential_kPa`.

Canonical units are meters (depth), m³ m⁻³ (VWC), g H₂O g⁻¹ soil (GWC), and kPa
(water potential, negative). A controlled `qc_flag` vocabulary records depth
approximation (`d1`) and coordinate provenance (`g1` retrieved from an external
registry, `g2` unresolvable). Schema conformance is validated programmatically
(column presence/exclusivity, dtypes, value ranges, required-field non-nullity).

## 3. Ground truth

The reference standard is a corpus of **19 expert-harmonized** Watershed Function
SFA (WFSFA) soil-moisture datasets drawn from ESS-DIVE. For each, the expert
produced (a) a harmonized output table, (b) modular, documented Python
transformation code (`data/gold/expert_code/harmonize_sm/`, one
`dataset_NN.py` per dataset plus shared `common.py`), and (c) a structured +
free-text change-mapping (`data/gold/sm_data_harmonization_mapping.json`). The
mapping file also encodes excluded datasets with their plain-language exclusion
reasons, providing gold labels for the curator's decision task.

> **TODO (results-time):** confirm the exact count of *included* vs. *excluded*
> datasets in the final gold set and report it here; the mapping JSON currently
> enumerates indices 0–27 with several excluded/auxiliary entries.

## 4. Study design

The study has two phases; within each, the agent pair is evaluated in three modes.

### 4.1 Phase A — Retrospective cross-validation

We perform **grouped leave-one-out cross-validation** over the gold datasets.
Datasets are grouped into source/instrument **clusters** (`config/cv_folds.yaml`)
so that datasets sharing a lab, site, or instrument family are held out together;
this prevents a near-duplicate sibling from leaking into the exemplar pool and
inflating apparent performance. For each fold, the held-out dataset(s) are
harmonized using only the *other* datasets as exemplars, and outputs are scored
against the expert version.

Phase A serves a second purpose: it **validates the automated metrics** against
expert judgment. If automated output-equivalence scoring agrees with an expert
rubric on the gold data, we can rely on the cheaper automated scoring in Phase B.

### 4.2 Phase B — Prospective blind evaluation

Using all gold datasets as exemplars, the agent harmonizes genuinely new ESS-DIVE
datasets. In parallel and blind to the agent's output, the domain expert harmonizes
the same datasets; the expert output becomes the reference. This estimates
real-world deployment performance on data neither the agent nor the expert has
previously processed.

### 4.3 Evaluation modes

Both phases score the system three ways to localize error:

1. **Skill 1 in isolation** — the curator bundle is scored field-by-field against
   expert labels.
2. **Skill 2 with oracle input** — the harmonizer is fed the *correct* (gold)
   curator bundle, so transformation quality is measured independently of curator
   error.
3. **End-to-end** — the full pipeline runs and errors propagate. The gap between
   modes (2) and (3) quantifies how much curator error degrades the final output.

### 4.4 Baselines and controls

- **Non-agentic single-call LLM** — one prompt, no skill structure or tool loop.
- **No-exemplars agent** — the agent with the gold exemplars removed, isolating the
  value of the 19 references.
- **Naïve heuristic** — a string-matching baseline.
- **Similarity covariate** — for each evaluation dataset we compute similarity to
  its nearest available exemplar and model it explicitly, turning a leakage risk
  into a reported finding ("performance holds up to similarity *X*, then degrades").
- **Reproducibility controls** — model ID/version, both skill versions, sampling
  parameters, and random seed are pinned per run (`config/experiment.yaml`).

> **TODO (results-time):** record the exact model identifier and version actually
> used (config currently pins a Claude model), temperature, `max_tokens`, and the
> number of stochastic repeats per dataset/mode (`n_stochastic_runs`).

## 5. Metrics

All scoring lives in `src/metrics/` and is phase-agnostic.

### 5.1 Skill 1 (curator)

Decision accuracy / precision / recall / F1 over `INCLUDE` / `EXCLUDE` / `FLAG`;
file-set precision/recall/F1 for payload, location, and sensor files; time-series
binary accuracy and sampling-interval numeric error; location-source and `qc_flag`
accuracy; manipulation-detection accuracy; exemplar-selection match quality; and
deferral (FLAG) calibration against expert confidence. A composite curator score
aggregates these with fixed, versioned weights (`config/metrics_weights.yaml`).

### 5.2 Skill 2 (harmonizer)

- **Primary endpoint — output-data equivalence.** Agent and expert code are each
  executed on the same raw inputs in a sandbox; the resulting tables are aligned on
  the natural key (`datetime_UTC`, `site_id`, `depth_m`, `replicate`) and compared.
  We report row-alignment precision/recall/F1 and per-column cell agreement
  (numeric columns within a float tolerance; categorical columns by exact match),
  with sub-scores for datetime, coordinate, depth, and unit-conversion accuracy.
- **Schema conformance** — columns, dtypes, ranges, required fields.
- **Semantic mapping accuracy** — precision/recall/F1 of the change-mapping against
  the expert's, over a controlled transformation-type vocabulary.
- **Code executability** — does the generated code run and reproduce its claimed
  output.
- **Documentation completeness** — does the change-mapping cover all and only the
  actual transformations.
- **Ontology / controlled-vocabulary validity** — correct use of schema terms and
  `qc_flag` codes.

A composite harmonizer score weights output equivalence most heavily
(`config/metrics_weights.yaml`).

### 5.3 End-to-end

Task success (output equivalence above threshold) plus an **error-propagation
taxonomy** classifying each failure as (i) Skill-1 error propagated, (ii) Skill-2
error given correct input, (iii) inter-skill interface inconsistency, or (iv)
genuinely ambiguous (expert also uncertain). Classification logic is in
`src/analysis/error_taxonomy.py`.

## 6. Statistical analysis

The data are nested: stochastic runs within datasets within source-clusters. To
avoid inflating the effective sample size we:

- report **cluster-level bootstrap confidence intervals** (resampling clusters, not
  individual runs);
- fit **mixed-effects models** with dataset and cluster as random effects and mode
  and similarity as fixed effects
  (`metric ~ mode + similarity + (1|dataset) + (1|cluster)`);
- report the **error-propagation gap** (oracle minus end-to-end) as a paired
  difference with a cluster-bootstrap CI;
- emphasize **effect sizes with CIs** over *p*-values, given the small number of
  gold datasets (N ≈ 19); and
- report the **distribution across stochastic repeats** (variance, and pass@k where
  appropriate), not only means.

Inter-rater reliability between automated metrics and the expert rubric is reported
for the metric-validation analysis (`src/analysis/irr.py`).

## 7. Reproducibility and provenance

Per-run artifacts (raw agent outputs, scored tidy CSVs, figures, tables) are written
under `results/`. Each run records the model identifier/version, both skill
versions, sampling parameters, and the random seed. The gold corpus is treated as
read-only. Code execution occurs in a sandbox (`src/execution/sandbox.py`) and
output comparison in `src/execution/output_loader.py`.

> **Reporting checklist (fill at results-time):** model + version; skill versions;
> temperature / sampling; seeds; `n_stochastic_runs`; number of folds and held-out
> clusters; counts of included/excluded gold datasets; number and provenance of
> prospective (Phase B) datasets; software/library versions; total compute / token
> budget.
