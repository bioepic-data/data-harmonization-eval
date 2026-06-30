# Introduction

> **Status:** Drafted. Prose is near-final; citations use author-year keys resolved
> in `references.md`. Any forward reference to a result is marked `[[PLACEHOLDER]]`.

## The harmonization bottleneck in environmental science

Synthesizing environmental observations across studies depends on first making
heterogeneous datasets comparable — a process of *harmonization* that maps disparate
source files onto a common schema with consistent variables, units, coordinates, and
time references. For soil moisture, the variable of interest in this work, the same
physical quantity is reported as volumetric water content (in % or m³ m⁻³),
gravimetric water content (g g⁻¹), or matric/water potential (kPa, MPa, or bar);
the gravimetric-to-volumetric conversion itself requires a bulk-density value that is
frequently missing [CEOS-SM; NIDIS-2024]. Sites are georeferenced in incompatible
coordinate systems (UTM vs. latitude/longitude, differing datums), depths follow
different conventions, timestamps are recorded in assorted local time zones, and
tables arrive in both wide and long layouts. Layered on top of these mechanical
differences are scientific judgments: whether a dataset measures soil moisture
directly or derives it from a model, whether observations form a continuous sensor
time series or a discrete sampling campaign, and whether an experimental manipulation
(warming, irrigation) confounds the natural signal.

Resolving these issues is expert, labor-intensive work, and at scale it remains
largely manual. The International Soil Moisture Network — the field's canonical
harmonization effort, integrating thousands of stations to a common volumetric, UTC
standard — documents that data collection from providers is still done "either
manually (mostly by email) or is automated, depending on the degree of automation at
the data provider side" [Dorigo-2021]. Community pipelines such as AmeriFlux BASE
[Chu-2023] and FLUXNET ONEFlux [Pastorello-2020] show that turning heterogeneous
submissions into a standardized product requires substantial, purpose-built curation
infrastructure. More broadly, data practitioners report spending a large majority of
their time on data preparation and cleaning rather than analysis
[Kandel-2012; Lohr-2014]. This curation cost is a first-order bottleneck on the
reuse of the long tail of environmental data deposited in repositories such as the
U.S. Department of Energy's ESS-DIVE [Crystal-Ornelas-2022].

## LLM agents as a route to automated curation

Large language models, embedded in tool-using *agentic* workflows, have rapidly
become candidates for exactly this kind of work. Recent systems apply LLMs to data
standardization [Qi-2024], autonomous data engineering [Wang-2025],
data preprocessing [Zhang-2024], schema and entity matching [KcMF-2024], and the
generation of executable data-transformation and ETL code [TabulaX-2024;
Prompt2DAG-2025], extending a long programming-by-example lineage from FlashFill
[Gulwani-2011] and the Wrangler/Trifacta tools. Most directly related to the present
work, *Harmonia* casts data harmonization itself as LLM-agent pipeline synthesis,
mapping diverse datasets to a target schema — though it is interactive
(human-in-the-loop), demonstrated on clinical data, and not evaluated against expert
ground truth via cross-validation [Santos-2025]. In parallel, benchmarks for
LLM agents on data tasks consistently find that *end-to-end* data pipelines remain
hard: KramaBench, which spans real-world pipelines including environmental science,
reports that the best system reaches only ~55% end-to-end accuracy [KramaBench-2025].

Two further threads frame our design. First, decomposing a task across multiple
agents introduces its own failure modes; recent taxonomies of multi-agent LLM
failures emphasize inter-agent misalignment and the difficulty of *attributing* a
failure to the responsible agent [Cemri-2025]. Second, evaluating stochastic LLM
systems reliably is non-trivial: LLM-as-judge scoring is unstable
[JudgeReliability-2026], motivating automated, execution-grounded metrics with known
answers [Zhang-2025-DataSci]. Our evaluation is built around both concerns.

## This work

We study a two-agent workflow, implemented as Anthropic Agent Skills
[AgentSkills-2025], for harmonizing soil-moisture datasets from ESS-DIVE. A
**curator** agent ingests a dataset identifier, inspects the package, decides whether
and how the dataset should be harmonized, and emits a structured bundle; a
**harmonizer** agent consumes that bundle and produces (a) executable Python
transformation code and (b) a documented change-mapping. We benchmark the pair
against a domain expert who harmonized 19 Watershed Function SFA datasets, combining
retrospective grouped leave-one-out cross-validation with prospective blind
evaluation on novel datasets.

Our evaluation makes three methodological commitments designed to produce a credible,
decomposable estimate of real-world performance:

1. **Output-data equivalence as the primary endpoint.** Rather than judging code text
   or relying on an LLM judge, we *execute* both the agent's and the expert's code on
   the same raw inputs and compare the resulting tables cell-by-cell. Two correct
   harmonizations score identically regardless of how the code is written.
2. **Decomposed error attribution.** Each agent is scored in isolation, the
   harmonizer is scored under an oracle (gold) bundle, and the full pipeline is scored
   end-to-end. The gap between the oracle and end-to-end conditions quantifies how
   much curator error propagates downstream, and an explicit taxonomy attributes each
   end-to-end failure to the curator, the harmonizer, their interface, or genuine
   ambiguity.
3. **Honest generalization.** Cross-validation holds out whole source/instrument
   clusters, and a per-dataset similarity covariate converts the in-context-exemplar
   leakage risk into a measured relationship between dataset novelty and performance.

Our contributions are: (i) a formal, reproducible evaluation framework for agentic
environmental data harmonization, with an output-equivalence primary endpoint and a
cross-agent error-propagation taxonomy; (ii) retrospective and prospective estimates
of how closely the agent pair reproduces expert harmonization `[[PLACEHOLDER:
headline numbers]]`; and (iii) an analysis of where the workflow succeeds, where and
why it fails, and the dataset-novelty boundary beyond which it should defer to a human
`[[PLACEHOLDER]]`.
