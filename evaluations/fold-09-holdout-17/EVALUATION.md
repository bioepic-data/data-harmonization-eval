# fold-09-holdout-17 Agent Evaluation

## Scope

This directory records one sandboxed sub-agent attempt for held-out dataset indices `[17]`.

- Sandbox: `.runs/fold-09-holdout-17`
- Tracked artifact copy: `evaluations/fold-09-holdout-17`
- Successful agent trace: `AGENT_ACTION_LOG.md`

## Anti-Leakage Audit

The successful trace was scanned for root gold data, root processed data, other fold sandboxes, held-out expert module names, and explicit `violation` markers. Result: `0` matches.

## Output Equivalence Against Gold

| Metric | Agent | Gold |
| --- | ---: | ---: |
| Rows | 225,524 | 226,080 |
| Target columns present | 9 / 9 | 9 / 9 |
| Schema exact match | true | n/a |
| Unique keyed rows recovered | 225,504 | 226,060 |
| Missing gold keyed rows | 556 | n/a |
| Extra agent keyed rows | 0 | n/a |
| Row precision | 1.000 | n/a |
| Gold recall | 0.998 | n/a |

Shared-row value matches after key merge:

| Column | Matched rows |
| --- | ---: |
| `interval_min` | 225502/225564 |
| `volumetric_water_content_m3_m3` | 225556/225564 |
| `gravimetric_water_content_gH2O_gs` | 225564/225564 |
| `water_potential_kPa` | 225564/225564 |
| `is_timeseries` | 225564/225564 |

## JSON Mapping Match

- Summary: `{"extra_agent_categories": ["soil_water_potential"], "field_exact_matches_by_name": {"destination_variable": "7/7", "source_files": "6/7", "source_pattern": "5/7", "transformation": "0/7", "unit_conversion": "3/7"}, "field_level_exact_matches": "21/35", "gold_mapping_categories_present": "7/7", "missing_gold_categories": [], "top_level_exact_matches": "7/7", "top_level_matches": {"archive_repository": true, "data_payload_files": true, "dataset_identifier": true, "doi": true, "index": true, "location_metadata_files": true, "sensor_metadata_files": true}}`

| Field | Exact matches |
| --- | ---: |
| `destination_variable` | 7/7 |
| `source_pattern` | 5/7 |
| `source_files` | 6/7 |
| `transformation` | 0/7 |
| `unit_conversion` | 3/7 |

## Overall Assessment

See `evaluation_metrics.json` for machine-readable details. The run passed the targeted local no-gold path audit. Output equivalence should be interpreted with the key policy recorded in the metrics (`key_includes_dataset_index=False`).
