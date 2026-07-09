# Fold 03 Holdout 4 Agent Evaluation

## Scope

This directory records one sandboxed sub-agent attempt on fold 03, where dataset
index 4 was held out:

- Dataset: `ess-dive-6c7085e9c544cc6-20250424T164534831`
- Sandbox: `.runs/fold-03-holdout-4`
- Tracked artifact copy: `evaluations/fold-03-holdout-4`
- Successful agent trace: `AGENT_ACTION_LOG.md`
- Failed earlier trace retained for audit: `AGENT_ACTION_LOG.failed-write-location.md`

The successful agent was instructed to use the fold-local Skill 1 curator and
Skill 2 harmonizer materials, write only under the fold sandbox, and log each
read/list/command/write action before performing it.

## Anti-Leakage Audit

The successful trace was scanned for direct evidence of forbidden access to:

- root gold data: `/scratch/jmc/data-harmonization-eval/data/gold`
- root processed data: `/scratch/jmc/data-harmonization-eval/data/processed`
- other fold sandboxes
- the held-out expert module name: `dataset_04.py`
- explicit `violation` markers

Command:

```bash
rg -n '(/scratch/jmc/data-harmonization-eval/data/gold|/scratch/jmc/data-harmonization-eval/data/processed|/scratch/jmc/data-harmonization-eval/.runs/fold-(01|02|04|05|06|07|08|09|10|11|12|13)|dataset_04\.py|violation)' evaluations/fold-03-holdout-4/AGENT_ACTION_LOG.md
```

Result: no matches. The trace therefore passes this targeted path audit.

The first attempt failed the operational audit because it wrote to root
`agent_outputs/`; that trace is preserved separately in
`AGENT_ACTION_LOG.failed-write-location.md`. The successful retry wrote artifacts
under the fold sandbox only.

## Output Equivalence Against Gold

The gold comparison used the current expert module for dataset 4. Running that
module required an evaluation-only compatibility shim for `add_loc_qc`, because
NumPy 2 raises a dtype promotion error when mixing string QC flags and `np.nan`.
The shim affected only the location-QC side output after the harmonized table was
constructed; it did not alter the soil-moisture transformation being compared.

Summary:

| Metric | Agent | Gold |
| --- | ---: | ---: |
| Rows | 1001 | 552 |
| Columns | 9 | 9 |
| Schema exact match | yes | yes |
| Unique keyed rows recovered | 552 | 552 |
| Missing gold keyed rows | 0 | n/a |
| Extra keyed rows | 449 | n/a |

Site counts:

| site_id | Agent rows | Gold rows |
| --- | ---: | ---: |
| `ph1` | 275 | 275 |
| `ph2` | 148 | 148 |
| `sg5` | 129 | 129 |
| `tb` | 449 | 0 |

For the 552 shared keyed rows, all checked target values matched gold:

| Column | Matched rows |
| --- | ---: |
| `depth_m` | 552 / 552 |
| `interval_min` | 552 / 552 |
| `volumetric_water_content_m3_m3` | 552 / 552 |
| `gravimetric_water_content_gH2O_gs` | 552 / 552 |
| `water_potential_kPa` | 552 / 552 |
| `is_timeseries` | 552 / 552 |

Interpretation: the agent recovered every gold observation and got the numeric
transformations right, but kept 449 `tb` rows that the gold expert drops. As a
full output submission, that is perfect recall and 552 / 1001 = 55.1% row
precision. After dropping `tb` and sorting, there were no observed cell-level
value differences in the target columns.

Additional formatting/order differences:

- Gold sorts by `datetime_UTC, site_id`; the agent leaves raw order.
- Gold stores timezone-aware UTC timestamps in the dataframe; the agent writes
  ISO strings ending in `Z`. Parsed as UTC, the timestamps match.

## JSON Mapping Match

The generated `mapping.json` was compared to gold mapping entry 4 from
`data/gold/sm_data_harmonization_mapping.json`.

Top-level exact matches:

| Field | Match |
| --- | --- |
| `index` | yes |
| `dataset_identifier` | yes |
| `doi` | no |
| `archive_repository` | yes |
| `data_payload_files` | yes |
| `location_metadata_files` | no |
| `sensor_metadata_files` | yes |

Mapping category coverage:

- Gold categories present: 8 / 8
- Extra agent category: `gravimetric_water_content`
- Missing gold categories: none

Field-level exact matches across shared categories:

| Field | Exact matches |
| --- | ---: |
| `destination_variable` | 8 / 8 |
| `source_pattern` | 5 / 8 |
| `source_files` | 4 / 8 |
| `transformation` | 0 / 8 |
| `unit_conversion` | 8 / 8 |
| Total | 25 / 40 |

Important JSON differences:

- Agent set `doi` to `null`; gold has `doi:10.15485/2561511`.
- Agent included an extra East Taylor reference file in
  `location_metadata_files`; gold lists only `df_meta.csv`.
- Agent mapped `datetime.source_files` to `df_meta.csv`; gold JSON says
  `df_data.csv`. The agent choice matches where the `datetime` field is actually
  read from by both the gold code and the agent code, but it does not match the
  gold JSON literally.
- Transformation prose did not match gold text literally.
- Agent included `gravimetric_water_content`, which is absent from the gold
  mapping JSON even though the output schema contains
  `gravimetric_water_content_gH2O_gs`.

## Python Match

The generated `harmonize_heldout.py` captured most of the gold expert
transformation:

- Reads `df_data.csv` and `df_meta.csv`.
- Concatenates row-aligned data and metadata.
- Converts local `America/Denver` dates to UTC.
- Maps `site` to `site_id`.
- Sets `depth_m` to null.
- Sets `replicate` to `1`.
- Sets `is_timeseries` to `True`.
- Sets `interval_min` to `1440`.
- Maps `swc` to `volumetric_water_content_m3_m3`.
- Maps `swp` to `water_potential_kPa`.
- Sets `gravimetric_water_content_gH2O_gs` to null.

Python misses relative to gold:

- Did not drop rows where `site_id == "tb"`.
- Did not sort by `datetime_UTC, site_id`.
- Did not implement the gold module interface using `Context` and
  `DatasetResult`.
- Did not emit the gold location side dataframe for `ph1`, `ph2`, and `sg5`.

## Overall Assessment

The successful sub-agent was strong on the executable transformation and weak
on the held-out curation details around row exclusion and location side output.
It appears to have obeyed the no-gold/no-other-fold constraint based on the
recorded trace and targeted path scan. The generated Python is close enough that
a small patch, dropping `tb` and sorting the output, would make the harmonized
target table match gold at the observed-value level. The generated JSON is
useful but only a moderate literal match to the held-out gold mapping.
