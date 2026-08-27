# Fold 05 Holdout 7 Agent Evaluation

## Scope

This directory records one sandboxed sub-agent attempt on fold 05, where dataset
index 7 was held out:

- Dataset: `ess-dive-38e901ec3d7bd24-20230504T211548257225`
- Sandbox: `.runs/fold-05-holdout-7`
- Tracked artifact copy: `evaluations/fold-05-holdout-7`
- Successful agent trace: `AGENT_ACTION_LOG.md`

The worker was run without inherited parent context. It was instructed to use
only the fold-local Skill 1 curator and Skill 2 harmonizer materials, raw ESS-DIVE
inputs, and fold-local exemplars, and to log each read/list/search/command/write
before performing it.

## Anti-Leakage Audit

The successful trace was scanned for direct evidence of forbidden access to:

- root gold data: `/scratch/jmc/data-harmonization-eval/data/gold`
- root processed data: `/scratch/jmc/data-harmonization-eval/data/processed`
- other fold sandboxes
- the held-out expert module name: `dataset_07.py`
- explicit `violation` markers

Command:

```bash
rg -n '(/scratch/jmc/data-harmonization-eval/data/gold|/scratch/jmc/data-harmonization-eval/data/processed|/scratch/jmc/data-harmonization-eval/.runs/fold-(01|02|03|04|06|07|08|09|10|11|12|13)|dataset_07\.py|violation)' .runs/fold-05-holdout-7/AGENT_ACTION_LOG.md
```

Result: no matches. The trace therefore passes this targeted local path audit.

The trace records one external metadata lookup through the ESS-DIVE package API
to retrieve the DOI/title. That is not local gold leakage, but it is external
metadata access and should be accounted for separately if the benchmark protocol
requires all metadata to come only from staged raw package files.

## Output Equivalence Against Gold

The gold comparison used the current expert module for dataset 7. Running that
module required an evaluation-only compatibility shim for `add_loc_qc`, because
NumPy 2 raises a dtype promotion error when mixing string QC flags and `np.nan`.
The shim affected only the location-QC side output after the harmonized table was
constructed; it did not alter the soil-moisture transformation being compared.

Summary:

| Metric | Agent | Gold |
| --- | ---: | ---: |
| Rows | 56,861 | 56,861 |
| Columns | 9 | 9 |
| Schema exact match | yes | yes |
| Unique keyed rows recovered | 56,861 | 56,861 |
| Missing gold keyed rows | 0 | n/a |
| Extra keyed rows | 0 | n/a |

Site and depth counts matched exactly:

| Field | Value |
| --- | --- |
| `site_id` | `BM` for all 56,861 rows |
| Depths | `0.1`, `0.2`, `0.3`, `0.5`, `0.75`, `1.0`, `1.3` m |
| Rows per depth | 8,123 |

For keyed rows, target-value matches were:

| Column | Matched rows |
| --- | ---: |
| `volumetric_water_content_m3_m3` | 56,861 / 56,861 |
| `water_potential_kPa` | 56,861 / 56,861 |
| `gravimetric_water_content_gH2O_gs` | 56,861 / 56,861 |
| `is_timeseries` | 56,861 / 56,861 |
| `interval_min` | 56,855 / 56,861 |

The only table mismatch was six `interval_min` cells. The agent computed
intervals within each `site_id`/`depth_m`/`replicate` stream. The gold expert
computes a raw sequential diff across the input file after parsing timestamps,
which creates six large negative interval values at depth transitions. The
agent's behavior is scientifically cleaner, but it is not literal gold
equivalence for those six cells.

After sorting and dropping `interval_min`, the agent and gold target tables were
exactly equal.

## JSON Mapping Match

The generated `mapping.json` was compared to gold mapping entry 7 from
`data/gold/sm_data_harmonization_mapping.json`.

Top-level exact matches:

| Field | Match |
| --- | --- |
| `index` | yes |
| `dataset_identifier` | yes |
| `doi` | yes |
| `archive_repository` | yes |
| `data_payload_files` | yes |
| `location_metadata_files` | yes |
| `sensor_metadata_files` | yes |

Mapping category coverage:

- Gold categories present: 8 / 8
- Extra agent category: `gravimetric_water_content`
- Missing gold categories: none

Field-level exact matches across shared categories:

| Field | Exact matches |
| --- | ---: |
| `destination_variable` | 8 / 8 |
| `source_pattern` | 3 / 8 |
| `source_files` | 7 / 8 |
| `transformation` | 0 / 8 |
| `unit_conversion` | 7 / 8 |
| Total | 25 / 40 |

Important JSON differences:

- Agent added `gravimetric_water_content`, which is absent from the gold mapping
  JSON even though the output schema contains
  `gravimetric_water_content_gH2O_gs`.
- Agent used the actual raw column names, such as `Depth (cm)` and
  `Volumetric Water Content`; gold uses normalized/source-pattern strings such
  as `Depth..cm.` and `Volumetric.Water.Content`.
- Transformation prose did not match gold text literally.
- For `site_id`, the agent cited both the BM file prefix and the location file;
  gold cites only `BM_EGM_Well_CO2.csv`.

## Python Match

The generated `harmonize_heldout.py` captured nearly all of the gold expert
transformation:

- Reads `BM_Merged_T_VWC_0616_1018.csv`.
- Parses `date.time` with `%m/%d/%y %H:%M` in `America/Denver` and converts to
  UTC.
- Sets constant `site_id = "BM"`.
- Converts `Depth (cm)` to `depth_m` by dividing by 100.
- Sets `replicate` to `1`.
- Sets `is_timeseries` to `True`.
- Maps `Volumetric Water Content` to `volumetric_water_content_m3_m3`.
- Sets water potential and gravimetric water content to null.

Python differences relative to gold:

- Computes `interval_min` within depth streams instead of raw file order,
  causing six literal gold mismatches.
- Sorts by `site_id`, `depth_m`, `replicate`, and timestamp before interval
  calculation; gold preserves raw input order for interval diffs.
- Does not implement the gold module interface using `Context` and
  `DatasetResult`.
- Does not emit the gold location side dataframe, though it documents the
  `BM_EGM_Well_CO2.csv` coordinates in the curator bundle and notes.

## Overall Assessment

The index 7 run was substantially stronger than the index 4 run. It recovered
the complete row set with no extras or omissions and matched all non-interval
target values exactly. The remaining output difference is narrowly localized to
six interval cells caused by a defensible but non-gold grouping choice. The JSON
mapping is structurally strong and perfect on top-level metadata, but only a
moderate literal match to gold prose and source-pattern fields.
