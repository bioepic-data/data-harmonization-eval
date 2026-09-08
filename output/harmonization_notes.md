# Harmonization notes — target dataset index 16

**Dataset identifier:** `ess-dive-b3d271f19a94e8d-20260114T204512119`
**Package title (inferred from files/metadata):** WFSFA East River (Pump House)
and Snodgrass ecohydrology sensor towers, Wu et al.
**Canonical index (from MANIFEST.json):** 16 — retained; no new index assigned.

## Decision: INCLUDE

- **Rule 2 (measurement type):** Payloads contain direct sensor observations of
  volumetric water content (`SWC_*`, METER TEROS 12) and soil water potential
  (`SWP_*`, METER TEROS 21). Passes.
- **Rule 1 (duplicate/superseded):** No evidence of duplication within the
  supplied references; the East River pumphouse gravimetric campaign (index 18)
  and the ER18 physical dataset (index 26) are distinct products. Included.
- **Rule 3 (experimental manipulation):** These are ambient ecohydrology towers
  (grassland / below-canopy forest); no warming/irrigation manipulation.
- **Rule 4 (extractable payload):** Eight machine-readable hourly CSVs. Passes.
- **Rule 5 (minimum metadata):** Site coordinates present in
  `metadata_site_v1-1.csv`; `qc_flag` not required (resolved from package).

## Source structure

- One wide-format payload per site: `data_<SITE_ID>_v1-1.csv`, hourly
  (`TIMESTAMP_START` / `TIMESTAMP_END`), covering 2019–2025.
- Soil-moisture columns follow the AmeriFlux/FLUXNET `<VAR>_H_V_R` convention:
  - `SWC_1_1_1 .. SWC_1_4_1` — volumetric water content, **percent (%)**.
  - `SWP_1_1_1` — soil water potential, **kPa** (negative matric potential).
- **Depth is NOT in the payload column names.** It is recorded in
  `metadata_instrument_v1-1.csv` as the signed `HEIGHT` field (negative = below
  surface). depth_m is resolved by joining each `SWC_/SWP_` variable to the
  instrument metadata on `(SITE_ID, VARIABLE)` and taking `-HEIGHT`.

## Mapping decisions

| Target column | Source | Transformation |
|---|---|---|
| `datetime_UTC` | `TIMESTAMP_START` | Parse `%Y-%m-%d %H:%M:%S` in Etc/GMT+7 (site `UTC_OFFSET=-7`); convert to UTC. Start-of-interval used. |
| `site_id` | filename | `ER-PHS1` … `SG-EHS8`; matches metadata `SITE_ID`. |
| `depth_m` | instrument `HEIGHT` | `-HEIGHT` in meters (no unit conversion). Site-specific (e.g. SG-EHS7 pos-3 = 0.5 m; ER pos-4 = 1.15 m). |
| `replicate` | `_H_V_R` suffix | Trailing replicate index `R` (all present sensors = 1). |
| `is_timeseries` | — | `True` (hourly logger deployment; median interval 60 min). |
| `volumetric_water_content_m3_m3` | `SWC_*` | Wide→long; divide by 100 (% → m³ m⁻³). |
| `water_potential_kPa` | `SWP_*` | Wide→long; source already kPa, no conversion. |
| `gravimetric_water_content_gH2O_gs` | — | Not reported; NA. |

- `-9999` (and stray `9999`) treated as missing.
- SWC and SWP are pivoted onto shared `(datetime, depth, replicate)` rows so a
  single water-potential sensor at 0.3 m aligns with the co-located SWC sensor.

## Output summary

- `ess-dive-b3d271f19a94e8d-20260114T204512119_harmonized.csv`: 1,176,445 rows,
  8 sites, depths {0.1, 0.3, 0.5, 0.6, 0.75, 1.06, 1.15} m,
  VWC non-null 1,173,763; water-potential non-null 267,477;
  datetime 2019-10-10T07:00Z → 2025-10-08T16:00Z.
- `location_data_harmonized_with_uuid.csv`: 8 sites with lat/lon from site
  metadata; all `qc_flag` null (coordinates resolved from the package).

## Limitations / open questions

- **DOI unavailable:** No package DOI is present in the staged workspace and no
  external lookup is permitted in fold mode; `doi` recorded as `null`.
- **Water-potential magnitude:** `SWP_*` spans down to ≈ -100,000 kPa (-100 MPa)
  at ER sites — within the METER TEROS 21 dry range but effectively censored at
  the sensor limit; retained as reported (no cap applied). Flag for reviewer.
- **Timestamp convention:** Interval start (`TIMESTAMP_START`) used as the
  observation time, consistent with other hourly tower datasets.
- **Files nested under subfolder:** payload/metadata paths are prefixed with
  `WFSFA_EHG_SensorTowers_Wu_et_al/` in the mapping entry and code.

## Reproduction

```
python3 output/run_harmonization.py
```

Imports the shared expert library (`data/gold/expert_code/common.py`) and the
generated `output/dataset_16.py`; reads only from `inputs/raw/` and the
`output/` mapping; writes all deliverables to `output/`.
