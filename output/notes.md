# Harmonization notes — fold-11-target-7

Target dataset: `ess-dive-38e901ec3d7bd24-20230504T211548257225` (canonical index 7,
retained from `MANIFEST.json`).

## Inputs used
- `inputs/raw/ess-dive-38e901ec3d7bd24-20230504T211548257225/BM_Merged_T_VWC_0616_1018.csv`
- `inputs/raw/ess-dive-38e901ec3d7bd24-20230504T211548257225/BM_EGM_Well_CO2.csv`
- Skills in `skills/` and long-format VWC code patterns from `data/gold/expert_code/`
  (datasets 5 and 23) for reference only.

No cached metadata directory (`data/external/ess-dive_meta/`) is present, and no
network/API/DOI lookups were performed (fold-evaluation mode).

## Payload identification (SKILL Step 2)
- **Payload:** `BM_Merged_T_VWC_0616_1018.csv` — 56,861 rows of long-format hourly
  soil sensor output with an explicit `Volumetric Water Content` column, an
  explicit `Depth (cm)` column (10/20/30/50/75/100/130 cm), and a `date.time`
  timestamp. Also carries temperature and EC, which are not part of the target
  schema and are dropped.
- **Not payload / location source:** `BM_EGM_Well_CO2.csv` — soil-CO2 (EGM well)
  measurements. This contains no soil-moisture variable (only `CO2.Max`), so it is
  not harmonized. It is the only file carrying site coordinates, so it is used
  solely as the location source.

## Inclusion decision (SKILL Section 3)
**INCLUDE.** Contains direct VWC observations (Rule 2 satisfied), a machine-readable
time-stamped table (Rule 4), and resolvable coordinates (Rule 5). No duplicate/
superseded evidence and no experimental-manipulation indicators found.

## Variable mapping (SKILL Step 4)
- `date.time` (`%m/%d/%y %H:%M`, local) -> `datetime_UTC`
- `Depth (cm)` / 100 -> `depth_m`
- `Volumetric Water Content` -> `volumetric_water_content_m3_m3` (already a fraction; no unit conversion; `-9999` -> NaN, none present)
- GWC and water potential: not measured -> NaN
- `site_id` = `"BM"` (single site; from the CO2 file `Location` column)
- `replicate`: no replicate encoding in source; assigned 1 (one sensor per depth)

## Time-series determination (SKILL Section 4)
`is_timeseries = True`. Each depth has 8,123 regularly spaced hourly observations
spanning 2016-06-20 to 2018-10-19 — a clear sensor deployment, not a campaign.
`interval_min` is not a target-schema column and is not emitted; the underlying
cadence is ~60 min.

## Location resolution (SKILL Section 5)
Coordinates (lat 38.98715, lon -107.003863) come from a package ancillary file
(`BM_EGM_Well_CO2.csv`), which is priority level 2 of the fallback hierarchy.
Because a genuine package source is used (not an external registry and not an
unresolved gap), no `g1`/`g2` flag is applied (`qc_flag = None`).

## Timezone assumption
The package is from the East River / Gunnison County, CO area (lon ~ -107 deg).
Following the exemplar convention for this region, local times are treated as fixed
Mountain Standard Time (`Etc/GMT+7`, UTC-7) with no DST shifting. Verified: a
14:00 local record maps to 21:00 UTC.

## QA checks
- All 8 required schema columns present, in order; no extra columns.
- 56,861 output rows; 0 rows with unparseable timestamps.
- VWC range 0.0557–0.5043 (physically plausible fractions).
- 7 depths present; `replicate` uniformly 1; `is_timeseries` uniformly True.
- Location file resolves the single site "BM" with valid coordinates.

## Outputs
- `ess-dive-38e901ec3d7bd24-20230504T211548257225_harmonized.csv` — harmonized measurements
- `ess-dive-38e901ec3d7bd24-20230504T211548257225_location.csv` — site coordinates + `source_dataset_id` + `qc_flag`
- `sm_data_harmonization_mapping.json` — mapping entry (index 7)
- `dataset_07.py` — generated transformation code

## Open questions / limitations
- **DOI unavailable:** no metadata was staged, so `doi` is recorded as `null`
  rather than retrieved externally.
- **Timezone** assumed fixed MST (no DST) by regional convention; the package does
  not state the offset explicitly.
- The CO2 file is used only for coordinates; its own CO2 measurements are outside
  the target schema and intentionally excluded.
