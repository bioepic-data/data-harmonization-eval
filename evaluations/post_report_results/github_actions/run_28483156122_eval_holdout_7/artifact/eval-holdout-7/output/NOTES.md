# Harmonization notes — held-out dataset 7

**Dataset:** `ess-dive-38e901ec3d7bd24-20230504T211548257225`

Harmonized from the package files alone using the `essdive_sm_harmonizer`
skill, the held-out-free exemplar mapping, and the expert reference code in
`data/gold/expert_code/harmonize_sm/`.

## Package contents

| File | Role | Key columns |
|------|------|-------------|
| `BM_Merged_T_VWC_0616_1018.csv` | **DATA PAYLOAD** | `date.time`, `record`, `Volumetric Water Content`, `Electrical Conductivity (dS/m)`, `T (degrees celcius)`, `Depth (cm)` |
| `BM_EGM_Well_CO2.csv` | **ANCILLARY (location source)** | `Location`, `Latitude`, `Longitude`, `Date`, `Time`, `Depth`, `CO2.Max`, `Notes` |

The payload is a long-format hourly time series at a single station ("BM"),
with one row per (timestamp, depth). 56,860 data rows. The CO2 file holds
soil-CO2 profile measurements (NOT soil moisture) but carries the site's
decimal-degree coordinates, so it is used only as the location source.

## Decisions (per skill SECTION 3 rules)

- **Inclusion:** INCLUDE. Rule 2 satisfied — the package contains direct
  volumetric water content observations (`Volumetric Water Content`).
- **Variable selection:** Only `Volumetric Water Content` is harmonized.
  `Electrical Conductivity`, soil temperature (`T`), and CO2 are out of the
  target schema and dropped. GWC and water potential are not reported (NA).
- **Units:** VWC values are ~0.12 (i.e. already m³ m⁻³), so **no /100
  conversion** is applied (contrast with datasets reporting VWC in %). Depth
  is an explicit `Depth (cm)` column → divide by 100 → m.
- **Depth encoding:** explicit numeric column; depth is *not* approximated
  from a range, so **no `d1` qc_flag**.
- **site_id:** single-station package; assigned constant `BM` (the name used
  in the CO2/location file). Timestamps are local Mountain time
  (America/Denver) and converted to UTC.
- **Time series (SECTION 4):** `is_timeseries = True` — regular hourly logger
  output with many observations per site+depth. `interval_min` is inferred
  per (site_id, depth_m) from successive timestamp differences (≈60 min).
- **Location (SECTION 5):** Source 2 — coordinates taken directly from a
  package ancillary file (the CO2 file: lat 38.98715, lon -107.003863,
  decimal degrees). No Varadharajan fallback needed → **no `g1`/`g2`
  qc_flag**.
- **replicate:** not provided in source → `1`.

## DOI

No cached metadata was available for this package (the
`data/external/ess-dive_meta/` directory is not present in this run
environment, and no offline lookup is permitted). The DOI is therefore set
to `null` in the mapping entry and flagged as an open question below.

## Outputs in this folder

- `harmonize_dataset_07.py` — transformation code (exposes `harmonize(ctx)`
  following the `dataset_NN.py` convention; also runnable standalone to write
  the CSVs). Imports shared helpers from
  `data/gold/expert_code/harmonize_sm/common.py`.
- `ess-dive-38e901ec3d7bd24-20230504T211548257225_harmonized.csv` — the
  harmonized payload in the 9-column target schema.
- `ess-dive-38e901ec3d7bd24-20230504T211548257225_locations.csv` — the site
  location row (BM + lat/lon + source_dataset_id + qc_flag).
- `sm_data_harmonization_mapping_entry.json` — the change-mapping entry
  (schema per skill SECTION 2).

## Open questions for operator review

1. **DOI** unresolved (no offline metadata available).
2. **Timezone** assumed America/Denver (Mountain), consistent with the East
   River / WFSFA SFA context used by exemplar datasets; the package does not
   state the timezone explicitly.
3. Confirm that the single station label `BM` is the intended `site_id`
   (the payload itself has no site column; the name is inferred from the
   companion CO2 file's `Location` field).
