# Mapping Notes: dataset 23

Dataset: `ess-dive-a99be52b7a6114c-20230504T210134503379`  
DOI: `doi:10.15485/1842908`  
Decision: INCLUDE

`WM_SWC.csv` contains direct hourly soil water content measurements (`Sensor.Type == SWC`) from the warming experiment near the Rocky Mountain Biological Laboratory. `plot_metadata.csv` identifies plots as control or heated, so the dataset is included but documented as experimentally manipulated.

The harmonizer joins `WM_SWC.csv` to `sensor_metadata.csv` by `Sensor.SN`. It constructs `site_id` as `Plot.Location_Point.Location_Veg`, converts `Depth.cm` to `depth_m`, assigns replicate numbers from sorted sensor serials within each site/depth, and uses `Measurement` directly as fractional volumetric water content (`m3/m3`). Timestamps are interpreted as fixed Mountain Standard Time (`Etc/GMT+7`) logger timestamps and written as UTC ISO strings.

Rows retained: 1722716. Rows excluded: 36. The excluded rows are from sensor `9731453`; the sensor metadata note says it was left plugged in but out of the ground, and it has no point, vegetation, or depth metadata.

Specific plot coordinates were not available in the raw files. Public package metadata provides only a broad East River bounding box, so plot-level location records would need `qc_flag = g2` unless an allowed external location registry is used.
