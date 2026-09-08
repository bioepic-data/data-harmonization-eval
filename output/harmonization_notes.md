# Harmonization notes — fold-08, target index 26

**Dataset:** `ess-dive-f782da867133296-20230504T211008637996`
**Payload file:** `ER18_soil_physical.csv` (586 rows, 25 columns)
**Decision:** INCLUDE

## Payload identification

Only one file is staged (`ER18_soil_physical.csv`). It is the measurement payload:
a soil physical characterization table with one destructive soil sample per
`SampleSiteCode`. It reports bulk density, texture (sand/silt/clay), and
`water content %vol` (volumetric water content in percent). No README, location,
or sensor metadata files are present in the package.

## Inclusion / exclusion

- RULE 2 (measurement type): the file contains direct observations of volumetric
  water content (`water content %vol`). INCLUDE.
- RULE 4 (extractable payload): machine-readable CSV with dated rows. Pass.
- No experimental-manipulation indicators (this is an ambient East River watershed
  characterization campaign).

## Variable mapping

| Target | Source | Notes |
|---|---|---|
| `datetime_UTC` | `Collection date` | Format `%m/%d/%y`, local tz America/Denver → UTC |
| `site_id` | `SampleSiteCode` | e.g. `001-ER18` |
| `depth_m` | `Top sample depth_cm`, `Bottom sample depth_cm` | midpoint / 100; `qc_flag='d1'` (range) |
| `replicate` | — | discrete campaign, one sample per site → 1 |
| `is_timeseries` | — | `False` (single observation per site+depth) |
| `volumetric_water_content_m3_m3` | `water content %vol` | ÷100 (% → m³ m⁻³) |
| `gravimetric_water_content_gH2O_gs` | — | not reported → NA |
| `water_potential_kPa` | — | not reported → NA |

## Time-series determination

`is_timeseries = False`, `interval_min = NaN`. Each `SampleSiteCode` has a single
collection date (a June/July/September 2018 sampling campaign, with one 2019 date);
these are discrete campaign sampling dates, not continuous sensor output.

## Depth handling

Two depth increments are present: 2.5–7.5 cm (426 rows) and 50–55 cm (159 rows).
Depth is taken as the reported range midpoint and converted to meters, so
`qc_flag = "d1"` is assigned. All rows carrying a `water content %vol` value fall in
the 2.5–7.5 cm increment (midpoint 0.05 m); the 50–55 cm increment rows have no
reported water content and are dropped (425 output rows). One row has neither a
depth nor a collection date and no water content; it is dropped by the
water-content filter.

## Location resolution

No coordinates are present in the payload. There is no ancillary location file, no
sensor metadata file, and no cached ESS-DIVE package metadata in the workspace
(`data/external/ess-dive_meta/` is absent). No approved location registry was
supplied. Per SECTION 5 the coordinates are therefore unresolvable within the run
workspace: `latitude`/`longitude` = NA and `qc_flag = "g2"`. Coordinates recorded in
the accompanying `*_location.csv`. (Note: index 0 — the East Taylor / Varadharajan
location identifier dataset — is not staged in this fold, so no fallback lookup was
possible.)

## Data-quality observations (flagged for operator review)

- One record has a missing `Collection date` and yields `NaT`; it is dropped by the
  water-content filter, so it does not appear in the output.
- A few `water content %vol` values are physically implausible (min −12.31 %,
  max 104.03 %). These are retained as reported (only `-9999` sentinels are treated
  as missing, per expert convention) and are flagged here for review; they translate
  to VWC values outside the plausible 0–1 m³ m⁻³ range in the output.
- `doi` is unknown: no metadata source in the workspace provides it, so it is set to
  `null` in the mapping entry.

## Missing inputs / limitations

- No package README or metadata staged → DOI and coordinates unavailable.
- `data/external/ess-dive_meta/` absent → no cached metadata fallback.
- Index 0 location registry not staged in this fold → no coordinate fallback.

## Outputs

- `ess-dive-f782da867133296-20230504T211008637996_harmonized.csv` — 425 rows, 8-column schema.
- `ess-dive-f782da867133296-20230504T211008637996_location.csv` — 425 site rows (lat/lon NA, `qc_flag='g2'`).
- `sm_data_harmonization_mapping.json` — mapping entry, retaining canonical index 26.
- `dataset_26.py` — transformation code.
