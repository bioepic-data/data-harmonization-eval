# Run environment — leave-one-cluster-out

Harmonize the held-out dataset(s) below using ONLY:
- the skills in `skills/`,
- the exemplars in `data/processed/.../sm_data_harmonization_mapping.json` and the code patterns in `data/gold/expert_code/harmonize_sm/` (both have the held-out cluster removed),
- the shared raw inputs under `~/ess-dive_wfsfa_soil_datasets/` and the cached metadata under `data/external/ess-dive_meta/`.

Do NOT look up the held-out dataset's existing harmonized output, expert code, or mapping entry from any other location. The held-out datasets are:

- `ess-dive-beca0be9bb38ece-20250516T122010234`
- `ess-dive-9fd65df885a8e87-20250715T064942543`
- `ess-dive-4c1829de1b8a2ec-20260220T045039633`
- `ess-dive-18e91eb74405882-20241017T173226640`
- `ess-dive-b3d271f19a94e8d-20260114T204512119`
- `ess-dive-c37aaf9ed6d4c0d-20230504T205923265966`
