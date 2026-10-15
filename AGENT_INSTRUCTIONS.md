# Run environment — targeted grouped leave-one-out

This file is the authoritative contract for this fold evaluation. It overrides any generic or production-oriented guidance in `skills/`.

## Allowed inputs

Harmonize only the target dataset(s) listed below, using ONLY:
- the skills in `skills/`,
- the held-out-free exemplars in `data/processed/ess-dive_wfsfa_soil_datasets/sm_data_harmonization_mapping.json` and code patterns in `data/gold/expert_code/`,
- raw inputs staged under `inputs/raw/<dataset_identifier>/`, and
- the target dataset's ESS-DIVE package metadata under `data/raw_cache/ess-dive_wfsfa_soil_metadata/<dataset_identifier>.json`, if present (only the target's record is supplied; other datasets' records are deliberately withheld).

Do not access parent directories, absolute paths outside this workspace, network services, APIs, or any other external data source. If required raw data or metadata is absent, record the limitation in the output rather than retrieving it. Do NOT look up a target dataset's existing harmonized output, expert code, or mapping entry from any other location.

## Required outputs

Write every deliverable under `output/`. For each target dataset, produce all five:

1. `<dataset_identifier>_harmonized.csv` — the harmonized data.
2. `<dataset_identifier>_location.csv` — one row per distinct `site_id`, with columns `site_id,latitude,longitude,source_dataset_id,qc_flag`. **This file is required even when coordinates cannot be resolved**: emit every `site_id` with empty `latitude`/`longitude` and the appropriate `qc_flag`. Do not omit the file, and do not invent coordinates.
3. the generated transformation code.
4. the change-mapping JSON.
5. notes documenting decisions or missing inputs.

For each target dataset, use its existing index from `MANIFEST.json`; do not assign a new sequential index.

## Target datasets

- `ess-dive-4c1829de1b8a2ec-20260220T045039633`

Only the target dataset(s) above should be harmonized. Additional datasets may be absent from the exemplar references; they are not targets.
