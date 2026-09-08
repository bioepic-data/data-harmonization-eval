# Harmonization notes — dataset 2

- **Dataset identifier:** `ess-dive-9fd65df885a8e87-20250715T064942543`
- **Canonical index (from MANIFEST.json):** 2 — retained, not reassigned.
- **Decision:** INCLUDE (Rule 2 satisfied: direct volumetric water content observations).

## Inputs used
- `inputs/raw/ess-dive-9fd65df885a8e87-20250715T064942543/` — raw package files.
- Skills in `skills/` and held-out-free exemplars (mapping JSON + `data/gold/expert_code/`).
- No cached ESS-DIVE metadata present under `data/external/ess-dive_meta/`; none retrieved.

## Payload identification
- Data payload files: `ER_SMN1.csv`, `ER_SMN3.csv`, `ER_SMN4.csv`, `ER_SMN5.csv`
  (one per monitoring station). Each is wide-format with columns:
  `DateTime`, `Moisture_m3/m3_50cm`, `Tempearture_C_50cm`, `EC_mS/cm_50cm`,
  `Moisture_m3/m3_10cm`, `Tempearture_C_10cm`, `EC_mS/cm_10cm`.
- Only the two `Moisture_m3/m3_*` columns map to the target schema (VWC).
  Temperature and electrical-conductivity columns are out of schema and dropped.
- Location metadata file: `SM_loc.csv` (station `Name`, UTM13N Northing/Easting,
  and decimal-degree `Lat`/`Lon`).
- Note: station "SMN2" is absent from the staged package; only SMN1/3/4/5 present.
  This is treated as the complete supplied payload (no external retrieval).

## Variable mapping
- **datetime_UTC** ← `DateTime`, format `%m/%d/%Y %I:%M:%S %p`, localized
  `America/Denver` (East River, Colorado) then converted to UTC.
- **site_id** ← parsed from filename; normalized `ER_SMNx` → `ER-SMNx` to match
  the hyphenated `Name` values in `SM_loc.csv`.
- **depth_m** ← integer cm embedded in the moisture column name (10cm, 50cm),
  divided by 100 → 0.1 m and 0.5 m.
- **volumetric_water_content_m3_m3** ← `Moisture_m3/m3_*`, already in m³ m⁻³
  (no unit conversion). `-9999` sentinel values treated as missing and dropped.
- **replicate** ← not reported; set to 1 (single sensor per site+depth).
- **gravimetric_water_content_gH2O_gs**, **water_potential_kPa** ← not measured (NaN).

## Time series determination
- `is_timeseries = True`: continuous EM50-logger output at ~6-hour cadence across
  2016–2018 with many observations per site+depth. `interval_min` not stored as a
  column in the target schema; cadence documented here only.

## Location resolution (SECTION 5)
- Source 1 (data payload) had no coordinates; Source 2 (package ancillary file
  `SM_loc.csv`) provides decimal-degree lat/lon directly for all four sites.
- `qc_flag = None` for all sites (coordinates resolved from the package's own
  location file; no approximation, so neither `g1` nor `g2` applies).
- UTM13N Northing/Easting are also present and agree with the supplied lat/lon;
  the direct decimal-degree columns were used.

## Outputs
- `ess-dive-9fd65df885a8e87-20250715T064942543_harmonized.csv` — 131,156 rows,
  schema-conformant columns; sites ER-SMN1/3/4/5; depths 0.1 & 0.5 m;
  VWC range ≈ 0.082–0.624 m³ m⁻³.
- `ess-dive-9fd65df885a8e87-20250715T064942543_location.csv` — 4 resolved sites.
- `sm_data_harmonization_mapping.json` — mapping entry (index 2).
- `harmonize_dataset_02.py` — generated transformation code.

## Open questions / limitations
- No README/DOI supplied in the staged package; `doi` left null in the mapping.
- Local timezone assumed `America/Denver` based on East River (CO) site coordinates;
  source does not state the offset explicitly.
- SMN2 station absent from the package; documented rather than retrieved externally.
