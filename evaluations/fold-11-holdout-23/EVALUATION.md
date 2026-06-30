# fold-11-holdout-23 Agent Evaluation

## Scope

This directory records one sandboxed sub-agent attempt for held-out dataset indices `[23]`.

- Sandbox: `.runs/fold-11-holdout-23`
- Tracked artifact copy: `evaluations/fold-11-holdout-23`
- Successful agent trace: `AGENT_ACTION_LOG.md`

Note: the raw `heldout_harmonized.csv` is 116,186,889 bytes, which exceeds
GitHub's 100 MB per-file limit. It is tracked as
`agent_outputs/heldout_harmonized.csv.gz`; see
`agent_outputs/heldout_harmonized_csv_manifest.json` for raw and compressed
artifact hashes.

## Anti-Leakage Audit

The successful trace was scanned for root gold data, root processed data, other fold sandboxes, held-out expert module names, and explicit `violation` markers. Result: `0` matches.

## Output Equivalence Against Gold

| Metric | Agent | Gold |
| --- | ---: | ---: |
| Rows | 1,722,716 | 912,417 |
| Target columns present | 9 / 9 | 9 / 9 |
| Schema exact match | true | n/a |
| Unique keyed rows recovered | 0 | 912,226 |
| Missing gold keyed rows | 912,226 | n/a |
| Extra agent keyed rows | 1,722,706 | n/a |
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

- Summary: `{"extra_agent_categories": ["gravimetric_water_content"], "field_exact_matches_by_name": {"destination_variable": "8/8", "source_files": "6/8", "source_pattern": "5/8", "transformation": "0/8", "unit_conversion": "6/8"}, "field_level_exact_matches": "25/40", "gold_mapping_categories_present": "8/8", "missing_gold_categories": [], "top_level_exact_matches": "5/7", "top_level_matches": {"archive_repository": true, "data_payload_files": true, "dataset_identifier": true, "doi": true, "index": true, "location_metadata_files": false, "sensor_metadata_files": false}}`

| Field | Exact matches |
| --- | ---: |
| `destination_variable` | 8/8 |
| `source_pattern` | 5/8 |
| `source_files` | 6/8 |
| `transformation` | 0/8 |
| `unit_conversion` | 6/8 |

## Overall Assessment

See `evaluation_metrics.json` for machine-readable details. The run passed the targeted local no-gold path audit. Output equivalence should be interpreted with the key policy recorded in the metrics (`key_includes_dataset_index=False`).
