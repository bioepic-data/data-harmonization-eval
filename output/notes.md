# Harmonization notes — fold-01 target

- **Dataset**: `ess-dive-beca0be9bb38ece-20250516T122010234` (canonical index **1**, retained per `MANIFEST.json`)
- **DOI**: `doi:10.15485/2566877` (from `essdive_sm_curator` SKILL.md working example, Section 14; no cached metadata was present under `data/external/ess-dive_meta/` to independently confirm — see limitations)

## Deliverables (under `output/`)
- `dataset_01.py` — transformation code
- `ess-dive-beca0be9bb38ece-20250516T122010234_harmonized.csv` — harmonized measurements (1,277,000 rows)
- `ess-dive-beca0be9bb38ece-20250516T122010234_location_harmonized.csv` — 9 sites with WGS84 coordinates
- `sm_data_harmonization_mapping.json` — mapping entry (index 1)

## Inclusion / exclusion decision
**INCLUDE.** The nine `ER_SM*.csv` logger files contain direct sensor observations of
volumetric water content (m³/m³) and, for two loggers, soil water potential (kPa).
No experimental manipulation is indicated (natural East River watershed monitoring).
Rules 1–5 pass; a machine-readable payload and resolvable coordinates are present.

## Payload identification
- **Data payloads**: `ER_SMN10, ER_SMN1B, ER_SMN30, ER_SMN3B, ER_SMN4B, ER_SMN5B, ER_SMS1, ER_SMS2, ER_SMS3` (`.csv`).
- **Location metadata**: `Sensor_Location.csv` (`Name, Alias1, Alias2, Easting, Northing, Elevation, Setup`).
- No README/sensor-metadata files were staged.

## Variable mapping
Wide columns encode `<units>_<variable>[_<rep>]_at_<depth>cm`:
- `m3_m3_Water_Content*` and `m3_m3_VWC*` → `volumetric_water_content_m3_m3` (already m³/m³, no conversion).
- `kPa_Potential*` → `water_potential_kPa` (already kPa, negative; only in ER_SMN4B, ER_SMN5B).
- Soil temperature and EC columns are ignored (not in target schema).
- `depth_m` = depth-in-cm / 100.
- `replicate` = embedded integer sensor index, defaulting to 1 when absent.
- `-9999` sentinel values set to NaN; NaN-only measurements dropped.
- VWC and potential sharing the same site/timestamp/depth/replicate are merged onto one row via pivot.

## Time series
`is_timeseries = True`. Regular logger cadence: 30-min for ER_SMN10/ER_SMN30, 60-min for the
remainder (median timestamp differences). Spans ~2018–2024 depending on logger.

## Location resolution
Source 2 (package ancillary file). `Sensor_Location.csv` gives UTM Zone 13N Easting/Northing;
converted to WGS84 via EPSG:32613→EPSG:4326. All nine sites resolve to the East River watershed,
Colorado (~38.92 °N, −106.95 °W), consistent with ~2760 m elevation. `qc_flag` left null (coordinates
resolved directly, not from a registry).

## Limitations / open questions
- **DOI** taken from the curator skill's worked example; no cached ESS-DIVE metadata was available in
  the workspace to independently verify it. Recorded rather than retrieved externally (per AGENT_INSTRUCTIONS).
- **Timezone** assumed America/Denver (Mountain) based on the East River, CO location and the SFA
  convention used by sibling datasets; the raw files do not state a timezone explicitly.
- **Same-depth duplicate sensors**: e.g., ER_SMN10 has two `_at_50cm` water-content columns. These are
  distinguished by their embedded replicate index (rep 3 vs rep 4), so no data is lost.
- **Potential extremes**: some `Potential` values reach ~−100,000 kPa (very dry / near sensor range
  limit); retained as reported after removing the −9999 sentinel.
- Because the target is held out of the reference mapping JSON, `dataset_01.py` reads paths directly
  from `inputs/raw/<identifier>/` instead of via a mapping-index lookup, while otherwise following the
  SKILL.md conventions and reusing the `common.py` helper patterns (`parse_local_to_utc`,
  `utm32613_to_latlon`, `ensure_harmonized_cols`, `add_loc_qc`).
