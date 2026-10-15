# Harmonization notes — Dataset 9

- **Dataset identifier:** `ess-dive-460e696d8210ed3-20260309T155937802`
- **DOI:** `doi:10.15485/3013006`
- **Title:** Geophysical survey associated with NEON AOP survey, East River, CO 2018 (Watershed Function SFA)
- **Canonical index (from MANIFEST.json):** 9 — retained; not reassigned.

## Payload identification

Staged input contained a single file, `NEON_plot_TDR.csv`. Per the package
metadata, the full package also contains `NEON_2018_EMI_survey.zip` (EMI
apparent electrical conductivity shapefile), `flmd.csv`, and `dd.csv`; these
were **not** staged in `inputs/raw/` and are not needed for soil-moisture
harmonization. `NEON_plot_TDR.csv` is the measurement payload: plot-level
Time-Domain Reflectometry (TDR) readings of volumetric water content (VWC, %)
and soil temperature (not harmonized).

## Inclusion decision: INCLUDE

- Rule 2 (measurement type): contains direct VWC observations. INCLUDE.
- Rule 4 (extractable payload): machine-readable dated measurement table present.
- Rule 5 (metadata): per-plot UTM coordinates present in the payload.
- The EMI electrical-conductivity layer is a geophysical proxy and is excluded
  from harmonization; only the TDR VWC observations are harmonized.

## Variable mapping

| Target column | Source | Notes |
|---|---|---|
| `datetime_UTC` | `Collection Date` | Campaign date; localized America/Denver → UTC. No time-of-day reported. |
| `site_id` | `SampleSiteCode` | 375 distinct plots (e.g. `001-ER18`). |
| `depth_m` | metadata (methods) | TDR 20-cm probe length → 0.20 m. Approximated → `qc_flag = d1`. |
| `replicate` | `VWC_1`, `VWC_2` | Two per-reading columns → replicates 1 and 2. |
| `is_timeseries` | — | `False` (one-time plot sampling campaign). |
| `volumetric_water_content_m3_m3` | `VWC_1`, `VWC_2` | % → m³ m⁻³ (÷100). `-9999` → NaN. |
| `gravimetric_water_content_gH2O_gs` | — | Not reported → NaN. |
| `water_potential_kPa` | — | Not reported → NaN. |

- `avg_VWC`, `Temp_1`, `Temp_2`, `avg_Temp`, and `VegetationType` are not part
  of the target schema. `avg_VWC` is a derived mean of the two readings and is
  dropped in favor of the per-reading replicate values.

## Time-series determination

`is_timeseries = False`. Each plot has a single collection date (discrete
field campaign, 14–28 June 2018); the package methods describe a one-time plot
survey, not a continuous sensor deployment.

## Location resolution

Priority order step 1: coordinates present in the payload itself as UTM
`Easting`/`Northing`. Reprojected from EPSG:32613 (WGS84 UTM Zone 13N) to
EPSG:4326. All 375 plots resolved (`qc_flag` empty). Resulting coordinates fall
within the package spatial-coverage bounding box (lat ≈ 38.86–38.99,
lon ≈ -107.10 to -106.95; metadata box lat 38.81–39.03, lon -107.13 to -106.87).

## Data-quality handling

- **Missing-value sentinel:** `-9999` in `VWC_1`/`VWC_2` (39 rows each) set to
  NaN. Harmonized VWC range after conversion: 0.0–0.523 m³ m⁻³.
- **Corrupted dates:** 4 `RMBL - RM` rows (`SampleSiteCode` 324–327-ER18) have
  a spreadsheet `####` overflow in `Collection Date`; these coerce to NaT
  (8 harmonized rows across 2 replicates). Their coordinates and VWC values are
  valid and retained. Contextually these plots belong to the 2018-06-14
  RMBL - RM collection, but the date was not imputed to avoid inventing a value.

## Output summary

- `..._harmonized.csv`: 750 rows (375 plots × 2 replicates), 8 schema columns
  plus `qc_flag`.
- `..._location.csv`: 375 rows (one per distinct `site_id`), columns
  `site_id,latitude,longitude,source_dataset_id,qc_flag`.

## Open questions / limitations

1. Depth (0.20 m) is approximated from the reported 20-cm TDR probe length
   rather than an exact measurement depth; flagged `d1`.
2. Time-of-day is not reported; `datetime_UTC` carries the collection date at
   local midnight (Denver) converted to UTC.
3. The package methods state three readings per plot were averaged, but only
   two per-reading columns (`VWC_1`, `VWC_2`) plus `avg_VWC` are present; the
   third reading is not available, so two replicates are emitted.
4. Non-staged package files (EMI shapefile, flmd.csv, dd.csv) were not
   available in the workspace and were not retrieved externally.
