# Run environment — leave-one-cluster-out

This file is the authoritative contract for this fold evaluation. It overrides any generic or production-oriented guidance in `skills/`.

## Allowed inputs

Harmonize the held-out dataset(s) using ONLY:
- the skills in `skills/`,
- the held-out-free exemplars in `data/processed/ess-dive_wfsfa_soil_datasets/sm_data_harmonization_mapping.json` and code patterns in `data/gold/expert_code/`,
- raw inputs staged under `inputs/raw/<dataset_identifier>/`, and
- cached metadata under `data/external/ess-dive_meta/`, if present.

Do not access parent directories, absolute paths outside this workspace, network services, APIs, or any other external data source. If required raw data or metadata is absent, record the limitation in the output rather than retrieving it. Do NOT look up the held-out dataset's existing harmonized output, expert code, or mapping entry from any other location.

## Required outputs

Write every deliverable under `output/`: harmonized CSV file(s), generated transformation code, a change-mapping JSON, and notes documenting decisions or missing inputs. For each held-out dataset, use its existing index from `MANIFEST.json`; do not assign a new sequential index.

## Held-out datasets

- `ess-dive-e67ab1151ebc525-20230929T190307767`
