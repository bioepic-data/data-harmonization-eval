# Manuscript

Working drafts for the paper describing this study:
**Evaluating an LLM Agent Pair for Environmental Data Harmonization.**

> **Status: pre-results scaffold (2026-06).** The methods and background are
> drafted; results, discussion, and the abstract contain `[[PLACEHOLDER]]` markers
> to be filled once the experimental pipeline (`experiments/`) has produced scored
> outputs under `results/`. Nothing here reports a number that the analysis code has
> not yet generated.

## Files

| File | Section | Status |
|---|---|---|
| `00_abstract.md` | Abstract | Scaffold — write last |
| `01_introduction.md` | Introduction & motivation | Drafted (cited) |
| `02_background.md` | Background / related work | Drafted (cited) |
| `03_methods.md` | Methods | Drafted from locked design |
| `04_results.md` | Results | Scaffold — tables/figures stubbed |
| `05_discussion.md` | Discussion | Scaffold — argument skeleton |
| `06_conclusion.md` | Conclusion | Scaffold |
| `figures_and_tables.md` | Display-item manifest | Mapped to analysis code |
| `references.md` | Bibliography | Drafted (research-backed) |
| `research_notes.md` | Raw literature research (provenance/verification) | Reference material |
| `figures/` | Figure 1 schematic (Mermaid source + HTML render) | Drafted |
| `slides/index.html` | HTML slide deck (reveal.js) | Drafted |

Read in numeric order for a continuous draft. The intended journal/venue is TBD
(candidates: *Scientific Data*, *Environmental Modelling & Software*, *PVLDB /
SIGMOD data-systems venues*, or an agentic-AI venue — decide once results frame the
strongest contribution).

## How this maps to the codebase

- **Methods** are derived from `config/` (experiment, folds, metric weights),
  `src/schemas/` (target schema, curator/harmonizer bundles), `src/metrics/`,
  `src/analysis/`, and `skills/` (the two agents under evaluation).
- **Results** display items each name the `experiments/…` or `src/…` code that
  generates them (see `figures_and_tables.md`).
- **Ground truth** is `data/gold/` (19 expert-harmonized datasets: code + mappings).

## Filling in results

1. Run `experiments/phase_a_crossval.py` → `results/scored/phase_a_results.csv`.
2. Run `experiments/metric_validation.py` (validates automated metrics vs. expert).
3. Run `experiments/phase_b_prospective.py` once novel + expert-blind data exist.
4. Generate figures/tables from `notebooks/` and `src/analysis/`.
5. Replace every `[[PLACEHOLDER]]` in `04_results.md`, then write `00_abstract.md`,
   the discussion's quantitative claims, and `06_conclusion.md`.
6. Reconcile the reporting checklist at the end of `03_methods.md` (model version,
   seeds, counts).

## Citation policy

`references.md` separates sources the research pass **verified by fetching** from
those captured **from search snippets only**; the latter are flagged and must be
confirmed before submission. Author-year keys in the prose (e.g. `[Dorigo-2021]`)
resolve to entries in `references.md`. Do not introduce a citation that is not in
`references.md`.
