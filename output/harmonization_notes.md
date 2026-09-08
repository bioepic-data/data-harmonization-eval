# Harmonization notes — fold-09-target-4

**Target dataset:** `ess-dive-6c7085e9c544cc6-20250424T164534831`
**Canonical index (from MANIFEST.json):** 4
**Package:** `Johnsen_Bi_2025_DAE_Manuscript_Data_Package`

## Package contents

Two row-aligned CSVs (1001 rows each):

- `df_data.csv` — measurement/model driver table with 20 columns:
  `txmax, txmin, tomax, tomin, u, vpd, pa, precip, srad, nsrad, nlrad, rn, g,
  lai, swc, swp, xT, xu, h, ET`. Structure is an eddy-covariance / land-surface
  manuscript data table.
- `df_meta.csv` — per-row metadata: `site, datetime, year, doy`.

The two files share the same row ordering; `df_meta` supplies the `site` and
observation `datetime` for the corresponding `df_data` row. Row counts match
exactly (1001), and each `site`+`datetime` pair is unique.

There is **no** README, location file, sensor file, or cached ESS-DIVE metadata
staged in this workspace (`data/external/ess-dive_meta/` is absent).

## Inclusion decision — INCLUDE

- **RULE 2 (measurement type):** The package contains direct soil moisture
  observations:
  - `swc` = soil (volumetric) water content, range 0.104–0.395 → already in
    m³ m⁻³.
  - `swp` = soil water potential, range −8386.02 … −3.45 (negative) → already in
    kPa.
- No duplicate/superseded signal available (RULE 1 not triggered from staged
  inputs).
- Payload is machine-readable CSV (RULE 4 satisfied).

## Variable mapping

| Target column | Source | Notes |
|---|---|---|
| `datetime_UTC` | `df_meta.datetime` | Date-only; localized `America/Denver` → UTC (East River / Snodgrass, CO). |
| `site_id` | `df_meta.site` | Values: `sg5, tb, ph1, ph2`. |
| `depth_m` | — | Not reported anywhere → `NaN`. |
| `replicate` | — | Not encoded → `NaN`. |
| `is_timeseries` | derived | `False` (see below). |
| `interval_min` | derived | `NaN` (discrete sampling). |
| `volumetric_water_content_m3_m3` | `df_data.swc` | No conversion (already m³ m⁻³). |
| `gravimetric_water_content_gH2O_gs` | — | Not present → `NaN`. |
| `water_potential_kPa` | `df_data.swp` | No conversion (already kPa, negative). |
| `qc_flag` | derived | `g2` for all rows (no coordinates). |

## Time-series determination

`is_timeseries = False`, `interval_min = NaN`. Each `site`+`datetime` pair has a
single observation; timestamps are date-only campaign/daily dates spread
irregularly across 2019–2023 rather than a continuous, regular logger stream.

## Location resolution

Following SECTION 5 fallback order:
1. Payload coordinates — none.
2. Package ancillary/location file — none in package.
3. Package-level ESS-DIVE metadata — not staged (`data/external` absent).
4. Approved location registry — the WFSFA location registry (mapping index 0,
   `East_Taylor_..._Point_Locations` CSV) is referenced by other datasets but is
   **not staged** in this workspace, and the site IDs here (`sg5, tb, ph1, ph2`)
   are non-standard lowercase codes that do not map cleanly to registry
   `Location_ID` values. Not used.
5. Unresolvable → `latitude/longitude = NaN`, `qc_flag = "g2"` for all sites.

**Limitation:** Site coordinates could not be resolved from any input available
in this workspace. Per AGENT_INSTRUCTIONS, this limitation is recorded here
rather than retrieved externally.

## Open questions for operator review

1. **Depth:** No measurement depth is reported for `swc`/`swp`. Left as `NaN`.
2. **Timezone:** Assumed `America/Denver` (East River / Snodgrass, Colorado
   sites). Date-only stamps make the exact UTC time-of-day nominal (set to
   local midnight → 06:00Z / 07:00Z depending on DST).
3. **Coordinates:** Unresolved (`g2`). If the location registry or package
   metadata is provided, sites `sg5/tb/ph1/ph2` should be geolocated and
   `qc_flag` updated.
4. **DOI:** Not available from staged inputs; recorded as `null`.
5. **swp/swc units:** Inferred from value ranges (no data dictionary in
   package). `swc`→m³ m⁻³ and `swp`→kPa are consistent with the observed ranges.

## Outputs

- `ess-dive-6c7085e9c544cc6-20250424T164534831_harmonized.csv` — 1001 rows.
- `ess-dive-6c7085e9c544cc6-20250424T164534831_location.csv` — 4 sites (g2).
- `dataset_04.py` — generated harmonization code.
- `sm_data_harmonization_mapping.json` — mapping entry (index 4).
- `harmonization_notes.md` — this file.
