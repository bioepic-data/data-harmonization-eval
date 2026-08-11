# Mapping Notes: ess-dive-6c7085e9c544cc6-20250424T164534831

Decision: INCLUDE (best effort).

Evidence used from allowed files:
- `df_data_dd.csv` defines `swc` as 24-hour average depth-averaged soil water content in m3/m3.
- `df_data_dd.csv` defines `swp` as soil water potential in kPa.
- `df_meta.csv` is row-aligned metadata containing `site` and `datetime` for `df_data.csv`.
- Notebooks treat `swc` and `swp` as observed predictor variables with source units m3/m3 and kPa.

Harmonization choices:
- `datetime_UTC`: parse `df_meta.datetime` as `%Y-%m-%d` in `America/Denver`, then convert to UTC.
- `site_id`: preserve `df_meta.site` (`ph1`, `ph2`, `sg5`, `tb`).
- `depth_m`: set to null. The source says depth-averaged but gives no depth or interval in allowed files.
- `replicate`: set to 1 because no replicate field is present.
- `is_timeseries`: set to true because each site has many dated daily observations.
- `interval_min`: set to 1440 based on the 24-hour-average definition and median within-site date interval.
- `volumetric_water_content_m3_m3`: direct mapping from `swc`.
- `water_potential_kPa`: direct mapping from `swp`.
- `gravimetric_water_content_gH2O_gs`: set to null; not reported.

Location notes:
- Coordinates are not included in the target held-out harmonized CSV, but were reviewed for curation.
- Allowed reference package index 0 supports moderate-confidence matches: `ph1 -> ER-PHS1`, `ph2 -> ER-PHS2`, `sg5 -> SG-EHS5`; use `qc_flag=g1` if those locations are materialized elsewhere.
- `tb` was not confidently resolved. A weak literal candidate `WC-TBA1`/`TB1` exists, but it is described as an ERT profile, so it was not used automatically; use `qc_flag=g2` unless an operator approves a match.

Open issues:
- DOI was not found in allowed local files; no network/API lookup was performed.
- The package includes neural-network code and derived ET modeling outputs. This mapping only harmonizes direct soil moisture variables (`swc`, `swp`) from `df_data.csv` and excludes `ET`.
