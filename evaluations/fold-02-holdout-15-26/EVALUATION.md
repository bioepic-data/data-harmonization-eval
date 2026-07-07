# fold-02-holdout-15-26 Agent Evaluation

## Scope

This directory records one sandboxed sub-agent attempt for held-out dataset indices `[15, 26]`.

- Sandbox: `.runs/fold-02-holdout-15-26`
- Tracked artifact copy: `evaluations/fold-02-holdout-15-26`
- Successful agent trace: `AGENT_ACTION_LOG.md`

## Anti-Leakage Audit

The successful trace was scanned for root gold data, root processed data, other fold sandboxes, held-out expert module names, and explicit `violation` markers. Result: `0` matches.

## Output Equivalence Against Gold

| Metric | Agent | Gold |
| --- | ---: | ---: |
| Rows | 711 | 586 |
| Target columns present | 9 / 9 | 9 / 9 |
| Schema exact match | true | n/a |
| Unique keyed rows recovered | 0 | 584 |
| Missing gold keyed rows | 584 | n/a |
| Extra agent keyed rows | 711 | n/a |
| Row precision | 0.000 | n/a |
| Gold recall | 0.000 | n/a |

Shared-row value matches after key merge:

| Column | Matched rows |
| --- | ---: |
| `interval_min` | 0/0 |
| `volumetric_water_content_m3_m3` | 0/0 |
| `gravimetric_water_content_gH2O_gs` | 0/0 |
| `water_potential_kPa` | 0/0 |
| `is_timeseries` | 0/0 |

## JSON Mapping Match

- Summary: `{"heldout_indices": [15, 26], "note": "cluster mapping literal comparison not computed"}`


## Overall Assessment

See `evaluation_metrics.json` for machine-readable details. The run passed the targeted local no-gold path audit. Output equivalence should be interpreted with the key policy recorded in the metrics (`key_includes_dataset_index=True`).
