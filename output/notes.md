# Harmonization notes — dataset index 18

- **Dataset:** `ess-dive-b924878d23c9dd7-20250214T163427929`
- **Title (from filename):** 2017 East River Pumphouse Soil Water Content and pH
- **Payload file:** `2017_East_River_Pumphouse_Soil_Water_Content_and_pH__1_.csv` (420 data rows)

## Inclusion decision

**INCLUDE.** The dataset contains direct observations of **gravimetric soil
water content** (column `Soil Water Content (g H2O per gram  soil)`), which
satisfies Rule 2 (measurement-type check) of the harmonizer skill. No duplicate
or supersession relationship is evident from the allowed inputs (Rule 1), the
payload is a machine-readable CSV table (Rule 4), and at least partial site
coordinates are present (Rule 5). There is no experimental manipulation (Rule 3);
snow-pit and vegetation labels are natural sampling contexts, not treatments.

## Measurement type

- Only **gravimetric water content (GWC)** is reported, in native units of
  g H2O per g soil (no conversion needed) -> `gravimetric_water_content_gH2O_gs`.
- `volumetric_water_content_m3_m3` and `water_potential_kPa` are populated with NA.
- Soil pH (`Soil pH `) is outside the target schema and is dropped.

## Time series determination

`is_timeseries = False`, `interval_min = NaN`. This is a discrete field
sampling campaign: `Date_Collected` holds nine campaign dates (date only, no
time-of-day). Dates are parsed as Mountain Standard Time (Etc/GMT+7, no DST,
consistent with reference datasets 25/26/27) and converted to UTC, giving
07:00 UTC.

## Depth

Depth is reported as increments (ranges), not point depths, so it is
**approximated by the range midpoint** and every row is flagged `qc_flag = "d1"`:

| Depth_Increment | Interpreted | depth_m |
|-----------------|-------------|---------|
| `0-5 cm`        | 0–5 cm midpoint (2.5 cm) | 0.025 |
| `5-15 cm`       | 5–15 cm midpoint (10 cm) | 0.100 |
| `15-May`        | Excel autocorrect artifact of `5-15 cm` (10 cm) | 0.100 |
| `15 cm +`       | open-ended; approximated by reported top of range (15 cm) | 0.150 |

- `15-May` appears in 60 rows (four of the nine campaigns) and is confirmed to
  be the same increment as `5-15 cm` (each campaign uses exactly one of the two
  labels for its middle depth).
- `15 cm +` is open-ended with no lower bound; its midpoint is undefined, so it
  is conservatively assigned the reported 15 cm boundary. This approximation is
  covered by the `d1` flag.

## site_id and location resolution

- `site_id` = `Location_FieldSite_Plot` (e.g. `East_River_Pumphouse_Hillslope_A1`).
  `Field_Site` alone was rejected as too coarse: within a single Field_Site the
  reported plots span up to ~2 km.
- Coordinates come from the payload's `Latitude`/`Longitude` columns
  (Location Resolution priority 1). These columns contain stray non-numeric
  bytes (e.g. `\xa0` and Unicode replacement characters in the July/September
  2017 floodplain and July hillslope C2 rows); they are stripped before numeric
  coercion.
- Per-site coordinates are taken as the **median** across that site's rows,
  which is robust to (a) per-campaign GPS re-measurement — some plot labels were
  recorded at different coordinates on different visits (notably
  `Washington_Gulch_Lower_Subalpine_A1`/`A2`) — and (b) a truncated entry
  `-107.000000` for `Washington_Gulch_Lower_Subalpine_C1`.
- **Unresolvable coordinates (`qc_flag = "g2"`):** all
  `Washington_Gulch_Upper_Montane_*` plots and the
  `Washington_Gulch_Lower_Subalpine_Willow`/`Veratrum` plots report no
  coordinates in the payload (57 rows). No package metadata or approved location
  registry for this package is present in the workspace, so these remain
  unresolved rather than being retrieved externally.

## Replicate

`replicate` is taken directly from the `Replicate` column (values 1, 2, 3),
coerced to integer.

## Row handling / QC

- 4 rows have no reported water content and are dropped -> **416 harmonized rows**.
- No `-9999`-style sentinel values are present in the water-content column.
- One GWC value of 4.00 (Snow Pit B1, 5/9/2017, 0–5 cm) is an extreme outlier
  but is a legitimately reported measurement and is retained.

## Missing inputs / limitations

- **DOI:** not present in the allowed workspace inputs; recorded as `null` in the
  mapping entry rather than retrieved from an external resolver.
- **Package metadata:** no `data/external/ess-dive_meta/` cache is present, so
  spatial-coverage or methods metadata could not corroborate the MST timezone
  assumption or resolve the missing Upper_Montane coordinates.

## Outputs

- `output/dataset_18.py` — standalone harmonization code.
- `output/ess-dive-b924878d23c9dd7-20250214T163427929_harmonized.csv` — 416 rows,
  target schema.
- `output/ess-dive-b924878d23c9dd7-20250214T163427929_location.csv` — 29 sites
  (8 with `g2`).
- `output/sm_data_harmonization_mapping.json` — mapping entry (index 18 retained
  from MANIFEST.json).

## Open questions for operator review

1. Interpretation of `15 cm +` depth (assigned 0.15 m) — confirm preferred
   convention for open-ended increments.
2. Whether the median-per-site coordinate collapse is acceptable given that some
   plot labels were re-surveyed at different locations across campaigns.
3. Timezone assumption (MST / Etc/GMT+7) for a date-only campaign.
