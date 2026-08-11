# Dataset 24 Mapping Notes

Decision: INCLUDE.

Package `ess-dive-daa156d2129c471-20250716T160748658` contains direct soil matric potential observations in `Iso_MP_Sap_DataDaily_ESSDiveUpload_R1.csv`. The six selected columns are `P1_MP_15`, `P1_MP_30`, `P1_MP_60`, `P2_MP_15`, `P2_MP_30`, and `P2_MP_60`. Columns are wide by profile (`P1`, `P2`) and depth in cm (`15`, `30`, `60`). The file is semicolon-delimited.

The package metadata retrieved from ESS-DIVE identifies DOI `doi:10.15485/2462766` and describes daily soil matric potential at 15, 30, and 60 cm for two soil profiles near Gothic, Colorado. The API record points to an earlier previous version, so this held-out package is treated as the current version rather than excluded as superseded.

`Locations.csv` provides coordinates for profile IDs `P1` and `P2`, so no location QC flag is needed. The harmonized CSV follows the fold-local `ensure_harmonized_cols` schema exactly. `MP` values are kept as kPa with no unit conversion, matching fold-local water-potential exemplars and the observed value range.

Timezone assumption: source daily dates are localized to `America/Denver` at midnight before conversion to UTC. The series is daily, so `interval_min` is computed per `site_id` and `depth_m` after UTC conversion. The first row for each site-depth series has missing interval; most daily rows are 1440 minutes, with 1380/1500 minute intervals at daylight-saving transitions because local midnight is converted to UTC.

Open question: the local raw package does not include the source data dictionary mentioned by ESS-DIVE metadata, so the kPa unit assignment is inferred from the column naming, values, and fold-local examples.
