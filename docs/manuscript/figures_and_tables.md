# Figures and Tables — Manifest

> Planned display items, with the analysis code/path that generates each. Keep this
> in sync with `04_results.md`. Outputs are written under `results/figures/` and
> `results/tables/`.

## Tables

| # | Title | Source | Status |
|---|---|---|---|
| 1 | Gold-corpus structural characterization (format, units, CRS, time-series share) | `notebooks/01_explore_gold.ipynb` | TODO |
| 2 | Curator (Skill 1) performance, all sub-metrics + composite | `phase_a_crossval.py` → `skill1_metrics.py` | TODO |
| 3 | Harmonizer (Skill 2, oracle) performance, output-equivalence breakdown | `skill2_output_equiv.py`, `skill2_*` | TODO |
| 4 | End-to-end vs. oracle, with error-propagation gap | `stats.py::error_propagation_gap` | TODO |
| 5 | Error-propagation taxonomy (failure attribution shares) | `error_taxonomy.py` | TODO |
| 6 | Agent pair vs. baselines (single-call, no-exemplar, naïve) | `phase_a_crossval.py` (baselines) | TODO |
| 7 | Mixed-effects model coefficients (mode, similarity) | `stats.py::mixed_effects_comparison` | TODO |
| 8 | Phase B prospective: agent vs. expert on novel data | `phase_b_prospective.py` | TODO |

## Figures

| # | Title | Source | Status |
|---|---|---|---|
| 1 | Pairwise dataset-similarity distribution (motivates grouped CV) | `similarity.py` | TODO |
| 2 | Curator decision confusion matrix | `skill1_metrics.py` | TODO |
| 3 | Per-column cell-agreement (harmonizer) | `skill2_output_equiv.py` | TODO |
| 4 | Per-dataset output-equivalence distribution | `phase_a_crossval.py` | TODO |
| 5 | Error-propagation taxonomy (stacked bar / Sankey) | `error_taxonomy.py` | TODO |
| 6 | Output equivalence vs. nearest-exemplar similarity (+ regression) | `similarity.py`, `stats.py` | TODO |
| 7 | Run-to-run variance / pass@k per mode | `phase_a_crossval.py` | TODO |
| 8 | Automated-metric vs. expert-rubric agreement | `metric_validation.py`, `irr.py` | TODO |

## Schematic (no data needed — can be drafted now)

| # | Title | Notes |
|---|---|---|
| 1 | Workflow + evaluation design schematic | **Drafted** — `figures/figure1_workflow.mmd` (Mermaid source) + `figures/figure1_workflow.html` (in-browser SVG render). Curator → bundle → Harmonizer → code+mapping → executed output vs. expert; three modes; gap. This is the main **Figure 1**. |

## Presentation

- `slides/index.html` — self-contained reveal.js deck summarizing motivation,
  the agent pair, design, metrics, positioning, and results placeholders. Renders
  Figure 1 live via Mermaid. Open in a browser; press <kbd>Esc</kbd> for overview,
  <kbd>?</kbd> for shortcuts.
