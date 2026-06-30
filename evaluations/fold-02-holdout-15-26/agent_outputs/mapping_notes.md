# Held-out Mapping Notes

## Dataset 15

- Included: direct TDR volumetric water-content measurements.
- Rows: 286 long-format VWC readings from 101 survey points and up to three replicate TDR columns.
- Date handling: the CSV lacks row-level dates; package temporal coverage starts on 2019-07-02, so all rows use 2019-07-02 local midnight converted to UTC.
- Depth handling: package metadata states the TDR survey was at 25 cm, mapped to depth_m = 0.25.
- Site handling: GPS_id is used as point-level site_id; coordinates are embedded as EPSG:32613 Easting/Northing in the payload.

## Dataset 26

- Included: soil-core volumetric water content and computable gravimetric water content from wet/dry weights.
- Rows: 425 rows with at least one moisture measurement; rows containing only texture/bulk-density fields were excluded from the target moisture table.
- Depth handling: reported top and bottom sample depths are converted to midpoint depth in meters; this is a depth-range approximation (qc d1 conceptually, but qc_flag is not part of the target CSV schema).
- Location handling: no per-site coordinates are present in the payload; package metadata has only a bounding box, so exact site coordinates would be g2 if a location table were emitted.

## Output Schema

The concatenated CSV contains exactly these columns: datetime_UTC, site_id, depth_m, replicate, is_timeseries, interval_min, volumetric_water_content_m3_m3, gravimetric_water_content_gH2O_gs, water_potential_kPa.
