# Harmonization notes — dataset index 1

- **Dataset:** `ess-dive-beca0be9bb38ece-20250516T122010234`
- **DOI:** doi:10.15485/2566877
- **Title:** Soil moisture and temperature from 2019 to 2024 along northeast- and
  southwest-facing hillslopes at the Lower Montane site, East River Watershed,
  Colorado (Watershed Function SFA).

## Decision

**INCLUDE.** The package contains direct, time-stamped sensor observations of
volumetric water content (VWC, m³ m⁻³) at all 9 stations and soil water
potential (kPa) at 2 stations (`ER_SMN4B`, `ER_SMN5B`), from TEROS12 / 5TE
sensors. This satisfies RULE 2 (direct observation of VWC / water potential),
RULE 4 (machine-readable measurement payload), and RULE 5 (resolvable
coordinates).

## Payload identification

- **Data payload (9 files):** `ER_SMN10.csv`, `ER_SMN1B.csv`, `ER_SMN30.csv`,
  `ER_SMN3B.csv`, `ER_SMN4B.csv`, `ER_SMN5B.csv`, `ER_SMS1.csv`, `ER_SMS2.csv`,
  `ER_SMS3.csv`. Each file is one station; columns are per-sensor time series
  with depth embedded in the column name (`*_at_<j>cm`).
- **Location metadata:** `Sensor_Location.csv` (`Name`, `Easting`, `Northing`
  in UTM Zone 13N, plus `Setup` describing depths/sensor types).
- Only the 10 files listed in the package metadata that were staged under
  `inputs/raw/` are available in this workspace; `ER_dd_.csv`, `flmd.csv`, and
  `Sensor_Location_dd.csv` (data dictionaries / file-level metadata, per the
  cached ESS-DIVE record) are **not staged** and are not required for the
  harmonization. This is documented rather than retrieved externally.

## Variable mapping

| Target | Source | Notes |
|---|---|---|
| `datetime_UTC` | `Time` | `%Y-%m-%d %H:%M:%S`, localized then converted to UTC |
| `site_id` | filename stem | e.g. `ER_SMN10` |
| `depth_m` | `*_at_<j>cm` suffix | ÷100 (cm→m) |
| `replicate` | column ordinal | sequential per site+depth+variable when co-located |
| `is_timeseries` | — | `True` |
| `volumetric_water_content_m3_m3` | `m3_m3_Water_Content*` / `m3_m3_VWC*` | no unit conversion |
| `water_potential_kPa` | `kPa_Potential*` | no unit conversion (already negative kPa) |
| `gravimetric_water_content_gH2O_gs` | — | NA (not reported) |

Soil temperature (`C_*`), electrical conductivity (`mS_cm_*`), battery, logger
temperature, and reference-pressure columns are **not** target variables and
were dropped.

## Time series determination

`is_timeseries = True`. Continuous logger deployments (30-min to hourly cadence)
spanning Oct 2019 – Oct 2024, with repeated observations per site and depth;
measurement technique describes TEROS12 / 5TE sensor time series.

## Timezone assumption (open question)

The package metadata does **not** state the timestamp timezone. Loggers in the
East River Watershed (Colorado) report local standard time; Mountain Standard
Time (UTC+7, `Etc/GMT+7`, no DST applied) was assumed, consistent with other
East River WFSFA soil-moisture exemplars (dataset 25). If the source timestamps
are instead already UTC, all `datetime_UTC` values would be offset by 7 hours.
**Flagged for operator review.**

## Replicate handling

Most site/depth combinations have a single sensor (`replicate = 1`). Where two
co-located sensors of the same measurement type report at the same depth, they
are numbered 1 and 2 by column order:
- `ER_SMN10`, `ER_SMN30`: two VWC sensors at 50 cm → replicate 1 and 2.
- `ER_SMN5B`: two water-potential sensors at 10 cm (both all-`-9999`, so no rows
  survive the missing-value filter).

VWC and water potential are treated as independent variables, so a VWC and a
water-potential sensor at the same depth each carry `replicate = 1`.

## Location resolution

Priority order (SKILL §5): coordinates resolved from the package ancillary file
`Sensor_Location.csv` (priority 2). `Easting`/`Northing` are UTM Zone 13N
(EPSG:32613), reprojected to WGS84 (EPSG:4326). All 9 sites resolved
(`qc_flag` empty); resulting coordinates (≈38.92 °N, −106.95 °W) fall within the
package bounding box (38.82–39.033 °N, −107.12 to −106.88 °W). The two
reinstalled NE-slope stations share coordinates with their predecessors
(`ER_SMN10`↔`ER_SMN1B` footprint `SM_1-54`; `ER_SMN30`↔`ER_SMN3B` footprint
`SM_2-19`), as expected from the metadata (reinstalled in 2020 after wildlife
damage). Cross-dataset location deduplication is deferred to the global
accumulator and not performed in this single-fold run.

## Missing data handling

`-9999` sentinel values (and gaps in datetime) were coerced to NA and dropped
from the long output.

## QA summary

- Harmonized rows: 1,326,691; sites: 9; depths (m): 0.1, 0.2, 0.3, 0.35, 0.4, 0.5.
- VWC non-null: 1,228,003 (range −0.023 to 0.601 m³ m⁻³).
- Water potential non-null: 98,688 (all negative kPa).
- No residual `-9999` sentinels; no null `datetime_UTC`.
- All 8 required harmonized columns present and in canonical order.
- `*_location.csv` emitted with one row per `site_id` and the required columns.

## Deliverables

- `..._harmonized.csv`
- `..._location.csv`
- `..._harmonize.py` (transformation code)
- `..._mapping.json` (change-mapping entry, retains canonical index 1)
- `..._notes.md` (this file)
