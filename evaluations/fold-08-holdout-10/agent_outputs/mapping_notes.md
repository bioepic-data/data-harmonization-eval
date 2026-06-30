# Held-out Dataset 10 Mapping Notes

Decision: INCLUDE.

The package metadata identifies the dataset as `doi:10.15485/2322567` and the held-out raw cache contains one relevant soil-moisture payload, `Soil_water_content_Fig4e.csv`. The first data row is a units row (`YYYY-MM-DD`, `m3/m3`, `m3/m3`, `m3/m3`), so harmonization skips that row before parsing dates and measurements.

The source is wide by site. Columns `PLM1 _vol_water_content`, `PLM2 _vol_water_content`, and `PLM3 _vol_water_content` are melted to long format and normalized to site IDs `ER-PLM1`, `ER-PLM2`, and `ER-PLM3` to match WFSFA location identifiers. Values are already volumetric water content in `m3/m3`, so no unit conversion is applied.

Depth is not present in the source file or the package metadata for this figure-level table, so `depth_m` is `NaN`. The repeated dated observations make this a time series, but the intervals are irregular; the output stores per-site elapsed minutes since the previous observation, leaving the first interval for each site missing.

Location coordinates are not written to `heldout_harmonized.csv` because the target held-out CSV schema has only the nine soil-moisture columns. For curation provenance, PLM coordinates were resolvable from the raw Varadharajan location registry referenced by fold-local mapping index 0, which would imply `g1` if a location output were required.
