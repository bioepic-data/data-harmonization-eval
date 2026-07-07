# Held-out soil moisture harmonization notes

Dataset: `ess-dive-460e696d8210ed3-20260309T155937802`  
DOI: `doi:10.15485/3013006`

## Decision

INCLUDE. The allowed raw package contains `NEON_plot_TDR.csv`, a machine-readable CSV with dated direct TDR volumetric water content observations. `SampleSiteCode`, `Easting`, and `Northing` provide site identity and location metadata in the payload.

## Payload interpretation

- `VWC_1` and `VWC_2` are treated as two replicate volumetric water content observations.
- `avg_VWC` is a derived average and is not emitted as a separate observation.
- `VWC_*` source units are percent, converted to `m3/m3` by dividing by 100.
- `Collection Date` is parsed as an America/Denver local date and converted to UTC.
- The observations are discrete campaign samples, so `is_timeseries = False` and `interval_min = NaN`.
- The allowed raw file does not report sampling depth; `depth_m` is left missing.

## Filtering

Rows with unparseable collection dates are dropped. Replicate values equal to `-9999` are treated as missing sentinel values and dropped after reshaping.

## Location

Coordinates are embedded in the payload as `Easting` and `Northing`; the mapping documents reprojection from EPSG:32613 to EPSG:4326. No location QC flag is needed because coordinates are present in the source.
