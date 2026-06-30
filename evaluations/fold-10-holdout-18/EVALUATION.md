# fold-10-holdout-18 Agent Evaluation

## Scope

This directory records one sandboxed sub-agent attempt for held-out dataset indices `[18]`.

- Sandbox: `.runs/fold-10-holdout-18`
- Tracked artifact copy: `evaluations/fold-10-holdout-18`
- Successful agent trace: `AGENT_ACTION_LOG.md`

## Anti-Leakage Audit

The successful trace was scanned for root gold data, root processed data, other fold sandboxes, held-out expert module names, and explicit `violation` markers. Result: `0` matches.

## Output Equivalence Against Gold

| Metric | Agent | Gold |
| --- | ---: | ---: |
| Rows | 416 | 420 |
| Target columns present | 9 / 9 | 9 / 9 |
| Schema exact match | true | n/a |
| Unique keyed rows recovered | 0 | 393 |
| Missing gold keyed rows | 393 | n/a |
| Extra agent keyed rows | 398 | n/a |
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

- Summary: `{"extra_agent_categories": [], "field_exact_matches_by_name": {"destination_variable": "8/9", "source_files": "9/9", "source_pattern": "7/9", "transformation": "2/9", "unit_conversion": "8/9"}, "field_level_exact_matches": "34/45", "gold_mapping_categories_present": "9/9", "missing_gold_categories": [], "top_level_exact_matches": "5/7", "top_level_matches": {"archive_repository": true, "data_payload_files": true, "dataset_identifier": true, "doi": false, "index": true, "location_metadata_files": false, "sensor_metadata_files": true}}`

| Field | Exact matches |
| --- | ---: |
| `destination_variable` | 8/9 |
| `source_pattern` | 7/9 |
| `source_files` | 9/9 |
| `transformation` | 2/9 |
| `unit_conversion` | 8/9 |

## Overall Assessment

See `evaluation_metrics.json` for machine-readable details. The run passed the targeted local no-gold path audit. Output equivalence should be interpreted with the key policy recorded in the metrics (`key_includes_dataset_index=False`).
