# Harmonization Notes — Dataset 15

- **Dataset identifier:** `ess-dive-987726ef1235abc-20230504T210342929747`
- **Canonical index (from MANIFEST.json):** 15
- **Payload file:** `TDR_survey_ER_20190701.csv`
- **Decision:** INCLUDE (contains direct volumetric water content observations)

## Deliverables (under `output/`)
- `dataset_15.py` — standalone transformation code (reads `inputs/raw/...`, writes `output/`).
- `ess-dive-987726ef1235abc-20230504T210342929747_harmonized.csv` — 286 harmonized rows.
- `ess-dive-987726ef1235abc-20230504T210342929747_location.csv` — 101 surveyed points with lat/lon.
- `sm_data_harmonization_mapping.json` — change-mapping entry (index 15).

## Payload identification
Single CSV. It serves as **both** the data payload and the location metadata source
(coordinates are embedded per row). No README, sensor-metadata, or ancillary files
were staged in the package.

## Inclusion / exclusion (SKILL Section 3)
- RULE 2 (measurement type): PASS — three replicate `TDR_SM(VWC%)_i` columns are
  direct volumetric water content (VWC) observations from a TDR probe.
- RULE 1 (duplicate/superseded): no evidence of duplication with an included package.
- RULE 3 (manipulation): none detected; a natural East River watershed field survey.
- RULE 4 (payload): PASS — machine-readable tabular data.
- RULE 5 (metadata): PASS — per-point UTM coordinates present.
- **Decision: INCLUDE.**

## Closest exemplar
Dataset 9 (`NEON_plot_TDR.csv`): a discrete TDR survey with replicate `VWC_i`
columns, VWC in percent, and UTM Zone 13N (EPSG:32613) coordinates embedded in the
payload. The same reshape / unit-conversion / reprojection pattern was applied here.

## Variable mapping
| Target | Source | Notes |
|---|---|---|
| `datetime_UTC` | filename token `20190701` | No per-record timestamp; single survey date 2019-07-01, America/Denver → UTC (06:00Z). |
| `site_id` | `GPS_id` | Point-level identifier (e.g., `ss01`, `TDR001`). |
| `depth_m` | — | Not reported (surface TDR probe); NA. |
| `replicate` | `TDR_SM(VWC%)_i` suffix | Integers 1–3. |
| `is_timeseries` | — | False (discrete campaign). |
| `interval_min` | — | NA. |
| `volumetric_water_content_m3_m3` | `TDR_SM(VWC%)_i` | Percent → m³/m³ (÷100), rounded to 4 dp. |
| `gravimetric_water_content_gH2O_gs` | — | Not reported; NA. |
| `water_potential_kPa` | — | Not reported; NA. |
| `latitude` / `longitude` | `Northing_m` / `Easting_m` | Reprojected EPSG:32613 → EPSG:4326. |

## Time-series determination (SKILL Section 4)
`is_timeseries = False`. Each surveyed point has a single date-only observation with
no time-of-day and no repeated site+depth records; the methods describe a discrete
field survey. `interval_min = NaN`.

## Location resolution (SKILL Section 5)
Priority 1 (coordinates in the payload) satisfied. Easting ≈ 325,913–331,150 m and
Northing ≈ 4,309,610–4,317,309 m are consistent with UTM Zone 13N over the East
River watershed (CO). Reprojected coordinates fall at ~38.92–38.99 °N, ~-107.01 to
-106.95 °W as expected. All 101 points resolved, so **no `g2` flags** were assigned.

## Data-handling details
- VWC parsed with `errors="coerce"`; the sentinel `-9999` (none present) would be
  set to NaN. Missing replicate cells are dropped, yielding 286 rows from
  101 points × 3 replicates minus blanks.
- One `TDR_EC(mS/m)` cell contains the string `>125`; electrical conductivity is
  **not** part of the target schema and is not harmonized, so this value is ignored.
- Duplicate coordinates exist across points (e.g., ss94/ss95 share Easting/Northing);
  the location table keeps one row per `site_id` (`GPS_id` is unique).
- Temperature (`TDR_T(C)_i`) and EC columns are not part of the soil-moisture schema
  and are dropped.

## Limitations / open questions
1. **DOI unavailable.** No DOI is present in the staged workspace (no cached
   `data/external/ess-dive_meta/` metadata was supplied). Recorded as `null` rather
   than retrieved externally, per AGENT_INSTRUCTIONS.md.
2. **Depth not reported.** TDR probe insertion depth is not in the payload;
   `depth_m` is NA. If package metadata specifies a nominal probe length, depth
   could be populated on review.
3. **Timezone assumption.** America/Denver assumed for the East River, CO site;
   only a date (no time) is reported, so the exact UTC instant is nominal.
4. **UTM zone assumption.** EPSG:32613 inferred from coordinate ranges and the East
   River convention used across sibling datasets (1, 9, 17); not explicitly stated
   in the payload.
