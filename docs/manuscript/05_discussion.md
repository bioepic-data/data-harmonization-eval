# Discussion

> **Status:** Structural scaffold. Argument skeleton and limitations are derivable
> from the design now; quantitative claims (`[[PLACEHOLDER]]`) are filled at
> results-time. Cross-references to related work (`§` in `02_background.md`) are
> marked `[[cite]]` and resolved against `references.md`.

## 1. Principal findings

> One or two paragraphs once results exist. Anticipated claims, each contingent on
> the data:

- The agent pair reproduces expert harmonization with end-to-end output equivalence
  of `[[PLACEHOLDER]]`, with `[[PLACEHOLDER]]`% of datasets meeting the strict
  cell-agreement threshold.
- Given correct curator input, the harmonizer alone reaches `[[PLACEHOLDER]]`; the
  error-propagation gap of `[[PLACEHOLDER]]` shows that `[[most / little]]` of the
  end-to-end shortfall originates upstream in curation.
- The dominant failure mode is `[[category]]`, concentrated in
  `[[structural type / unit / location resolution]]`.

## 2. Why decompose the workflow

Scoring each skill in isolation, the harmonizer under an oracle bundle, and the full
pipeline lets us attribute error rather than report an opaque success rate. This
matters for deployment: a system that fails mostly through *curator* errors (file
selection, inclusion decisions) calls for a different intervention — a human gate at
curation — than one that fails through *harmonizer* errors (unit conversions,
timezone handling). The error-propagation taxonomy operationalizes that distinction
and connects to broader work on chained/multi-agent LLM pipelines `[[cite]]`, where
compounding error across stages is a known failure mode.

## 3. Output equivalence as the right endpoint

Comparing executed outputs rather than code (or rather than an LLM-judge score)
sidesteps two problems: stylistic code variation (two correct programs differ
arbitrarily) and the reliability concerns of LLM-as-judge evaluation `[[cite]]`. It
also gives a domain-meaningful unit — the fraction of harmonized cells a downstream
scientist could trust. The cost is that output equivalence requires both code
artifacts to *execute* on shared raw data, which is why code executability is scored
separately and why sandboxed execution is part of the harness.

## 4. Generalization and the exemplar question

In-context exemplars are the mechanism by which the agent learns the target schema,
yet they also create a leakage risk under cross-validation: a held-out dataset with
a near-duplicate sibling in the exemplar pool would overstate performance. Grouped
cross-validation (holding out whole source/instrument clusters) and the explicit
similarity covariate convert this risk into a measured relationship. The
similarity–performance curve `[[PLACEHOLDER]]` indicates the boundary of reliable
generalization and, practically, where the system should defer to a human. The
no-exemplars baseline `[[PLACEHOLDER]]` separately quantifies how much the reference
corpus contributes at all.

## 5. Relation to prior work

> Resolve against `02_background.md` once research citations are integrated.

- **Vs. classic data-wrangling / ETL synthesis** (`[[cite]]`): how the agentic,
  schema-targeted, exemplar-driven approach differs from program-synthesis and
  rule-based wrangling tools.
- **Vs. LLM-based schema/entity matching and data cleaning** (`[[cite]]`): we
  evaluate end-to-end *transformation-code generation against executed expert
  ground truth*, not a matching/labeling decision in isolation.
- **Vs. environmental-science harmonization practice** (`[[cite]]`): contrast with
  manual, script-per-dataset harmonization and with standardized reporting formats /
  ontologies; position the agent pair as an accelerator that still produces
  human-auditable code and documented mappings.

## 6. Limitations

- **Small gold corpus.** With ≈19 expert-harmonized datasets, estimates are
  uncertain; we report effect sizes with cluster-bootstrap CIs and avoid
  over-reliance on *p*-values, but power is inherently limited.
- **Single domain, single repository.** The corpus is WFSFA soil moisture on
  ESS-DIVE. Generalization to other variables, repositories, or Earth-science
  domains is untested and is an explicit direction for future work.
- **Expert as gold standard.** The reference is one expert's harmonization; some
  decisions are genuinely ambiguous (captured by the taxonomy's fourth category and
  by expert-confidence labels), and a second independent expert would strengthen the
  ground truth.
- **Model and skill drift.** Results are pinned to a specific model version and
  skill versions; LLM and skill updates may change performance, so we report exact
  versions and seeds for reproducibility.
- **Stochasticity.** LLM outputs vary run-to-run; we report variance and pass@k, but
  any single deployed run may differ from the reported mean.
- **Automated-metric validity.** Phase B leans on automated scoring; its credibility
  rests on the Phase A metric-validation agreement `[[PLACEHOLDER]]`, which bounds
  how far the automated numbers can be trusted.
- **Prospective scope.** Phase B covers `[[N]]` novel datasets; broader prospective
  deployment is needed to confirm the retrospective estimate.

## 7. Implications and future work

- **Human-in-the-loop deployment.** The natural operating point is agent-drafts /
  expert-reviews, with automatic deferral above the similarity threshold and on
  low-confidence curator decisions (the FLAG path). Report the implied human-effort
  savings `[[PLACEHOLDER]]`.
- **Beyond soil moisture.** Extend to other ESS-DIVE reporting formats and to other
  environmental variables; test whether the curator/harmonizer split transfers.
- **Richer provenance.** The change-mapping JSON is a step toward machine-readable,
  FAIR-aligned transformation provenance `[[cite]]`; future work could emit
  standardized provenance directly.
- **Active exemplar selection.** Given the similarity findings, selecting or
  synthesizing exemplars to cover structural gaps may extend the generalization
  frontier.

## 8. Conclusion

> Short — typically merged into `06_conclusion.md`. Restate the headline
> output-equivalence result, the decomposed error attribution, and the practical
> deployment recommendation, all contingent on the final numbers.
