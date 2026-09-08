# Harmonization Notes — Dataset 8

- **Dataset:** `ess-dive-61a0ecd70856892-20230808T205724993`
- **Canonical index:** 8 (from `MANIFEST.json`; retained, not reassigned)
- **Site:** Slate River OBJ-2 (SLAC Groundwater Quality SFA)
- **Decision:** INCLUDE

## Payload identification

Package contains 8 files: 4 annual `*_data.csv` measurement files (2018–2021)
and 4 matching `*_InstallationMethods.csv` files. The `*_data.csv` files are the
measurement payload (timestamped, wide-format sensor tables). The
`*_InstallationMethods.csv` files serve double duty as location metadata
(`Latitude`/`Longitude`/`SiteName`) and sensor metadata (make/model/depth
descriptions), so they are listed in both `location_metadata_files` and
`sensor_metadata_files`.

## Inclusion / exclusion (SKILL Section 3)

- Rule 2 (measurement type): PASS — direct sensor observations of volumetric
  water content (`SoilMoisture_*.m3.m3`, CS655) and soil matric potential
  (`SoilMatricPot_*.kPa`).
- Rule 3 (manipulation): none — ambient monitoring station, no treatment.
- Rule 4 (payload): PASS — parseable time-stamped CSV tables.
- Rule 5 (metadata): PASS — station coordinates present in the package.
- Rule 1 (duplicate/superseded): not evident from the staged package; no other
  target datasets available for comparison in this fold.

## Variable mapping

| Source | Target | Notes |
|---|---|---|
| `DateTime.MST` | `datetime_UTC` | MST fixed offset UTC-7 (`Etc/GMT+7`) → UTC |
| `SoilMoisture_<d>cm.m3.m3` | `volumetric_water_content_m3_m3` | already m³/m³, no unit conversion |
| `SoilMatricPot_<d>cm.kPa` | `water_potential_kPa` | already kPa (negative), no conversion |
| depth embedded in column name | `depth_m` | cm → m (÷100) |
| `SiteName` / constant | `site_id` | single station "Slate River OBJ-2" |
| `Latitude` / `Longitude` | location file | 38.90943, -107.028242 (WGS84) |

Ignored non-target columns: SoilTemp, SoilBulkEC, SoilCO2, SoilO2,
EnclosureTemp, BarometricPress, ScansPerRec, DataFlag_01.

## Time series (SKILL Section 4)

`is_timeseries = True` — continuous datalogger output (CR1000X) at a regular
30-minute cadence across multiple years. `interval_min` is not part of the
target column schema in `ensure_harmonized_cols`, so it is not emitted as a
column.

## Location resolution (SKILL Section 5)

Source 2 (package ancillary file). Coordinates taken directly from the
InstallationMethods files; identical across all rows and years. `qc_flag`
left null (coordinates resolved). Written to
`<id>_location.csv` via the location accumulator convention.

## Depth handling detail

VWC sensors report depths 40, 60, 82.5 cm; matric-potential sensors report
40, 60, 79, 100 cm. Because the two variable families do not fully share
depths, the long→wide pivot yields rows where only one of VWC / water potential
is populated at 79 cm and 100 cm (matric-pot only) and 82.5 cm (VWC only). This
is expected and preserved rather than force-aligned.

## Missing values

`-9999` sentinels converted to `NaN` and dropped prior to pivoting. The 2018
data file predates the matric-potential and CO2/O2 sensors, so those columns
are absent that year (water potential begins 2019-08).

## Limitations

- **DOI:** not present in the staged package or any permitted workspace source;
  recorded as `null` in the mapping entry rather than retrieved externally.
- **`pyproj` unavailable** in the run environment, but not needed — coordinates
  are already WGS84 decimal degrees (no UTM conversion required).
- Cross-dataset location de-duplication (Union-Find in the expert `common.py`)
  is a global post-processing step across all datasets and is out of scope for
  this single-fold run; the per-dataset location accumulator is emitted instead.

## Outputs

- `ess-dive-61a0ecd70856892-20230808T205724993_harmonized.csv` — 195,524 rows;
  datetime range 2018-10-05 → 2022-01-01 UTC; VWC 0.437–0.58 m³/m³;
  water potential −9.4 to −5.2 kPa.
- `ess-dive-61a0ecd70856892-20230808T205724993_location.csv`
- `sm_data_harmonization_mapping.json` — mapping entry (index 8)
- `dataset_08.py` — generated transformation code
