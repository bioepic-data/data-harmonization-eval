# Held-out Dataset 18 Mapping Notes

Dataset identifier: `ess-dive-b924878d23c9dd7-20250214T163427929`

Decision: INCLUDE. The package has one machine-readable CSV with direct gravimetric soil water content observations, collection dates, depth increments, site hierarchy fields, replicate identifiers, and embedded coordinates for most rows.

Payload: `2017_East_River_Pumphouse_Soil_Water_Content_and_pH__1_.csv` read with `latin1` encoding.

DOI: `UNKNOWN_FROM_ALLOWED_INPUTS`. No fold-local metadata cache was present and the allowed held-out raw CSV did not include DOI metadata.

Harmonization choices:
- `Date_Collected` is parsed as `%m/%d/%Y` in `America/Denver` and converted to UTC ISO strings.
- `site_id` concatenates `Location`, `Field_Site`, `Block`, `Plot`, `Replicate`, and non-missing `Topographic_Position`.
- `Depth_Increment` maps `0-5 cm` to `0.025`, `5-15 cm` to `0.10`, `15-May` to `0.10`, and `15 cm +` to `0.15` meters.
- `Soil Water Content (g H2O per gram  soil)` maps directly to `gravimetric_water_content_gH2O_gs`; four rows missing that value are omitted.
- Volumetric water content and water potential are not reported and are populated as missing values.
- The data are discrete sampling observations, so `is_timeseries` is `False` and `interval_min` is missing.

Location notes: `Latitude`/`Longitude` are present in the payload for most rows; 57 raw rows lack one or both coordinate values. The required held-out harmonized CSV does not include location columns, but companion location records derived only from this payload should flag those missing-coordinate sites as `g2`.
