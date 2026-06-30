# Run environment — leave-one-cluster-out

Harmonize the held-out dataset(s) below using ONLY:
- the skills in `skills/`,
- the exemplars in `data/processed/.../sm_data_harmonization_mapping.json` and the code patterns in `data/gold/expert_code/harmonize_sm/` (both have the held-out cluster removed),
- the shared raw inputs under `~/ess-dive_wfsfa_soil_datasets/` and the cached metadata under `data/external/ess-dive_meta/`.

Do NOT look up the held-out dataset's existing harmonized output, expert code, or mapping entry from any other location. The held-out datasets are:

- `ess-dive-38e901ec3d7bd24-20230504T211548257225`
