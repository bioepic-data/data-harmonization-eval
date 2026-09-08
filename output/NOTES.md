# Harmonization notes — dataset index 5

**Target:** `ess-dive-8ac2940c708a515-20230504T210140482233`
**Payload:** `inputs/raw/ess-dive-8ac2940c708a515-20230504T210140482233/SM_SWC.csv`
**Mode:** fold-10-target-5 (leave-one-out); canonical index 5 retained per `MANIFEST.json`.

## Deliverables (under `output/`)
- `dataset_05.py` — standalone harmonization code (reads staged raw, writes CSV).
- `ess-dive-8ac2940c708a515-20230504T210140482233_harmonized.csv` — harmonized measurements (1,089,621 rows).
- `ess-dive-8ac2940c708a515-20230504T210140482233_location.csv` — per-site location accumulator (33 sites, all qc_flag `g2`).
- `sm_data_harmonization_mapping.json` — mapping entry (index 5).

## Payload identification
Single file `SM_SWC.csv` with columns `Date Time`, `SFA_Location`, `Sensor.SN`, `Measurement`. It is the sole measurement payload; no README, ancillary, sensor, or location files are present in the package.

## Inclusion decision
**INCLUDE.** Contains direct volumetric water content observations (Rule 2 satisfied). Not modeled/derived; machine-readable; no experimental-manipulation columns present (Rule 3 not triggered). Structurally the closest analog is expert dataset 23 (`WM_SWC.csv`), another SFA `*_SWC` time series.

## Variable mapping
- `Date Time` → `datetime_UTC`: parsed as `%Y-%m-%d %H:%M:%S`, localized to `Etc/GMT+7` (Watershed Function / East River SFA local standard time, UTC-7, no DST — same convention as expert dataset 23), converted to UTC. Verified: 13:00 local → 20:00 UTC. 0 unparseable timestamps.
- `Measurement` → `volumetric_water_content_m3_m3`: no unit conversion; source already m³/m³ (observed range 0.0003–0.5887; no `-9999`/null sentinels).
- `SFA_Location` → `site_id`: direct rename. 33 unique sites (`ER-*`, `WG-*`, `XX-*`).
- `replicate`: numbered by distinct `Sensor.SN` within (`datetime_UTC`, `site_id`, `depth_m`). Four sites carry two sensors → replicate values 1–2; all others 1.
- `gravimetric_water_content_gH2O_gs`, `water_potential_kPa`: not reported → NA.

## Time series
`is_timeseries = True`. Continuous multi-year sensor deployment (2017-05-26 to 2020-10-23), regular timestamps (median interval ~10 min per site). `interval_min` not part of the target output schema, so not emitted as a column.

## Location resolution
No coordinates in the payload and no ancillary/location file in the package. The SFA point-location registry (mapping index 0) is the expected fallback source, but its CSV
(`East_Taylor_Watershed_Community_Observatory_Sites...`) is **not staged** in this
run workspace. Per `AGENT_INSTRUCTIONS.md`, no external retrieval was attempted.
Coordinates therefore remain unresolvable: `latitude`/`longitude` = NA, `qc_flag = "g2"` for all 33 sites.

## Limitations / open questions for operator review
1. **Depth unresolved.** No depth information anywhere in this package; `depth_m` is NA for all rows. If a sensor-metadata table exists in the source archive (not staged here), it would supply per-`Sensor.SN` depths.
2. **Coordinates unresolved (`g2`).** Recoverable by joining `site_id` to the SFA point-location registry (index 0) when that CSV is available.
3. **DOI unknown.** Not present in the staged workspace; recorded as `null` in the mapping entry.
4. **Timezone assumption.** `Etc/GMT+7` inferred from the SFA/East River convention used for the analogous dataset 23; source package did not explicitly state a timezone.
