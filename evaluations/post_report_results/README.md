# Post-Report Completed Results

Created: 2026-08-11T17:43:41+00:00

This directory captures benchmark-related outputs that were found after the overall evaluation report branch had been checked in.

## Contents

- `parallel_batch_20260701/`: local `.runs/fold-*` result artifacts for the parallel leave-one-out batch described in GitHub issue #42. These include manifests, instructions, action logs, generated harmonizer code, mapping JSON, curator bundles, and notes.
- `parallel_batch_20260701/large_generated_csv_manifest.csv`: checksums, sizes, and line counts for generated harmonized CSVs that were too large to commit directly to GitHub.
- `github_actions/run_28483156122_eval_holdout_7/`: downloaded artifact from the successful `Run Harmonization Eval` GitHub Actions run for holdout 7.

## Trace Caveat

The `.runs` folders do not contain complete raw sub-agent tool-call transcripts. They contain `AGENT_ACTION_LOG.md` files and final outputs. Future benchmark harness runs should persist the complete raw sub-agent JSONL/tool-call transcript for each sub-agent, not only action logs and output files.

## Large CSV Policy

Generated harmonized CSVs were not committed because several are too large for normal GitHub storage, including files over 100 MB. They are represented by size, line count, and SHA-256 digest in `parallel_batch_20260701/large_generated_csv_manifest.csv`.
