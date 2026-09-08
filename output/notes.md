# Harmonization notes — dataset index 9

- **Dataset identifier:** `ess-dive-460e696d8210ed3-20260309T155937802`
- **Canonical index (from MANIFEST.json):** 9 (retained; not reassigned)
- **Payload file:** `NEON_plot_TDR.csv` (375 rows, one per NEON plot)
- **Decision:** INCLUDE — contains direct volumetric water content (VWC) observations.

## Payload identification
Single staged file `NEON_plot_TDR.csv`. It serves as both the data payload and
the location metadata source (coordinates embedded per plot). No README,
metadata JSON, sensor file, or separate location file is present in the
workspace.

Columns:
`SampleSiteCode, Easting, Northing, VegetationType, Site, Collection Date,
VWC_1, VWC_2, avg_VWC, Temp_1, Temp_2, avg_Temp`

- `VWC_1`, `VWC_2` — two replicate TDR volumetric water content readings (%).
- `avg_VWC` — mean of the two replicates; not used (redundant).
- `Temp_1`, `Temp_2`, `avg_Temp` — soil/probe temperature; out of schema scope, dropped.
- `VegetationType`, `Site` — ancillary grouping; not part of target schema.

## Inclusion/exclusion (SKILL Section 3)
- RULE 2 (measurement type): PASS — direct VWC observations.
- RULE 3 (manipulation): none detected (natural vegetation-type survey).
- RULE 4 (payload): PASS — machine-readable CSV table.
- RULE 5 (metadata): PASS — UTM coordinates present per plot.

## Time-series determination (SKILL Section 4)
`is_timeseries = False`. Each plot has a single `Collection Date` (a discrete
field campaign spanning 2018-06-14 to 2018-06-28 across sites); there is one
observation per plot, not continuous sensor output. `interval_min = NA`.

## Variable mapping
| Target | Source | Conversion |
|---|---|---|
| `datetime_UTC` | `Collection Date` (`%Y-%m-%d`) | Date only; localized to UTC 00:00 |
| `site_id` | `SampleSiteCode` | rename |
| `depth_m` | — | NA (not reported; see limitation) |
| `replicate` | `VWC_1`/`VWC_2` suffix (1, 2) | wide→long |
| `volumetric_water_content_m3_m3` | `VWC_1`, `VWC_2` | ÷100 (% → m³/m³) |
| `gravimetric_water_content_gH2O_gs` | — | NA |
| `water_potential_kPa` | — | NA |

## Location resolution (SKILL Section 5)
Source 1 (coordinates in payload). `Easting`/`Northing` are UTM Zone 13N
(EPSG:32613); reprojected to EPSG:4326. Resulting coordinates fall in the East
River / Rocky Mountain Biological Laboratory area near Crested Butte, CO
(~38.9°N, ~107.0°W), consistent with the other WFSFA East River datasets
(e.g., datasets 15 and 26). All 375 plots resolved; `qc_flag` = none (no `g2`).

## Reference exemplars used
- **Dataset 15** (`ess-dive-987726ef1235abc...`, ER TDR survey): closest
  structural analog — discrete campaign, VWC% wide→long by replicate, UTM
  Zone 13N reprojection. Code pattern followed.
- **Dataset 26** (`ess-dive-f782da867133296...`, ER18 plots): JSON schema
  pattern and `SampleSiteCode` handling.

## Data-quality handling
- Sentinel `-9999` replaced with NA before conversion (affects some `Temp`
  values and is applied defensively to VWC).
- Output: 375 plots × 2 replicates = **750 rows**; 78 VWC values are NA
  (blank/sentinel readings). VWC range after conversion: 0.0–0.523 m³/m³.

## Limitations
- **Depth not resolvable:** the payload has no depth column and no package
  metadata/README is staged in this workspace to supply a sampling depth.
  `depth_m` is populated with NA. (The analogous ER TDR survey, dataset 15,
  used 25 cm sourced from package metadata that is unavailable here.) Per
  AGENT_INSTRUCTIONS, this limitation is recorded rather than retrieved
  externally.
- **DOI not available:** no metadata file in the workspace provides the DOI;
  set to `null`.

## Outputs written to `output/`
- `ess-dive-460e696d8210ed3-20260309T155937802_harmonized.csv`
- `ess-dive-460e696d8210ed3-20260309T155937802_location.csv`
- `dataset_09.py` (generated transformation code)
- `sm_data_harmonization_mapping.json` (change-mapping entry, index 9)
- `notes.md` (this file)
