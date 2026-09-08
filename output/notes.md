# Harmonization notes — dataset index 6

- **Dataset identifier:** `ess-dive-18e91eb74405882-20241017T173226640`
- **Canonical index:** 6 (retained from `MANIFEST.json`; not reassigned)
- **Payload file:** `Snodgrass_ESS.csv`

## Payload identification
The package contains a single CSV. Its first row is the machine-readable
column header; the next two rows are descriptive (long variable names and
units) and are skipped on read (`skiprows=[1, 2]`). The file is a wide-format
half-hourly logger export combining meteorological, soil temperature, CO2, and
soil moisture channels for four forested sites in the East River / Snodgrass
area.

## Inclusion decision: INCLUDE
- **Rule 2 (measurement type):** Contains direct volumetric water content (VWC)
  observations at 5, 15, and 50 cm (`VWC_5cm`, `VWC_15cm`, `VWC_50cm`), reported
  in m3/m3 (values 0.02–0.54, consistent with VWC). No gravimetric content or
  water potential is present.
- **Rule 3 (manipulation):** No experimental manipulation; sites are natural
  aspen and mixed-conifer stands (`tree_cover` = aspen / mixed-conifer). Included
  without a flag.
- **Rule 4 (payload):** Machine-readable time-stamped table present.
- **Rule 5 (metadata):** Site coordinates are embedded per row in the payload.

Non-soil-moisture columns (soil/air temperature `T_*`, `AirT_*`, CO2 `CO2_*`,
battery, radiation, rain, wind, pressure, humidity, lightning) were not mapped.

## Variable mapping
| Target | Source | Notes |
|---|---|---|
| `datetime_UTC` | `TIMESTAMP` | Already UTC (header documents "date_time UTC"); parsed `mm/dd/yy HH:MM`, localized to UTC with no offset conversion. |
| `site_id` | `site` | 4 sites: low_aspen, middle_aspen, middle_conifer, high_conifer. |
| `depth_m` | column-name suffix of `VWC_*cm` | cm -> m (divide by 100): 0.05, 0.15, 0.50. |
| `volumetric_water_content_m3_m3` | `VWC_5cm`, `VWC_15cm`, `VWC_50cm` | Wide -> long melt; source already m3/m3, no unit conversion. |
| `replicate` | — | Not in source; set to 1. |
| `is_timeseries` | — | True. |
| `water_potential_kPa` | — | Not measured; NaN. |
| `gravimetric_water_content_gH2O_gs` | — | Not measured; NaN. |

## Time series determination
`is_timeseries = True`. Median timestamp spacing per site is 30 minutes across
2021-07-23 to 2024-06-08, i.e., a continuous logger deployment. Per skill
convention `interval_min` is not a required output-schema column, so it is not
emitted in the harmonized CSV, but the inferred nominal interval is 30 min.

## Location resolution
Source 1 (coordinates in the payload file). Each site carries a single constant
`latitude`/`longitude` pair:

| site_id | latitude | longitude |
|---|---|---|
| low_aspen | 38.926196 | -106.97144 |
| middle_aspen | 38.928400 | -106.97812 |
| middle_conifer | 38.927448 | -106.97852 |
| high_conifer | 38.931421 | -106.98524 |

All four resolve directly, so `qc_flag = None` (no `g1`/`g2`). No depth
approximation, so no `d1` flag.

## Limitations
- **DOI unavailable.** No cached ESS-DIVE metadata was supplied
  (`data/external/ess-dive_meta/` is absent) and external lookups are not
  permitted in fold-evaluation mode. `doi` is recorded as `null`.
- **Missing values:** ~50 NaN VWC readings per depth are retained as NaN. No
  `-9999` sentinel was observed in the VWC columns (a `NA` string appears in
  other, unmapped columns such as `CO2_2cm`).
- The payload doubles as the location metadata source; it is listed under both
  `data_payload_files` and `location_metadata_files` in the mapping entry.

## Outputs written
- `ess-dive-18e91eb74405882-20241017T173226640_harmonized.csv` — 618,408 rows
  (206,136 timestamps x 3 depths), 8 schema columns.
- `location_data_harmonized.csv` — 4 sites with coordinates and qc_flag.
- `sm_data_harmonization_mapping.json` — mapping entry (index 6).
- `dataset_06.py` — transformation code (mirrors expert modular pattern:
  `harmonize(ctx) -> DatasetResult`, using helpers from `common.py`).
