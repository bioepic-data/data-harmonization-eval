# Harmonization notes — dataset index 24

- **Dataset:** `ess-dive-daa156d2129c471-20250716T160748658`
- **Canonical index (from MANIFEST.json):** 24 (retained; not reassigned)
- **Decision:** INCLUDE

## Files
- `Iso_MP_Sap_DataDaily_ESSDiveUpload_R1.csv` — data payload (semicolon-delimited,
  956 daily rows, 406 columns).
- `Locations.csv` — location metadata (semicolon-delimited; `ID`, `Latitude`,
  `Longitude` in decimal degrees, plus ancillary columns).

## Payload identification
The payload file is a wide daily table mixing several unrelated measurement
groups:
- **Soil matric potential** (`P1_MP_15`, `P1_MP_30`, `P1_MP_60`, `P2_MP_15`,
  `P2_MP_30`, `P2_MP_60`) — the only direct soil-moisture observations.
- Water isotopes (`d2H_*`, `d18O_*`), sap flow (`SapFlow*`, `T*mmh*`),
  meteorology (`Precip_mm`, `Tair`, `RelHum`, `BarPress_mbar`, wind, `SolRad`),
  and modeled/transformed isotope profiles (`*Trans*`).

Only the matric-potential columns map to the target schema
(`water_potential_kPa`). All other columns are excluded per SKILL Rule 2
(measurement type): isotopes, sap flow, and meteorology are not soil moisture,
and the `*Trans*` columns are derived/transformed values.

## Variable mapping
- `datetime_UTC`: parsed from `Timestamp` (`%Y-%m-%d`, date-only). Timezone not
  stated in package; interpreted as Mountain Standard Time (`Etc/GMT+7`, no DST)
  consistent with other East River / RMBL packages (e.g., indices 25, 26, 27),
  then converted to UTC. Because timestamps are date-only, the UTC times are
  07:00 UTC.
- `site_id`: profile prefix parsed from the MP column name (`P1`, `P2`).
- `depth_m`: trailing integer of MP column name (15/30/60 cm) ÷ 100 → 0.15,
  0.30, 0.60 m.
- `water_potential_kPa`: MP value; source units already kPa (negative values,
  range ≈ −3638 to −0.1 kPa). No unit conversion.
- `volumetric_water_content_m3_m3`, `gravimetric_water_content_gH2O_gs`: not
  reported → NA.
- `replicate`: 1 (single MP sensor per profile/depth).
- `is_timeseries`: True (regular daily records spanning 2022-01-01 to
  2024-08-13 per site/depth).

## Time series
Daily monitoring time series. `interval_min` is not part of the required output
schema/common helper and is therefore not emitted; if needed it would be ~1440
min (daily) but timestamps are date-only so an explicit interval was not added.

## Location resolution
Coordinates for `P1` and `P2` are present directly in `Locations.csv` as decimal
degrees (SECTION 5, source 2 / priority 1–2). No reprojection needed.
`qc_flag` is empty (coordinates resolved) for both profiles.
- P1: 38.96071917, −106.9910977
- P2: 38.96067806, −106.9910133

The other IDs in `Locations.csv` (A1–A3 aspen trees, S1–S3 spruce trees) are
sap-flow/isotope tree locations, not MP profiles, and are excluded from the
location output.

## Outputs
- `dataset_24.py` — generated transformation code.
- `ess-dive-daa156d2129c471-20250716T160748658_harmonized.csv` — 3204 rows
  (534 dated MP observations × 6 profile/depth series).
- `ess-dive-daa156d2129c471-20250716T160748658_location.csv` — P1, P2 with
  coordinates and qc_flag.
- `sm_data_harmonization_mapping.json` — mapping entry (index 24).

## Limitations / open questions
- **DOI not available** in the staged workspace; recorded as `null` in the
  mapping entry rather than retrieved externally.
- **Timezone assumption**: no timezone documented in the staged files; MST
  (Etc/GMT+7) assumed from site context. Date-only timestamps limit temporal
  precision.
- Of 956 daily rows, 534 carry MP values; the remaining rows have no MP data
  (only isotope/met columns) and drop out after filtering nulls.
