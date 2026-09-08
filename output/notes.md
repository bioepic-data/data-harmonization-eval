# Harmonization Notes — Dataset 17

- **Dataset identifier:** `ess-dive-be919d7d5d42c94-20240130T205332180`
- **Canonical index (from MANIFEST.json):** 17 (retained; no new index assigned)
- **Decision:** INCLUDE

## Payload identification
- Data payload files: `TMC1.csv, TMC2.csv, TMC4.csv, TMC5.csv, TMC6.csv`
  (under `FieldData/Soil_Moisture_Data/`). Each file is one soil-moisture &
  temperature monitoring site.
- Location metadata: `Locations.csv` (UTM Zone 13N Easting/Northing/Elevation).
- No sensor-metadata or README/documentation files present in the package.
- Each payload file's first data row is a **units row**
  (`V/V, degrees_Celsius, mS/cm`) and is skipped on read.

## Inclusion / exclusion (SKILL Section 3)
- RULE 1 (duplicate/superseded): no evidence of duplication → pass.
- RULE 2 (measurement type): direct volumetric water content observations
  (`MC_*` columns, units V/V) → pass.
- RULE 3 (manipulation): no manipulation keywords or treatment structure → pass.
- RULE 4 (extractable payload): 5 parseable timestamped CSV tables → pass.
- RULE 5 (minimum metadata): site coordinates resolvable from `Locations.csv` → pass.
- **Result: INCLUDE**, `qc_flag = null` (coordinates resolved from package
  ancillary file, Section 5 priority 2).

## Variable mapping
- `MC_jm` (moisture content, V/V) -> `volumetric_water_content_m3_m3`.
  Units V/V are equivalent to m3/m3; **no unit conversion**.
- Depth is embedded in the column name in **meters**
  (`MC_0.1m -> 0.1`, `0.3`, `0.6`, `0.8 m`); parsed directly, **no /100**.
- `T_*` (temperature) and `EC_*` (electrical conductivity) columns are outside
  the target schema and are dropped.
- No gravimetric water content or water potential in this package (set NaN).
- `site_id` parsed from filename (`TMC1`..`TMC6`), matching the `ID` column in
  `Locations.csv`.
- `replicate = 1` (single sensor per site+depth; not encoded in source).

## Time series (SKILL Section 4)
- `is_timeseries = True`: continuous logger output, multiple timestamps per
  site+depth, ~11,304 hourly records per site spanning 2021-06-10 to 2022-09-23.
- `interval_min = 60.0` (median timestamp difference = 60 min).

## Timezone
- Site coordinates (UTM Zone 13N, elevation ~3100 m) place the study near
  Crested Butte, Colorado (~38.93 N, -106.98 W). Timestamps treated as local
  Mountain Standard Time and localized with `Etc/GMT+7` (no DST), then converted
  to UTC. This matches the convention used by the structurally analogous
  exemplar dataset 1 (same region and CRS). Verified: 00:00 local -> 07:00 UTC.

## Location resolution (SKILL Section 5)
- Source: package ancillary file `Locations.csv` (priority 2).
- Coordinates reprojected from EPSG:32613 (WGS84 UTM Zone 13N) to EPSG:4326.
- Only the 5 sites present in the payload are emitted. `Locations.csv` also
  lists non-soil-moisture entries (ERT-End, ERT-Start, SNI1B borehole,
  WeatherStation) and a `TMC3` soil-moisture station; these are excluded from
  the location output because they have no soil-moisture payload file.

## Quality assurance
- All 8 required harmonized columns present; column order enforced.
- VWC value range 0.0–0.4549 m3/m3 — physically valid; no `-9999` sentinels
  found (guard retained in code regardless).
- All timestamps converted to UTC.
- Output: 225,544 harmonized rows; 5 location rows, all with resolved coordinates.

## Limitations / open questions
- **DOI unavailable:** No cached ESS-DIVE metadata was supplied in the workspace
  (`data/external/ess-dive_meta/` absent), and external lookups are disallowed in
  fold-evaluation mode. `doi` is recorded as `null` in the mapping entry.
- **TMC3:** `Locations.csv` lists a soil-moisture station `TMC3`, but no
  `TMC3.csv` payload file exists in the package; it is therefore not harmonized.
- **Timezone assumption:** Local timezone is inferred from geography (MST,
  `Etc/GMT+7`); the package contains no explicit timezone statement.

## Deliverables (all under `output/`)
- `dataset_17.py` — transformation code (self-contained, runnable).
- `ess-dive-be919d7d5d42c94-20240130T205332180_harmonized.csv` — harmonized data.
- `ess-dive-be919d7d5d42c94-20240130T205332180_location_data.csv` — site coordinates.
- `sm_data_harmonization_mapping.json` — mapping entry (index 17).
- `notes.md` — this file.
