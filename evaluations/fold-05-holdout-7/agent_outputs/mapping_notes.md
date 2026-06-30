# Held-out Mapping Notes: dataset 7

Package: `ess-dive-38e901ec3d7bd24-20230504T211548257225`  
DOI: `doi:10.15485/1660455`

Decision: INCLUDE. The primary payload `BM_Merged_T_VWC_0616_1018.csv` contains direct, depth-resolved volumetric water content observations with parseable local timestamps. The package metadata describes this file as datalogger output from seven Campbell CS655 soil moisture and temperature sensors at Bradley Meadow.

Mapping choices:
- `date.time` is parsed with `%m/%d/%y %H:%M` and localized to `America/Denver`, matching the East River, Colorado convention used by fold-local examples.
- `site_id` is assigned as `BM`, supported by the raw file prefixes and `BM_EGM_Well_CO2.csv` location field.
- `Depth (cm)` is divided by 100 to produce `depth_m`; observed depths are 0.10, 0.20, 0.30, 0.50, 0.75, 1.00, and 1.30 m.
- `Volumetric Water Content` is copied directly to `volumetric_water_content_m3_m3`; observed values range from 0.0557 to 0.5043, consistent with fractional m3/m3 rather than percent.
- `replicate` is set to 1 because the merged payload has one stream per depth and no sensor identifier column.
- `is_timeseries` is true. `interval_min` is calculated as the within-site/depth/replicate timestamp difference in minutes; the median interval is 60 minutes.
- Coordinates are resolved from `BM_EGM_Well_CO2.csv`: latitude 38.98715, longitude -107.003863. Coordinates are documented in the mapping and curator bundle, but the requested harmonized CSV schema does not include latitude/longitude columns.

Uncertainties:
- No README or methods file was present in the allowed raw directory. Timezone is inferred from site geography and fold-local examples.
- `BM_EGM_Surface_Flux.csv` has 36 non-null `Soil.Moisture` values, but it is a CO2 surface-flux file with no depth metadata and is not included in the harmonized soil moisture output.
