# Harmonization notes — fold-13, held-out dataset index 25

**Dataset:** `ess-dive-e67ab1151ebc525-20230929T190307767`
**Decision:** INCLUDE

## Deliverables (in `output/`)
- `dataset_25.py` — self-contained transformation code
- `ess-dive-e67ab1151ebc525-20230929T190307767_harmonized.csv` — harmonized payload (474,147 rows)
- `ess-dive-e67ab1151ebc525-20230929T190307767_location.csv` — location accumulator
- `sm_data_harmonization_mapping.json` — mapping entry (index 25 retained per MANIFEST.json)

## Payload identification
Package contains two files, one per site:
- `Carbone_aspen.csv` — **no header row**; 24 columns in the same order as the conifer file.
- `Carbone_conifer.csv` — header row present.

Both are hourly forest soil-profile records (2011–2021). Columns:
`Year, Month, Day, Hour, CO2-{50,15,5,0}cm, CO2-above, T-{50,15,5,0}cm, T-above,
VWC-{50,15,5}cm, DecagonT-{50,15,5}cm, EC-{50,15,5}cm, BatteryVoltage`.

The only direct soil-moisture observations are the three `VWC-{depth}cm` columns.
CO2, temperature (T / DecagonT), electrical conductivity (EC), and battery voltage
are ancillary and dropped.

## Decision rules (SKILL Section 3)
- Rule 1 (duplicate/superseded): no evidence of superseding another included package → keep.
- Rule 2 (measurement type): contains direct VWC observations → satisfies inclusion.
- Rule 3 (manipulation): none apparent (ambient aspen vs. conifer stands).
- Rule 4 (payload): machine-readable hourly CSV tables present.
- Rule 5 (metadata): no coordinates available (see below) → included with `qc_flag = g2`.

## Variable mapping
- `datetime_UTC`: assembled from integer `Year/Month/Day/Hour`, localized then converted to UTC.
- `site_id`: derived from filename stem (`aspen`, `conifer`) — not an explicit column.
- `depth_m`: parsed from `VWC-<d>cm` column names; cm → m (÷100). Depths: 0.05, 0.15, 0.50 m.
- `volumetric_water_content_m3_m3`: wide→long from the three VWC columns; **already m³/m³**, no unit conversion. Sentinel `-9999` → NA.
- `gravimetric_water_content_gH2O_gs`, `water_potential_kPa`: not reported → NA.
- `replicate`: not reported → 1.
- `is_timeseries`: **True** (continuous hourly logger output; multiple timestamps per site+depth).
- `interval_min`: hourly (60 min) implied; left implicit as in schema (not a required output column).

## Location resolution (SKILL Section 5)
No coordinates in the payload, no ancillary/site-metadata file in the package, and
no cached ESS-DIVE metadata (`data/external/ess-dive_meta/` absent from the workspace).
No approved location registry supplied. Coordinates are therefore **unresolved**:
`latitude/longitude = NaN`, `qc_flag = g2` for both sites.

## Open questions / limitations for operator review
1. **Timezone assumption.** The record clock timezone is not documented in the staged
   files. The Carbone flux/soil sites (Manitou Experimental Forest area) are in
   Colorado, so `America/Denver` was used for the local→UTC conversion. If the logger
   recorded in standard time (fixed UTC−7) or UTC, the timestamps would shift. 270 rows
   fall on DST-transition (nonexistent/ambiguous) hours and yield `NaT` datetimes.
2. **DOI unavailable.** The package DOI is not present in any staged file or cached
   metadata within the workspace; `doi` left `null` rather than retrieved externally.
3. **Coordinates unresolved (g2).** As above — recommend manual lookup against the
   project location registry if/when available.
4. **VWC outliers.** A small number of source VWC values are physically implausible
   (e.g., >1 m³/m³, or slightly negative). Only the `-9999` sentinel was mapped to NA;
   other raw values are preserved without clipping, matching the expert-code convention
   of coercing but not silently editing measured values. Flag for QA review.
5. **Aspen headerless file.** The `Carbone_aspen.csv` column order was inferred to be
   identical to the labeled `Carbone_conifer.csv` (both 24 columns, matching value
   ranges). This assumption underlies the aspen VWC mapping.
