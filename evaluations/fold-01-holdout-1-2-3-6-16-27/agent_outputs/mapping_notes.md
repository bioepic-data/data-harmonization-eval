# Held-out Soil Moisture Mapping Notes

All six held-out packages were included because each has machine-readable timestamped direct soil-moisture observations: VWC, water potential, or both. All generated target rows use the required schema only: `datetime_UTC`, `site_id`, `depth_m`, `replicate`, `is_timeseries`, `interval_min`, `volumetric_water_content_m3_m3`, `gravimetric_water_content_gH2O_gs`, `water_potential_kPa`.

DOIs were not present in the allowed raw files for datasets 2, 3, 6, 16, and 27, so `mapping.json` records `unknown_from_allowed_inputs` for those entries. Dataset 1 uses the DOI shown in the fold-local curator skill example. No external gold/processed held-out mapping was consulted.

Dataset 1 maps ER_SMN/ER_SMS logger CSVs from `Time` and wide `m3_m3_Water_Content`, `m3_m3_VWC`, and `kPa_Potential` columns. Depth is parsed from `_at_<cm>cm`; replicate is parsed from the optional numeric column suffix, with unsuffixed columns treated as replicate 1.

Dataset 2 maps four ER_SMN CSVs from `DateTime` and `Moisture_m3/m3_10cm` / `Moisture_m3/m3_50cm`; site IDs are normalized from file names.

Dataset 3 maps `Soil_water_potential.csv`; data-dictionary rows indicate the MP variables are average soil water potential in KPa. Site IDs and depths are parsed from column names such as `SD11-25cm_MP` and `SD1-60cm_MP_4_Avg`. The SD1/SD11 sensor sites do not link cleanly to `locations.csv`, but coordinates are outside the final target schema.

Dataset 6 maps `Snodgrass_ESS.csv` after skipping descriptor and unit rows. Its XML states the sensors report soil moisture at 50 cm, 15 cm, and 5 cm, with 30-minute averages; the payload timestamp row labels time as UTC.

Dataset 16 maps EHG sensor tower files. SWC columns are converted from percent to m3/m3 by dividing by 100. Depths come from `metadata_instrument_v1-1.csv` HEIGHT values for each site/variable; negative belowground heights are converted to positive depths.

Dataset 27 maps ER-PHS field CSVs. VWC is taken from `S1_wc_(m3/m3)` through `S4_wc_(m3/m3)` and water potential from `S5_wp_(kPa)`. Since the package has no explicit depth metadata, S1-S4 depths are inferred from the related held-out ER-PHS sensor-tower metadata used for dataset 16; S5 water potential is assigned 0.30 m. This is the main uncertainty.
