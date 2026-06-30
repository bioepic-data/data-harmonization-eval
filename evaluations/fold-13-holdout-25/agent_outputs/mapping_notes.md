# Mapping Notes: Dataset 25

Package: `ess-dive-e67ab1151ebc525-20230929T190307767`  
DOI: `doi:10.6084/M9.FIGSHARE.7834406.V2`

Decision: INCLUDE. The package contains direct hourly volumetric water content observations in `VWC-50cm`, `VWC-15cm`, and `VWC-5cm` for two adjacent forest stands.

Key assumptions and handling:
- `Carbone_aspen.csv` is headerless in the raw package copy. Its column order matches `Carbone_conifer.csv`; the same 24-column schema is applied.
- Site identifiers are the source filename stems: `Carbone_aspen` and `Carbone_conifer`.
- Depth is parsed from the VWC column suffixes and converted from cm to m: 0.50, 0.15, and 0.05 m.
- Source timestamps have no timezone field. The script assumes fixed Mountain Standard Time (`Etc/GMT+7`) for the logger timestamps and emits UTC ISO strings.
- `Carbone_conifer.csv` includes non-leap-year February 29 rows for 2014, 2018, and 2021. These rows are dropped because they cannot be represented as valid datetimes.
- VWC values are already in m3/m3. Missing values and physically implausible values outside 0-1 are dropped.
- Coordinates are resolved from package-level ESS-DIVE metadata: 38.9592, -106.9898 for the two soil pits within 15 m of each other.
