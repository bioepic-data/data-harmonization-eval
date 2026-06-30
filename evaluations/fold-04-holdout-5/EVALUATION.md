# Fold 04 Holdout 5 Agent Evaluation

## Scope

This directory records one sandboxed sub-agent attempt on fold 04, where dataset index 5 was held out.

- Dataset index: `5`
- Sandbox: `.runs/fold-04-holdout-5`
- Tracked artifact copy: `evaluations/fold-04-holdout-5`
- Successful agent trace: `AGENT_ACTION_LOG.md`

## Anti-Leakage Audit

The successful trace was scanned for root gold data, root processed data, other fold sandboxes, `dataset_05.py`, and explicit `violation` markers. Result: `0` matches.

## Output Equivalence Against Gold

| Metric | Agent | Gold |
| --- | ---: | ---: |
| Rows | 515,825 | 1,089,621 |
| Columns | 9 | 9 |
| Schema exact match | true | n/a |
| Unique keyed rows recovered | 515,795 | 976,805 |
| Missing gold keyed rows | 461,010 | n/a |
| Extra agent keyed rows | 0 | n/a |
| Row precision | 1.000 | n/a |
| Gold recall | 0.528 | n/a |

Shared-row value matches after key merge:

| Column | Matched rows |
| --- | ---: |
| `interval_min` | 59007/516005 |
| `volumetric_water_content_m3_m3` | 515933/516005 |
| `gravimetric_water_content_gH2O_gs` | 516005/516005 |
| `water_potential_kPa` | 516005/516005 |
| `is_timeseries` | 516005/516005 |

Interpretation: this run did not match the gold row set. The agent retained control-treatment SWC rows only, producing 515,825 rows versus 1,089,621 gold rows. Because `depth_m` is missing and timestamps/sites repeat, the key merge has duplicate expansions; row-set metrics above use NaN-safe unique keys.

## JSON Mapping Match

- Top-level exact matches: `5/7`
- Gold mapping categories present: `8/8`
- Extra agent categories: `gravimetric_water_content`
- Missing gold categories: `none`
- Field-level exact matches: `24/40`

Field exact matches by name:

| Field | Exact matches |
| --- | ---: |
| `destination_variable` | 8/8 |
| `source_pattern` | 4/8 |
| `source_files` | 4/8 |
| `transformation` | 0/8 |
| `unit_conversion` | 8/8 |

## Python Match

The generated script produced the required target schema and parsed successfully, but its curation choice diverged from gold by filtering to `Treatment == "ctl"` rows only. Gold includes a much larger row set for this dataset.

## Overall Assessment

The fold 04 run passed the local no-gold trace audit and generated executable artifacts, but output equivalence was poor because the row-inclusion decision diverged from gold.
