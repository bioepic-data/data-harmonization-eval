# Held-out Dataset 08 Harmonization Notes

Dataset: `ess-dive-61a0ecd70856892-20230808T205724993`  
DOI: `doi:10.15485/1958210`

Decision: INCLUDE. The raw package contains machine-readable sensor time series with direct volumetric water content and soil matric potential observations.

Files classified as payload:
- `SLT_OBJ2_SoilSensors_2018_data.csv`
- `SLT_OBJ2_SoilSensors_2019_data.csv`
- `SLT_OBJ2_SoilSensors_2020_data.csv`
- `SLT_OBJ2_SoilSensors_2021_data.csv`

Files classified as location/sensor metadata:
- `SLT_OBJ2_SoilSensors_2018_InstallationMethods.csv`
- `SLT_OBJ2_SoilSensors_2019_InstallationMethods.csv`
- `SLT_OBJ2_SoilSensors_2020_InstallationMethods.csv`
- `SLT_OBJ2_SoilSensors_2021_InstallationMethods.csv`

Mapping decisions:
- `DateTime.MST` is parsed as fixed MST (`Etc/GMT+7`) and converted to UTC.
- `SoilMoisture_<depth>cm.m3.m3` maps to `volumetric_water_content_m3_m3`; no unit conversion.
- `SoilMatricPot_<depth>cm.kPa` maps to `water_potential_kPa`; no unit conversion.
- Depth is parsed from the column name in cm and divided by 100.
- Site is the single installation metadata site `Slate River OBJ-2`.
- Coordinates are present in installation metadata and package spatial coverage: 38.90943, -107.028242. No location QC flag is needed.
- Replicate is set to 1 because no replicate identifier is present.
- `-9999` values are treated as missing. Rows with both target values missing after replacement are dropped.
- Time series status is true. `interval_min` is computed per source file; the modal cadence is 30 minutes, with a 120 minute gap observed in 2019.

Expected schema:
`datetime_UTC, site_id, depth_m, replicate, is_timeseries, interval_min, volumetric_water_content_m3_m3, gravimetric_water_content_gH2O_gs, water_potential_kPa`
