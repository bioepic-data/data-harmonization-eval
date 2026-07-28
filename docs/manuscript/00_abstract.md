# Abstract

> **Status: SCAFFOLD.** To be written last, once results exist. Target ~200–250
> words. Numbers are `[[PLACEHOLDER]]`.

**Motivation.** Harmonizing heterogeneous environmental datasets into analysis-ready
form is a labor-intensive, expertise-bound bottleneck in Earth-science synthesis.
`[[1–2 sentences on the soil-moisture harmonization problem and its cost.]]`

**Approach.** We evaluate a two-agent large language model (LLM) workflow — a
*curator* that ingests a dataset identifier and decides what and how to harmonize,
and a *harmonizer* that generates executable transformation code and a documented
change-mapping — on soil-moisture datasets from the DOE ESS-DIVE repository. We
benchmark it against a domain expert who harmonized 19 Watershed Function SFA
datasets, using grouped leave-one-out cross-validation (retrospective) and blind
prospective evaluation on novel datasets. Our primary endpoint is *output-data
equivalence*: agent and expert code are executed on identical raw inputs and the
resulting tables are compared cell-by-cell, so two correct harmonizations score
equally regardless of coding style. We additionally score each agent in isolation,
the harmonizer under an oracle bundle, and the full pipeline, enabling explicit
attribution of error between the two agents.

**Results.** `[[PLACEHOLDER: headline end-to-end output equivalence; per-skill
performance; error-propagation gap; dominant failure mode; comparison to
single-call and no-exemplar baselines; similarity-generalization threshold.]]`

**Conclusions.** `[[PLACEHOLDER: the workflow can/cannot reliably draft expert-grade
harmonizations; recommended human-in-the-loop operating point; implications for
scaling FAIR environmental data curation.]]`
