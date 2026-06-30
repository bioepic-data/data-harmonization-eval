# Held-out Dataset 17 Mapping Notes

Decision: INCLUDE.

Package: `ess-dive-be919d7d5d42c94-20240130T205332180`  
DOI: `doi:10.15485/2283406`

The package contains five soil moisture and temperature payload files under `FieldData/Soil_Moisture_Data/`: `TMC1.csv`, `TMC2.csv`, `TMC4.csv`, `TMC5.csv`, and `TMC6.csv`. Each file has a `DateTime` column, four volumetric water content columns (`MC_0.1m`, `MC_0.3m`, `MC_0.6m`, `MC_0.8m`), plus temperature and electrical conductivity columns that are not part of the target schema. The first data row is a units row and is skipped by the harmonizer.

`Locations.csv` maps TMC site IDs to Easting/Northing coordinates. ESS-DIVE metadata describes the CRS as NAD83 / UTM Zone 13N. The harmonized CSV follows the target observation schema and does not include location columns.

Timestamps are parsed as `America/Denver` local time and converted to UTC. The series are hourly after averaging from 15-minute source measurements, so `is_timeseries=True` and `interval_min` is computed within each site/depth series. VWC units are `V/V`, so no numeric unit conversion is applied.
