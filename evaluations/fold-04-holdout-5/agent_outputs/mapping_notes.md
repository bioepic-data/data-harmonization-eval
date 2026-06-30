# Held-out Dataset 5 Mapping Notes

Package: `ess-dive-8ac2940c708a515-20230504T210140482233`  
DOI: `doi:10.15485/1842907`

Decision: INCLUDE, control sensors only. The ESS-DIVE metadata describes an experimental early snowmelt manipulation, and `Microclimate_Sensors.csv` separates `ctl` and `tmt` sensors. Following the fold-local dataset 23 pattern, `SM_SWC.csv` is joined to sensor metadata and only `Treatment == 'ctl'` rows are retained.

Payload: `SM_SWC.csv` contains direct soil water content observations in `Measurement`, with `Date Time`, `SFA_Location`, and `Sensor.SN`. The other `SM_*` files contain air temperature, soil temperature, and relative humidity and are not harmonized.

Depth: no depth column is present in `SM_SWC.csv` or `Microclimate_Sensors.csv`; `depth_m` is populated with missing values.

Location: coordinates are resolved from the raw Varadharajan location registry where `SFA_Location` matches `Location_ID`. Exact matches are available for 14 of 19 retained control site IDs. Unmatched retained control IDs are: WG-LSB1, WG-USA2R, WG-USB2R, WG-USC1L, WG-USC1R.

Time series: timestamps are parsed as `America/Denver` local time and converted to UTC. `interval_min` is computed per `site_id` and replicate.

Counts before final timestamp/value cleanup: 1089621 raw SWC rows; 515825 control SWC rows; 19 retained control site IDs; 19 retained control sensors.
