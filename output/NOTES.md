# Harmonization notes — dataset index 3

**Dataset:** `ess-dive-4c1829de1b8a2ec-20260220T045039633`
**Canonical index (from MANIFEST.json):** 3 (retained; not reassigned)
**Decision:** INCLUDE

## Inputs used
- `inputs/raw/ess-dive-4c1829de1b8a2ec-20260220T045039633/Soil_water_potential.csv` (payload)
- `inputs/raw/ess-dive-4c1829de1b8a2ec-20260220T045039633/locations.csv` (location metadata)
- Skills in `skills/`; expert code pattern reference `data/gold/expert_code/dataset_08.py`
  (structurally analogous wide-format matric-potential + moisture logger export).

No parent directories, network, APIs, or external lookups were used. No cached
metadata directory (`data/external/ess-dive_meta/`) is present in this workspace.

## Payload identification
`Soil_water_potential.csv` is the sole measurement payload: a CR-logger export
(10-min cadence, 27,954 rows, 2024-11-09 to 2025-06-04) with matric-potential
(`*_MP*`) and soil-temperature (`*_Temp*`) columns per sensor, plus logger
housekeeping columns (`RECORD`, `BattV_*`, `PTemp_C_Avg`). `locations.csv` is a
single-row ancillary location record.

## Decision rules (SKILL SECTION 3)
- RULE 2 (measurement type): PASS — direct soil **matric/water potential**
  observations (target variable `water_potential_kPa`). Temperature and logger
  housekeeping columns are excluded.
- RULE 3 (manipulation): none detected (ambient hillslope monitoring).
- RULE 4 (extractable payload): PASS — parseable time-stamped table.
- RULE 5 (minimum metadata): PASS via the ancillary location file.

## Variable mapping
Wide → long. Depth and station are embedded in the MP column names:

| Source column | site_id | depth_m | replicate |
|---|---|---|---|
| `SD11-25cm_MP` | SD11 | 0.25 | 1 |
| `SD11-60cm_MP_2_Avg` | SD11 | 0.60 | 1 |
| `SD1-25cm_MP_3_Avg` | SD1 | 0.25 | 1 |
| `SD1-60cm_MP_4_Avg` | SD1 | 0.60 | 1 |
| `SD1-25cm_sagebrush_rhizo_MP_5_Avg` | SD1 | 0.25 | 2 |

- Units: matric potential is already in **kPa** (values are negative, range
  approx -7996 to -0.1); no unit conversion applied.
- VWC and GWC are not measured → `NaN`.

## Sentinel / missing-value handling
The logger reports out-of-range (below sensor dry limit) as exactly **-7999**.
These, plus non-finite values (one `+inf` in `SD11-25cm_MP`), are set to missing
and dropped. Near-limit but non-sentinel values (e.g. -6861, -7996) are retained
as valid clipped readings. Final harmonized rows: 96,482; all `water_potential_kPa`
values are finite and negative.

## Time series (SKILL SECTION 4)
`is_timeseries = True` (continuous logger deployment, regular timestamps).
`interval_min = 10.0` (median timestamp difference per site+depth+replicate).

## Location resolution (SKILL SECTION 5)
The ancillary `locations.csv` provides a **single** site-level coordinate for
"North Facing Hillslope Sagebrush Site 1" (`Location_ID` ER-LLN1;
lat 38.920555, lon -106.948333). The datalogger station identifiers in the
payload (`SD1`, `SD11`) do not appear as `Location_ID`s, so the single
site-level coordinate is applied to both stations. `qc_flag = "g1"`
(coordinates from a supplied location file, not a 1:1 per-station match).

## Timezone assumption
Timestamps carry no offset. Site is East River / Coal Creek SFA, Colorado
(Mountain Time). Converted to UTC using a fixed no-DST Mountain offset
(`Etc/GMT+7`), consistent with the expert code's handling of other SFA loggers.

## Limitations / open questions
- **DOI unavailable** in the workspace; recorded as `null` rather than retrieved.
- **Coordinates are site-level, not per-station** (g1). If SD1/SD11 have distinct
  footprints, per-station coordinates would need a sensor/installation metadata
  file that is not present.
- **Mountain time assumed** (no explicit timezone in the source); no DST applied,
  matching prior SFA convention.
- The `sagebrush_rhizo` probe (SD1 25 cm) is interpreted as a co-located second
  sensor → `replicate = 2`; it could alternatively be treated as a distinct
  micro-site if operator prefers.

## Outputs written under `output/`
- `ess-dive-4c1829de1b8a2ec-20260220T045039633_harmonized.csv`
- `ess-dive-4c1829de1b8a2ec-20260220T045039633_location.csv`
- `sm_data_harmonization_mapping.json` (single entry, index 3)
- `dataset_03.py` (generated transformation code)
- `NOTES.md` (this file)
