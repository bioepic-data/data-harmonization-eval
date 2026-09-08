# Harmonization notes — dataset 10

- **Dataset identifier:** `ess-dive-01092fc392bc46d-20240819T143818677`
- **Canonical index (from MANIFEST.json):** 10 (retained; not reassigned)
- **Payload file:** `Soil_water_content_Fig4e.csv`

## Payload identification
The package stages a single CSV, `Soil_water_content_Fig4e.csv`. Its filename
indicates data digitized from a manuscript figure (Fig. 4e). It has a header
row followed by a units row (`YYYY-MM-DD`, `m3/m3`, ...) and 105 dated rows.
Columns: `Date`, `PLM1 _vol_water_content`, `PLM2 _vol_water_content`,
`PLM3 _vol_water_content`. This is the only file, so it is necessarily the
measurement payload.

## Inclusion decision — INCLUDE
- Rule 2 (measurement type): contains direct volumetric water content (VWC)
  observations reported in m3/m3. Pass.
- Rule 4 (extractable payload): a parseable dated measurement table exists. Pass.
- No duplicate/superseded signal available in-workspace (Rule 1 not triggered).
- No experimental-manipulation signal in the payload (Rule 3 not triggered).

## Variable mapping
| Target column | Source | Notes |
|---|---|---|
| `datetime_UTC` | `Date` (`%Y-%m-%d`) | Date-only; no time/timezone reported. Localized to UTC (midnight). |
| `site_id` | column names | `PLM1`, `PLM2`, `PLM3` parsed from the three value columns. |
| `depth_m` | — | Not reported anywhere; set NA (see limitation below). |
| `replicate` | — | Not reported; set to 1. |
| `is_timeseries` | inferred True | Repeated observations per site across 2017–2021. |
| `volumetric_water_content_m3_m3` | `PLM* _vol_water_content` | Already m3/m3; no unit conversion. |
| `gravimetric_water_content_gH2O_gs` | — | Not reported; NA. |
| `water_potential_kPa` | — | Not reported; NA. |

## Time series determination
`is_timeseries = True` — each PLM site has many observations at varying dates
(≈105 dates spanning 2017-05 to 2021-05). Sampling is irregular (mixed
biweekly/monthly), so `interval_min` is left as NA (not emitted; the target
schema does not retain an interval column, and it would be NA regardless).

## Location resolution — qc_flag = g2
No location metadata file is present in the package, no cached ESS-DIVE
metadata is staged (`data/external/ess-dive_meta/` absent), and the index-0
reference location dataset's CSV is not staged in this workspace (only the
mapping JSON references it). Per SECTION 5, coordinates are therefore
unresolvable: `latitude/longitude = NA`, `qc_flag = "g2"`. Site IDs `PLM*`
resemble East River / Pumphouse Lower Montane identifiers but were not resolved
to coordinates without an in-workspace authoritative source.

## Missing-value handling
Sentinel `-9999` (present in the PLM3 column for four 2020–2021 dates) is
mapped to NA and those rows dropped, yielding 305 harmonized rows
(103 dates × 3 sites = 309 cells, minus 4 `-9999` entries).

## Data quality checks
- All 8 required schema columns present, in canonical order.
- VWC range after harmonization: 0.056–0.498 m3/m3 (physically plausible).
- No `-9999` values remain in the output.
- Timestamps emitted as ISO-8601 UTC (`...Z`).

## Open questions for operator review
1. **Depth unknown.** No measurement depth is given in the payload, column
   names, or any in-workspace metadata. `depth_m` is NA. If the source figure
   caption or package metadata specifies a depth, it should be backfilled.
2. **DOI unknown.** No DOI is available in the workspace; `doi` set to null.
3. **Coordinates unresolved (g2).** If an approved location registry or cached
   metadata becomes available, PLM1/PLM2/PLM3 coordinates should be resolved
   and `qc_flag` cleared.
4. **Timezone assumption.** Dates are date-only; UTC midnight was used rather
   than assuming a local (e.g., Mountain) offset, because no time component or
   timezone is reported.

## Deliverables in `output/`
- `dataset_10.py` — harmonization code following the modular `common.py` pattern.
- `run_dataset_10.py` — self-contained runner used to generate the CSVs in this
  fold workspace (reads from `inputs/raw/`).
- `ess-dive-01092fc392bc46d-20240819T143818677_harmonized.csv` — harmonized data.
- `ess-dive-01092fc392bc46d-20240819T143818677_location.csv` — location records (g2).
- `sm_data_harmonization_mapping.json` — mapping entry (index 10).
- `dataset_10_notes.md` — this file.
