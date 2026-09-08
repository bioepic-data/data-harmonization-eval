# Run environment — targeted grouped leave-one-out

This file is the authoritative contract for this fold evaluation. It overrides any generic or production-oriented guidance in `skills/`.

## Allowed inputs

Harmonize only the target dataset(s) listed below, using ONLY:
- the skills in `skills/`,
- the held-out-free exemplars in `data/processed/ess-dive_wfsfa_soil_datasets/sm_data_harmonization_mapping.json` and code patterns in `data/gold/expert_code/`,
- raw inputs staged under `inputs/raw/<dataset_identifier>/`, and
- cached metadata under `data/external/ess-dive_meta/`, if present.

Do not access parent directories, absolute paths outside this workspace, network services, APIs, or any other external data source. If required raw data or metadata is absent, record the limitation in the output rather than retrieving it. Do NOT look up a target dataset's existing harmonized output, expert code, or mapping entry from any other location.

## Required outputs

Write every deliverable under `output/`: harmonized CSV file(s), generated transformation code, a change-mapping JSON, and notes documenting decisions or missing inputs. For each target dataset, use its existing index from `MANIFEST.json`; do not assign a new sequential index.

## Target datasets

- `ess-dive-6c7085e9c544cc6-20250424T164534831`

Only the target dataset(s) above should be harmonized. Additional datasets may be absent from the exemplar references; they are not targets.
