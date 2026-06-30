# fold-07-holdout-9 Agent Evaluation

## Scope

This directory records one sandboxed sub-agent attempt for held-out dataset indices `[9]`.

- Sandbox: `.runs/fold-07-holdout-9`
- Tracked artifact copy: `evaluations/fold-07-holdout-9`
- Successful agent trace: `AGENT_ACTION_LOG.md`

## Anti-Leakage Audit

The successful trace was scanned for root gold data, root processed data, other fold sandboxes, held-out expert module names, and explicit `violation` markers. Result: `0` matches.

## Output Equivalence Against Gold

| Metric | Agent | Gold |
| --- | ---: | ---: |
| Rows | 664 | 672 |
| Target columns present | 9 / 9 | 9 / 9 |
| Schema exact match | true | n/a |
| Unique keyed rows recovered | 0 | 672 |
| Missing gold keyed rows | 672 | n/a |
| Extra agent keyed rows | 664 | n/a |
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

- Summary: `{"extra_agent_categories": ["gravimetric_water_content"], "field_exact_matches_by_name": {"destination_variable": "8/8", "source_files": "8/8", "source_pattern": "5/8", "transformation": "0/8", "unit_conversion": "6/8"}, "field_level_exact_matches": "27/40", "gold_mapping_categories_present": "8/8", "missing_gold_categories": [], "top_level_exact_matches": "7/7", "top_level_matches": {"archive_repository": true, "data_payload_files": true, "dataset_identifier": true, "doi": true, "index": true, "location_metadata_files": true, "sensor_metadata_files": true}}`

| Field | Exact matches |
| --- | ---: |
| `destination_variable` | 8/8 |
| `source_pattern` | 5/8 |
| `source_files` | 8/8 |
| `transformation` | 0/8 |
| `unit_conversion` | 6/8 |

## Overall Assessment

See `evaluation_metrics.json` for machine-readable details. The run passed the targeted local no-gold path audit. Output equivalence should be interpreted with the key policy recorded in the metrics (`key_includes_dataset_index=False`).
