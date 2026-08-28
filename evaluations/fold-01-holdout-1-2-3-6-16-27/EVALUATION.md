# fold-01-holdout-1-2-3-6-16-27 Agent Evaluation

## Scope

This directory records one sandboxed sub-agent attempt for held-out dataset indices `[1, 2, 3, 6, 16, 27]`.

- Sandbox: `.runs/fold-01-holdout-1-2-3-6-16-27`
- Tracked artifact copy: `evaluations/fold-01-holdout-1-2-3-6-16-27`
- Successful agent trace: `AGENT_ACTION_LOG.md`

Note: the raw combined `heldout_harmonized.csv` is 394,183,424 bytes, which
exceeds GitHub's 100 MB per-file limit. It is tracked as
`agent_outputs/heldout_harmonized.csv.gz`; see
`agent_outputs/heldout_harmonized_csv_manifest.json` for raw and compressed
artifact hashes.

## Anti-Leakage Audit

The successful trace was scanned for root gold data, root processed data, other fold sandboxes, held-out expert module names, and explicit `violation` markers. Result: `0` matches.

## Output Equivalence Against Gold

| Metric | Agent | Gold |
| --- | ---: | ---: |
| Rows | 3,584,771 | 2,214,708 |
| Target columns present | 9 / 9 | 9 / 9 |
| Schema exact match | true | n/a |
| Unique keyed rows recovered | 1,306,547 | 2,102,354 |
| Missing gold keyed rows | 795,807 | n/a |
| Extra agent keyed rows | 2,278,224 | n/a |
| Row precision | 0.364 | n/a |
| Gold recall | 0.621 | n/a |

Shared-row value matches after key merge:

| Column | Matched rows |
| --- | ---: |
| `interval_min` | 1306902/1307069 |
| `volumetric_water_content_m3_m3` | 1238017/1307069 |
| `gravimetric_water_content_gH2O_gs` | 1307069/1307069 |
| `water_potential_kPa` | 1306739/1307069 |
| `is_timeseries` | 1307069/1307069 |

## JSON Mapping Match

- Summary: `{"heldout_indices": [1, 2, 3, 6, 16, 27], "note": "cluster mapping literal comparison not computed"}`


## Overall Assessment

See `evaluation_metrics.json` for machine-readable details. The run passed the targeted local no-gold path audit. Output equivalence should be interpreted with the key policy recorded in the metrics (`key_includes_dataset_index=True`).
