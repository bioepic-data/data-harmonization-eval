# Harmonization notes — dataset 27

- **Dataset identifier:** `ess-dive-c37aaf9ed6d4c0d-20230504T205923265966`
- **Canonical index (retained from MANIFEST.json):** 27
- **Decision:** INCLUDE
- **Structural analog used for code pattern:** dataset 17 (per-file, single-station,
  wide-format sensor time series reshaped wide→long; station id parsed from filename;
  separate/absent location metadata).

## Payload identification

Four CSVs are present in the package, all measurement payloads (one per station):

| File | Rows | Station |
|------|------|---------|
| `ER-PHS1_Field dataset_2019_Oct11 to_2020_Mar20.csv` | 3864 | ER-PHS1 |
| `ER-PHS2_Field Dataset_2019_Oct11 to 2020_Apr03.csv` | 4191 | ER-PHS2 |
| `ER-PHS3_Field dataset_2019_Oct12.csv` | 7 | ER-PHS3 |
| `ER-PHS4_Field Dataset_2019_Oct14 to 2020_Apr03.csv` | 4129 | ER-PHS4 |

Each file is a wide-format field-station export containing many environmental
columns (CO2 flux, radiation, meteorology, etc.). The soil-moisture-relevant
columns are the co-located sensors:

- `S1_wc_(m3/m3)` … `S4_wc_(m3/m3)` — volumetric water content (m³ m⁻³)
- `S5_wp_(kPa)` — soil water potential (kPa)

## Inclusion/exclusion (SKILL Section 3)

- RULE 1 (duplicate/superseded): no evidence of duplication with another package
  available in the workspace. Keep.
- RULE 2 (measurement type): contains direct VWC and water-potential observations. Pass.
- RULE 3 (manipulation): no manipulation keywords in filenames/columns; these are
  field-station ("Field dataset") deployments. No flag.
- RULE 4 (extractable payload): all four files are parseable timestamped tables. Pass.
- RULE 5 (minimum metadata): no coordinates in payload, no ancillary location file, no
  cached metadata, and no approved location registry present → included with `qc_flag = "g2"`.

## Variable mapping

- **datetime_UTC:** source `Time` (`%m/%d/%Y %H:%M`). Parsed as local `America/Denver`
  (East River / WFSFA SFA sites, consistent with exemplars) and converted to UTC.
- **site_id:** parsed from source filename via `(ER-PHS\d+)` → `ER-PHS1..ER-PHS4`.
- **depth_m:** NA. Individual sensor depths are not encoded in column names and no
  sensor-depth metadata file exists in the package.
- **replicate:** each co-located moisture sensor is treated as a replicate. VWC sensors
  S1–S4 map to replicates 1–4; the single water-potential sensor S5 maps to replicate 1.
- **is_timeseries:** True. Regular hourly cadence (median interval = 60 min) with many
  observations per station.
- **volumetric_water_content_m3_m3:** from `S1..S4_wc_(m3/m3)`; already in m³ m⁻³ (no
  unit conversion).
- **water_potential_kPa:** from `S5_wp_(kPa)`; already in kPa (no unit conversion).
- **gravimetric_water_content_gH2O_gs:** NA (not measured).

## Missing-value handling

The water-potential column uses a `-99999` sentinel. Values `<= -9999` are set to NA.
After filtering, valid water-potential readings remain only for ER-PHS1 (large negative
values ~ -13,000 to -15,000 kPa near sensor range limit), ER-PHS2, and ER-PHS3; ER-PHS4
water potential is entirely sentinel/NA. VWC columns contain no sentinels.

Rows where both VWC and water potential are NA are dropped.

## Time series (SKILL Section 4)

`is_timeseries = True`; native cadence is hourly. `interval_min` is not part of the
required output schema (Section 1) so it is not emitted; the column set matches
`ensure_harmonized_cols`.

## Location resolution (SKILL Section 5)

No coordinates are available from any permitted in-workspace source (payload, ancillary
file, cached `data/external/ess-dive_meta/` metadata — directory absent, or an approved
registry — absent). All four stations therefore receive `qc_flag = "g2"` with NA
coordinates, recorded in `*_location.csv`. External lookup was not performed, per the
fold contract.

## Outputs

- `dataset_27.py` — harmonization code (modular pattern, imports `common.py`).
- `run_fold.py` — runner adapting `common.Context` to the fold mapping (index-keyed) and
  the staged `inputs/raw` base directory.
- `ess-dive-c37aaf9ed6d4c0d-20230504T205923265966_harmonized.csv` — 48,958 rows
  (48,764 VWC, 194 water-potential), datetime range 2019-10-11T20:00Z → 2020-04-03T15:00Z.
- `ess-dive-c37aaf9ed6d4c0d-20230504T205923265966_location.csv` — 4 stations, all `g2`.
- `sm_data_harmonization_mapping.json` — mapping entry (index 27).

## Open questions / limitations

1. **Sensor depths unknown.** S1–S5 depths are not documented in the payload and no
   sensor metadata file is present. `depth_m` is NA for all rows. If a data dictionary or
   sensor-installation table becomes available, depths (and possibly per-depth `d1`
   flags) should be added.
2. **Coordinates unresolved (g2).** ER-PHS stations are almost certainly East River (CO)
   WFSFA sites, but no authoritative coordinate source is present in the workspace, so
   coordinates are left NA rather than inferred.
3. **DOI unknown.** No package metadata is staged; `doi` is set to null.
4. **Water-potential validity.** Retained water-potential values for ER-PHS1 are near the
   sensor's dry-range limit (~ -14,000 kPa); they are kept as reported but may warrant
   expert review for sensor saturation.
