# GitHub Issue #42: First parallel leave-one-out batch

Source: https://github.com/bioepic-data/data-harmonization-eval/issues/42
Created: 2026-07-01T00:02:04Z

## First parallel leave-one-out batch - results + isolation/audit findings

We ran the curator+harmonizer agent on **18 held-out target datasets in parallel** (leave-one-out; each in its own `build_env` sandbox), then scored outputs against the expert and audited every run's trace with the invigilator. Batch: 18 agents, ~2.0M tokens, 495 tool calls, ~21 min wall-clock. Dataset 7 was run manually earlier, giving 19 folds on disk total.

TL;DR: output quality was strong and not inflated by cheating: no agent read its held-out answer. The run surfaced two harness problems before relying on it at scale: instruction-based isolation was leaky, and invigilator v1 was too noisy.

## Quality Scorecard

| Metric | Result |
|---|---|
| Curator include decision | 18/19 (only idx 4 excluded) |
| Payload-file selection (exact) | 18/18 of included datasets |
| Location-file selection (exact) | 14/18 (differ: 5, 10, 23, 26) |
| Variable mappings | near-perfect, mostly 8/8 with a few 7/8 documentation-completeness differences |
| Code ran and produced harmonized CSV | 18/19; the excluded one correctly did not |

## Isolation Audit Summary

- No agent read its held-out answer.
- Five agents listed the real `data/gold/` directory and saw filenames, not content.
- One agent for idx 3 read the head of the full mapping JSON, containing early entries but not its own held-out answer.
- Most invigilator flags were false positives caused by shell-variable expansion, path-token regex issues, timezone strings, system paths, harness-internal transcript paths, and benign repo-root input reads.

## Follow-up Requirements

- Harden the invigilator false-positive classes.
- Move to absence-based isolation so gold answers are not reachable from the run environment.
- Human-review idx 4 and the four location-file mismatches.
- Add output-equivalence scoring against expert code for cell-level accuracy.
- Persist complete raw tool-call JSONL traces for every sub-agent in future benchmark runs.
