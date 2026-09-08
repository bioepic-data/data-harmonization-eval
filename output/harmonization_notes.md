# Harmonization notes — fold-19, target index 25

**Dataset:** `ess-dive-e67ab1151ebc525-20230929T190307767`
**DOI:** not available in the run workspace (no cached metadata; not retrieved externally per fold rules)

## Payload identification

Package contains two CSV files, both hourly soil-profile records with an
identical 24-column layout:

`Year, Month, Day, Hour, CO2-50cm, CO2-15cm, CO2-5cm, CO2-0cm, CO2-above,
T-50cm, T-15cm, T-5cm, T-0cm, T-above, VWC-50cm, VWC-15cm, VWC-5cm,
DecagonT-50cm, DecagonT-15cm, DecagonT-5cm, EC-50cm, EC-15cm, EC-5cm,
BatteryVoltage`

- `Carbone_conifer.csv` — header row present (24 columns), 79,024 data rows.
- `Carbone_aspen.csv` — **no header row**; first row is data (`2011,8,20,0,...`).
  Same 24-column structure, so the conifer header was applied to it.

Both are data payloads. The soil-moisture payload is the three volumetric
water content columns `VWC-50cm`, `VWC-15cm`, `VWC-5cm`. The CO2, temperature
(T-*, DecagonT-*), electrical conductivity (EC-*), and battery-voltage columns
are not part of the target soil-moisture schema and were dropped.

## Inclusion decision

**INCLUDE.** Contains direct volumetric water content observations (Rule 2).
No duplicate/superseded evidence available (Rule 1 not triggered). No
experimental-manipulation indicators in the data (Rule 3). Machine-readable
tabular payload present (Rule 4). Minimum-metadata gap on coordinates handled
via `qc_flag = "g2"` (Rule 5).

## Variable mapping

| Target column | Source | Transformation |
|---|---|---|
| `datetime_UTC` | `Year, Month, Day, Hour` | Assemble local timestamp, convert to UTC |
| `site_id` | filename stem | `Carbone_conifer`, `Carbone_aspen` |
| `depth_m` | `VWC-<n>cm` column name | parse cm, /100 → 0.50, 0.15, 0.05 m |
| `replicate` | — | constant `1` (single sensor per site+depth) |
| `is_timeseries` | — | `True` (regular hourly logger output) |
| `volumetric_water_content_m3_m3` | `VWC-50cm/15cm/5cm` | direct; already m³/m³ |
| `gravimetric_water_content_gH2O_gs` | — | `NaN` (not measured) |
| `water_potential_kPa` | — | `NaN` (not measured) |

## Time-series determination

`is_timeseries = True`. Regular hourly cadence over multi-year deployments
(~79k rows/file), consistent with continuous logger output. `interval_min`
is not part of the target CSV schema and is not emitted; the nominal interval
is 60 min.

## Timestamp / timezone

Timestamps are split across `Year/Month/Day/Hour` integer columns (no explicit
timezone). Conifer records span 2011-06 to ~2011-10 in the previewed rows;
across the full files the assembled UTC range is 2011-06-04 to 2022-01-01.
The sites (Carbone aspen/conifer soil-CO2/moisture profiles) are in the
western US. In the absence of any package metadata, a fixed standard-time
offset **UTC-7 (`Etc/GMT+7`, no DST)** was applied before converting to UTC,
matching the convention used by the western-US exemplar datasets (e.g.,
datasets 1 and 27). This is an assumption; see open questions.

## Location resolution

Priority cascade (SKILL Section 5) yielded no coordinates:
1. Payload files — no lat/lon or easting/northing columns.
2. Package ancillary file — none present.
3. Cached ESS-DIVE metadata — `data/external/ess-dive_meta/` is absent.
4. Approved location registry — the only reference location file in the
   workspace (mapping index 0, East Taylor Watershed point locations) does
   not contain these Carbone aspen/conifer sites.
5. Unresolvable → `latitude/longitude = NaN`, **`qc_flag = "g2"`**.

## Units / QC

- VWC values are native m³/m³ (median ≈ 0.14; 99.9th pct ≈ 0.55); no unit
  conversion needed.
- `-9999` sentinels treated as missing.
- 6 of 471,677 harmonized VWC values fall outside the physical [0, 1] range
  (5 slightly negative, 1 at ~4.19). These raw sensor anomalies were retained
  unclipped, consistent with the exemplar expert handling (datasets 1, 27),
  which only strip explicit sentinels and do not range-clip.

## Outputs

- `ess-dive-e67ab1151ebc525-20230929T190307767_harmonized.csv` — 471,677 rows
  (2 sites × 3 depths × hourly), target 8-column schema.
- `ess-dive-e67ab1151ebc525-20230929T190307767_location.csv` — 2 site rows,
  coordinates NaN, `qc_flag = "g2"`.
- `sm_data_harmonization_mapping.json` — mapping entry retaining canonical
  index 25.
- `dataset_25.py` — self-contained transformation code.

## Open questions / limitations

1. **Timezone assumed** (UTC-7, no DST). Not confirmable without package
   metadata; a different offset or DST handling would shift `datetime_UTC`.
2. **DOI unknown** — not present in the workspace; left null.
3. **Coordinates unresolved** (`g2`) for both sites.
4. **site_id derived from filenames** — no in-file site identifier; the two
   files are treated as two distinct sites (aspen vs. conifer stand).
5. **aspen header inferred** from the conifer file (identical structure);
   assumes the column order is the same, which the data ranges support.
6. A few out-of-range VWC values retained unclipped (see QC).
