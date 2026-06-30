# %%
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer

# %%
# =============================================================
# Config / Paths
# =============================================================

HOME = Path.home()
BASE_DIR = Path(HOME, "ess-dive_wfsfa_soil_datasets")
OUT_DIR = Path("data", "processed", "ess-dive_wfsfa_soil_datasets")
MAP_JSON_PATH = OUT_DIR / "sm_data_harmonization_mapping.json"

OUT_DIR.mkdir(parents=True, exist_ok=True)

with MAP_JSON_PATH.open("r", encoding="utf-8") as f:
    map_json: list[dict] = json.load(f)

# map_json[0] is the reference dataset (lookup)
REF_IDX = 0

# %%
# =============================================================
# Helpers
# =============================================================

def as_list(x):
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def dsid(idx: int) -> str:
    return map_json[idx]["dataset_identifier"]


def ds_path(idx: int) -> Path:
    return BASE_DIR / dsid(idx)


def read_ds_csv(idx: int, filename: str, encoding='utf-8', errors='ignore', **kwargs) -> pd.DataFrame:
    return pd.read_csv(ds_path(idx) / filename, encoding=encoding, **kwargs)


def parse_local_to_utc(series: pd.Series, fmt: str | None, tz: str) -> pd.Series:
    dt = pd.to_datetime(series, format=fmt, errors="coerce")
    dt = dt.dt.tz_localize(tz, ambiguous="NaT", nonexistent="shift_forward")
    return dt.dt.tz_convert("UTC")


def interval_min(s: pd.Series) -> pd.Series:
    return s.diff().dt.total_seconds() / 60.0


def utm32613_to_latlon(df: pd.DataFrame, e_col: str, n_col: str) -> pd.DataFrame:
    tr = Transformer.from_crs("EPSG:32613", "EPSG:4326", always_xy=True)
    e = pd.to_numeric(df[e_col], errors="coerce").values
    n = pd.to_numeric(df[n_col], errors="coerce").values
    lon, lat = tr.transform(e, n)
    out = df.copy()
    out["longitude"] = lon
    out["latitude"] = lat
    return out


def ensure_harmonized_cols(df: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "datetime_UTC",
        "site_id",
        "depth_m",
        "replicate",
        "is_timeseries",
        "interval_min",
        "volumetric_water_content_m3_m3",
        "gravimetric_water_content_gH2O_gs",
        "water_potential_kPa",
    ]
    for c in cols:
        if c not in df.columns:
            df[c] = np.nan
    return df[cols]


def add_loc_qc(df: pd.DataFrame) -> pd.DataFrame:
    if "qc_flag" not in df.columns:
        df["qc_flag"] = np.where(df["latitude"].isna() | df["longitude"].isna(), "g2", np.nan)
    return df


harmonized_data: list[pd.DataFrame] = []
harmonized_ids: list[str] = []
loc_data: list[pd.DataFrame] = []

# %%
# =============================================================
# Dataset 1
# =============================================================
idx = 1
f1 = as_list(map_json[idx]["data_payload_files"])
m1 = as_list(map_json[idx]["location_metadata_files"])[0]

ls1 = [read_ds_csv(idx, x) for x in f1]
mdf1 = read_ds_csv(idx, m1)

ls1_h = []
for i, d in enumerate(ls1):
    cols = [c for c in d.columns if re.search(r"Water_Content|VWC|Potential", c)]
    x = d[["Time"] + cols].copy()

    x["datetime_UTC"] = parse_local_to_utc(x["Time"], "%Y-%m-%d %H:%M:%S", "America/Denver")
    x["interval_min"] = interval_min(x["datetime_UTC"])
    x = x.drop(columns=["Time"])

    long = x.melt(id_vars=["datetime_UTC", "interval_min"], var_name="name", value_name="value")
    m = long["name"].str.extract(r"^(.*)_at_(.*)$")
    long["var_name"] = m[0]
    long["depth"] = m[1]
    long = long.dropna(subset=["depth"])

    long["value"] = pd.to_numeric(long["value"], errors="coerce")
    long.loc[long["value"] == -9999, "value"] = np.nan
    long = long.dropna(subset=["value"])

    long["dest_var"] = np.where(
        long["var_name"].str.contains(r"Water_Content|VWC", regex=True, na=False),
        "volumetric_water_content_m3_m3",
        np.where(
            long["var_name"].str.contains(r"Potential", regex=True, na=False),
            "water_potential_kPa",
            np.nan,
        ),
    )
    long = long.dropna(subset=["dest_var"])

    long["replicate"] = long.groupby(["datetime_UTC", "depth", "dest_var"]).cumcount() + 1

    wide = (
        long.pivot_table(
            index=["datetime_UTC", "interval_min", "depth", "replicate"],
            columns="dest_var",
            values="value",
            aggfunc="first",
        )
        .reset_index()
    )

    wide["depth_m"] = pd.to_numeric(wide["depth"].str.replace("cm", "", regex=False), errors="coerce") / 100
    wide["site_id"] = re.sub(r"\.csv$", "", f1[i])
    wide["is_timeseries"] = True
    wide["gravimetric_water_content_gH2O_gs"] = np.nan

    ls1_h.append(ensure_harmonized_cols(wide))

df1_harmonized = pd.concat(ls1_h, ignore_index=True)
harmonized_data.append(df1_harmonized)
harmonized_ids.append(dsid(idx))

loc1_tmp = utm32613_to_latlon(mdf1, "Easting", "Northing")
loc1 = pd.DataFrame(
    {
        "site_id": loc1_tmp["Name"],
        "latitude": loc1_tmp["latitude"],
        "longitude": loc1_tmp["longitude"],
    }
)
loc1["source_dataset_id"] = dsid(idx)
loc1 = add_loc_qc(loc1)
loc_data.append(loc1)

# %%
# =============================================================
# Dataset 2
# =============================================================
idx = 2
f2 = as_list(map_json[idx]["data_payload_files"])
m2 = as_list(map_json[idx]["location_metadata_files"])[0]

ls2 = [read_ds_csv(idx, x) for x in f2]
mdf2 = read_ds_csv(idx, m2)

ls2_h = []
for i, d in enumerate(ls2):
    cols = [c for c in d.columns if re.search(r"Moisture", c)]
    x = d[["DateTime"] + cols].copy()
    x["datetime_UTC"] = parse_local_to_utc(x["DateTime"], "%m/%d/%Y %I:%M:%S %p", "America/Denver")
    x["interval_min"] = interval_min(x["datetime_UTC"])
    x = x.drop(columns=["DateTime"])

    long = x.melt(
        id_vars=["datetime_UTC", "interval_min"],
        var_name="name",
        value_name="volumetric_water_content_m3_m3",
    )
    long["depth_m"] = (
        pd.to_numeric(long["name"].str.split("_").str[-1].str.replace("cm", "", regex=False), errors="coerce") / 100
    )
    long["site_id"] = re.sub(r"\.csv$", "", f2[i])
    long["is_timeseries"] = True
    long["water_potential_kPa"] = np.nan
    long["gravimetric_water_content_gH2O_gs"] = np.nan
    long["replicate"] = long.groupby(["datetime_UTC", "depth_m", "name"]).cumcount() + 1

    ls2_h.append(ensure_harmonized_cols(long))

df2_harmonized = pd.concat(ls2_h, ignore_index=True)
harmonized_data.append(df2_harmonized)
harmonized_ids.append(dsid(idx))

loc2 = mdf2.rename(columns={"Name": "site_id", "Lat ": "latitude", "Lon": "longitude"})[
    ["site_id", "latitude", "longitude"]
].copy()
loc2["source_dataset_id"] = dsid(idx)
loc2 = add_loc_qc(loc2)
loc_data.append(loc2)

# %%
# =============================================================
# Dataset 3
# =============================================================
idx = 3
f3 = as_list(map_json[idx]["data_payload_files"])[0]
m3 = as_list(map_json[idx]["location_metadata_files"])[0]

df3 = read_ds_csv(idx, f3)
mdf3 = read_ds_csv(idx, m3)

x = df3.copy()
x["datetime_UTC"] = parse_local_to_utc(x["TIMESTAMP"], "%Y-%m-%d %H:%M", "America/Denver")
x["interval_min"] = interval_min(x["datetime_UTC"])

mp_cols = [c for c in x.columns if "_MP" in c]
for c in mp_cols:
    x[c] = pd.to_numeric(x[c], errors="coerce")

long = x.melt(id_vars=["datetime_UTC", "interval_min"], value_vars=mp_cols, var_name="name", value_name="water_potential_kPa")
long["depth_m"] = pd.to_numeric(
    long["name"].str.replace(r"[._]", " ", regex=True).str.split().str[1].str.replace("cm", "", regex=False),
    errors="coerce",
) / 100
long["site_id"] = "ER-LLN1"
long["is_timeseries"] = True
long["water_potential_kPa"] = long["water_potential_kPa"].where(~np.isnan(long["water_potential_kPa"]), np.nan)
long["volumetric_water_content_m3_m3"] = np.nan
long["gravimetric_water_content_gH2O_gs"] = np.nan
long["replicate"] = long.groupby(["datetime_UTC", "depth_m"]).cumcount() + 1

df3_harmonized = ensure_harmonized_cols(long)
harmonized_data.append(df3_harmonized)
harmonized_ids.append(dsid(idx))

loc3 = mdf3.rename(columns={"Location_ID": "site_id", "Latitude": "latitude", "Longitude": "longitude"})[
    ["site_id", "latitude", "longitude"]
].copy()
loc3["source_dataset_id"] = dsid(idx)
loc3 = add_loc_qc(loc3)
loc_data.append(loc3)

# %%
# =============================================================
# Dataset 4
# =============================================================
idx = 4
f4 = as_list(map_json[idx]["data_payload_files"])[0]
m4 = as_list(map_json[idx]["location_metadata_files"])[0]
ddf4 = read_ds_csv(idx, f4)
mdf4 = read_ds_csv(idx, m4)

x = pd.concat([ddf4.reset_index(drop=True), mdf4.reset_index(drop=True)], axis=1)
dt = pd.to_datetime(x["datetime"], errors="coerce").dt.tz_localize("America/Denver", ambiguous="NaT", nonexistent="shift_forward")
x["datetime_UTC"] = dt.dt.tz_convert("UTC")
x["site_id"] = x["site"]
x["depth_m"] = np.nan
x["replicate"] = 1
x["is_timeseries"] = True
x["interval_min"] = 24 * 60
x["volumetric_water_content_m3_m3"] = pd.to_numeric(x["swc"], errors="coerce")
x["water_potential_kPa"] = pd.to_numeric(x["swp"], errors="coerce")
x["gravimetric_water_content_gH2O_gs"] = np.nan
x = x.sort_values(["datetime_UTC", "site_id"])
x = x[x["site_id"] != "tb"]

df4_harmonized = ensure_harmonized_cols(x)
harmonized_data.append(df4_harmonized)
harmonized_ids.append(dsid(idx))

loc4 = pd.DataFrame(
    {
        "site_id": ["ph1", "ph2", "sg5"],
        "latitude": [38.92, 38.922583, 38.926250],
        "longitude": [-106.95, -106.947288, -106.98],
    }
)
loc4["source_dataset_id"] = dsid(idx)
loc4 = add_loc_qc(loc4)
loc_data.append(loc4)

# %%
# =============================================================
# Dataset 5
# =============================================================
idx = 5
f5 = as_list(map_json[idx]["data_payload_files"])[0]
m5 = as_list(map_json[REF_IDX]["location_metadata_files"])[0]

ddf5 = read_ds_csv(idx, f5)
mdf5 = read_ds_csv(REF_IDX, m5)

x = ddf5.copy()
dt_local = pd.to_datetime(x["Date Time"], errors="coerce").dt.tz_localize("America/Denver", ambiguous="NaT", nonexistent="shift_forward")
x["datetime_UTC"] = dt_local.dt.tz_convert("UTC")
x["site_id"] = x["SFA_Location"]
x["depth_m"] = np.nan
x["replicate"] = 1
x["is_timeseries"] = True
x["interval_min"] = 60
x["volumetric_water_content_m3_m3"] = pd.to_numeric(x["Measurement"], errors="coerce")
x["water_potential_kPa"] = np.nan
x["gravimetric_water_content_gH2O_gs"] = np.nan

df5_harmonized = ensure_harmonized_cols(x)
harmonized_data.append(df5_harmonized)
harmonized_ids.append(dsid(idx))

loc5 = pd.DataFrame({"site_id": df5_harmonized["site_id"].dropna().unique()})

loc5a = loc5.merge(
    mdf5[["Location_ID", "Latitude", "Longitude"]],
    left_on="site_id",
    right_on="Location_ID",
    how="left",
).drop(columns=["Location_ID"])

loc5b = loc5.merge(
    mdf5[["Parent_Location_ID", "Latitude", "Longitude"]],
    left_on="site_id",
    right_on="Parent_Location_ID",
    how="left",
).drop(columns=["Parent_Location_ID"])

loc5m = loc5a.merge(loc5b, on="site_id", how="left", suffixes=(".x", ".y"))
loc5m["latitude"] = loc5m["Latitude.x"].combine_first(loc5m["Latitude.y"])
loc5m["longitude"] = loc5m["Longitude.x"].combine_first(loc5m["Longitude.y"])
loc5m["source_dataset_id"] = dsid(idx)

loc5 = loc5m[["site_id", "latitude", "longitude", "source_dataset_id"]].drop_duplicates(subset=["site_id"])
loc5["qc_flag"] = np.where(loc5["latitude"].isna() | loc5["longitude"].isna(), "g2", "g1")
loc_data.append(loc5)

# %%
# =============================================================
# Dataset 6
# =============================================================
idx = 6
f6 = as_list(map_json[idx]["data_payload_files"])[0]
ddf6 = read_ds_csv(idx, f6)

x = ddf6.iloc[2:].copy()
x["datetime_UTC"] = pd.to_datetime(x["TIMESTAMP"], format="%m/%d/%y %H:%M", errors="coerce", utc=True)
x["site_id"] = x["site"]
x["interval_min"] = interval_min(x["datetime_UTC"])

vwc_cols = [c for c in x.columns if "VWC" in c]
long = x.melt(
    id_vars=["datetime_UTC", "site_id", "interval_min"],
    value_vars=vwc_cols,
    var_name="name",
    value_name="volumetric_water_content_m3_m3",
)
long["depth_m"] = (
    pd.to_numeric(long["name"].str.split("_").str[-1].str.replace("cm", "", regex=False), errors="coerce") / 100
)
long["replicate"] = 1
long["is_timeseries"] = True
long["water_potential_kPa"] = np.nan
long["gravimetric_water_content_gH2O_gs"] = np.nan

df6_harmonized = ensure_harmonized_cols(long)
harmonized_data.append(df6_harmonized)
harmonized_ids.append(dsid(idx))

loc6 = (
    ddf6.iloc[2:]
    .groupby("site", as_index=False)
    .first()[["site", "latitude", "longitude"]]
    .rename(columns={"site": "site_id"})
)
loc6["source_dataset_id"] = dsid(idx)
loc6 = add_loc_qc(loc6)
loc_data.append(loc6)

# %%
# =============================================================
# Dataset 7
# =============================================================
idx = 7
f7 = as_list(map_json[idx]["data_payload_files"])[0]
m7 = as_list(map_json[idx]["location_metadata_files"])[0]

ddf7 = read_ds_csv(idx, f7)
mdf7 = read_ds_csv(idx, m7, encoding='latin-1')

x = ddf7.copy()
x["datetime_UTC"] = parse_local_to_utc(x["date.time"], "%m/%d/%y %H:%M", "America/Denver")
x["site_id"] = "BM"
x["interval_min"] = interval_min(x["datetime_UTC"])
x["depth_m"] = pd.to_numeric(x["Depth (cm)"], errors="coerce") / 100
x["replicate"] = 1
x["is_timeseries"] = True
x["volumetric_water_content_m3_m3"] = pd.to_numeric(x["Volumetric Water Content"], errors="coerce")
x["water_potential_kPa"] = np.nan
x["gravimetric_water_content_gH2O_gs"] = np.nan

df7_harmonized = ensure_harmonized_cols(x)
harmonized_data.append(df7_harmonized)
harmonized_ids.append(dsid(idx))

lat_col = [c for c in mdf7.columns if "Latitude" in c][0]
lon_col = [c for c in mdf7.columns if "Longitude" in c][0]
loc7 = mdf7.iloc[[0]].rename(columns={"Location": "site_id", lat_col: "latitude", lon_col: "longitude"})[
    ["site_id", "latitude", "longitude"]
].copy()
loc7["source_dataset_id"] = dsid(idx)
loc7 = add_loc_qc(loc7)
loc_data.append(loc7)

# %%
# =============================================================
# Dataset 8
# =============================================================
idx = 8
f8 = as_list(map_json[idx]["data_payload_files"])
m8 = as_list(map_json[idx]["location_metadata_files"])

ls8 = [read_ds_csv(idx, x) for x in f8]
mdf8 = pd.concat([read_ds_csv(idx, x) for x in m8], ignore_index=True)

ls8_h = []
for d in ls8:
    cols = [c for c in d.columns if re.search(r"SoilMoisture|SoilMatricPot", c)]
    x = d[["DateTime.MST"] + cols].copy()
    x["datetime_UTC"] = parse_local_to_utc(x["DateTime.MST"], "%Y-%m-%d %H:%M:%S", "America/Denver")
    x["interval_min"] = interval_min(x["datetime_UTC"])
    x = x.drop(columns=["DateTime.MST"])
    x.columns = [re.sub(r"\.m3\.m3|\.kPa", "", c) for c in x.columns]

    value_cols = [c for c in x.columns if re.search(r"SoilMoisture|SoilMatricPot", c)]
    long = x.melt(id_vars=["datetime_UTC", "interval_min"], value_vars=value_cols, var_name="name", value_name="value")
    m = long["name"].str.extract(r"^(SoilMoisture|SoilMatricPot)_(.*)$")
    long["var"] = m[0]
    long["depth_m"] = pd.to_numeric(m[1].str.replace("cm", "", regex=False), errors="coerce") / 100
    long["value"] = pd.to_numeric(long["value"], errors="coerce")
    long.loc[long["value"] == -9999, "value"] = np.nan

    wide = (
        long.pivot_table(
            index=["datetime_UTC", "interval_min", "depth_m"],
            columns="var",
            values="value",
            aggfunc="first",
        )
        .reset_index()
        .rename(columns={"SoilMoisture": "volumetric_water_content_m3_m3", "SoilMatricPot": "water_potential_kPa"})
    )

    wide["replicate"] = 1
    wide["site_id"] = "Slate River OBJ-2"
    wide["is_timeseries"] = True
    wide["gravimetric_water_content_gH2O_gs"] = np.nan

    ls8_h.append(ensure_harmonized_cols(wide))

df8_harmonized = pd.concat(ls8_h, ignore_index=True)
harmonized_data.append(df8_harmonized)
harmonized_ids.append(dsid(idx))

loc8 = mdf8.iloc[[0]].rename(columns={"SiteName": "site_id", "Latitude": "latitude", "Longitude": "longitude"})[
    ["site_id", "latitude", "longitude"]
].copy()
loc8["source_dataset_id"] = dsid(idx)
loc8 = add_loc_qc(loc8)
loc_data.append(loc8)

# %%
# =============================================================
# Dataset 9
# =============================================================
idx = 9
f9 = as_list(map_json[idx]["data_payload_files"])[0]
m9 = as_list(map_json[idx]["location_metadata_files"])[0]

ddf9 = read_ds_csv(idx, f9)
mdf9 = read_ds_csv(idx, m9)

x = ddf9.copy()
x["datetime_UTC"] = parse_local_to_utc(x["Collection Date"], "%Y-%m-%d", "America/Denver")
x["site_id"] = x["SampleSiteCode"]
x["interval_min"] = np.nan
x["depth_m"] = 0.2
x["is_timeseries"] = False
x["water_potential_kPa"] = np.nan

long = x.melt(
    id_vars=["datetime_UTC", "site_id", "interval_min", "depth_m", "is_timeseries", "water_potential_kPa"],
    value_vars=["VWC_1", "VWC_2"],
    var_name="tmp",
    value_name="VWC",
)
long["replicate"] = long["tmp"].str.extract(r"_(\d+)")[0]
long["VWC"] = pd.to_numeric(long["VWC"], errors="coerce")
long.loc[long["VWC"] == -9999.0, "VWC"] = np.nan
long = long[long["VWC"].notna()].copy()
long["volumetric_water_content_m3_m3"] = long["VWC"]
long["gravimetric_water_content_gH2O_gs"] = np.nan

df9_harmonized = ensure_harmonized_cols(long)
harmonized_data.append(df9_harmonized)
harmonized_ids.append(dsid(idx))

loc9_tmp = utm32613_to_latlon(mdf9, "Easting", "Northing")
loc9 = pd.DataFrame(
    {
        "site_id": loc9_tmp["SampleSiteCode"],
        "latitude": loc9_tmp["latitude"],
        "longitude": loc9_tmp["longitude"],
    }
)
loc9["source_dataset_id"] = dsid(idx)
loc9 = add_loc_qc(loc9)
loc_data.append(loc9)

# %%
# =============================================================
# Dataset 10
# =============================================================
idx = 10
f10 = as_list(map_json[idx]["data_payload_files"])[0]
m10 = as_list(map_json[REF_IDX]["location_metadata_files"])[0]

ddf10 = read_ds_csv(idx, f10)
mdf10 = read_ds_csv(REF_IDX, m10)

x = ddf10.iloc[1:].copy()
x["datetime_UTC"] = parse_local_to_utc(x["Date"], "%Y-%m-%d", "America/Denver")
x["interval_min"] = interval_min(x["datetime_UTC"])

vcols = [c for c in x.columns if re.search(r"vol_water_content", c)]
long = x.melt(id_vars=["datetime_UTC", "interval_min"], value_vars=vcols, var_name="name", value_name="volumetric_water_content_m3_m3")
nm = long["name"].str.extract(r"(.*)\._(.*)")
long["site_id"] = nm[0]
long["depth_m"] = np.select(
    [long["site_id"].eq("PLM1"), long["site_id"].eq("PLM2"), long["site_id"].eq("PLM3")],
    [0.3, 0.28, 0.2],
    default=np.nan,
)
long["is_timeseries"] = True
long["water_potential_kPa"] = np.nan
long["replicate"] = 1
long["gravimetric_water_content_gH2O_gs"] = np.nan

df10_harmonized = ensure_harmonized_cols(long)
harmonized_data.append(df10_harmonized)
harmonized_ids.append(dsid(idx))

sites = df10_harmonized["site_id"].dropna().astype(str).unique().tolist()
pattern = r"(?:^|)(%s)$" % "|".join([re.escape(s) for s in sites]) if sites else r"$^"
loc10 = mdf10[mdf10["Location_ID"].astype(str).str.contains(pattern, regex=True, na=False)].copy()
loc10["site_id"] = loc10["Location_ID"].str.replace("ER-", "", regex=False)
loc10 = loc10.rename(columns={"Latitude": "latitude", "Longitude": "longitude"})[["site_id", "latitude", "longitude"]]
loc10["source_dataset_id"] = dsid(idx)
loc10 = add_loc_qc(loc10)
loc_data.append(loc10)

# %%
# =============================================================
# Dataset 11-14 excluded
# =============================================================

# %%
# =============================================================
# Dataset 15
# =============================================================
idx = 15
f15 = as_list(map_json[idx]["data_payload_files"])[0]
m15 = as_list(map_json[idx]["location_metadata_files"])[0]

ddf15 = read_ds_csv(idx, f15)
mdf15 = read_ds_csv(idx, m15)

x = ddf15.iloc[1:].copy()
x["datetime_UTC"] = pd.Timestamp("2019-07-02 06:00:00", tz="UTC")
x["is_timeseries"] = False
x["interval_min"] = np.nan

vcols = [c for c in x.columns if re.search(r"SM\.VWC", c)]
long = x.melt(
    id_vars=["datetime_UTC", "GPS_id", "is_timeseries", "interval_min"],
    value_vars=vcols,
    var_name="name",
    value_name="volumetric_water_content_m3_m3",
)
long["replicate"] = long["name"].str.extract(r"\._(.*)$")[0]
long["volumetric_water_content_m3_m3"] = pd.to_numeric(long["volumetric_water_content_m3_m3"], errors="coerce") / 100
long["depth_m"] = 0.25
long["water_potential_kPa"] = np.nan
long["gravimetric_water_content_gH2O_gs"] = np.nan
long["site_id"] = long["GPS_id"]

df15_harmonized = ensure_harmonized_cols(long)
harmonized_data.append(df15_harmonized)
harmonized_ids.append(dsid(idx))

loc15_tmp = utm32613_to_latlon(mdf15, "Easting_m", "Northing_m")
loc15 = pd.DataFrame(
    {
        "site_id": loc15_tmp["GPS_id"],
        "latitude": loc15_tmp["latitude"],
        "longitude": loc15_tmp["longitude"],
    }
)
loc15["source_dataset_id"] = dsid(idx)
loc15 = add_loc_qc(loc15)
loc_data.append(loc15)

# %%
# =============================================================
# Dataset 16
# =============================================================
idx = 16
f16 = as_list(map_json[idx]["data_payload_files"])
m16 = as_list(map_json[idx]["location_metadata_files"])[0]
s16 = as_list(map_json[idx]["sensor_metadata_files"])[0]

ls16 = [read_ds_csv(idx, x) for x in f16]
mdf16 = read_ds_csv(idx, m16)
sdf16 = read_ds_csv(idx, s16)

ls16_h = []
for i, d in enumerate(ls16):
    siten = f16[i]
    x = d.copy()
    x["datetime_UTC"] = parse_local_to_utc(x["TIMESTAMP_END"], "%Y-%m-%d %H:%M:%S", "Etc/GMT+7")
    x["interval_min"] = interval_min(x["datetime_UTC"])
    parts = siten.split("_")
    x["SITE_ID"] = parts[6] if len(parts) >= 7 else np.nan

    sw_cols = [c for c in x.columns if re.search(r"SWC|SWP", c)]
    long = x.melt(id_vars=["datetime_UTC", "interval_min", "SITE_ID"], value_vars=sw_cols, var_name="VARIABLE", value_name="value")

    meta = sdf16.loc[sdf16["VARIABLE"].astype(str).str.contains("SWC|SWP", regex=True, na=False), ["SITE_ID", "VARIABLE", "HEIGHT"]]
    long = long.merge(meta, on=["SITE_ID", "VARIABLE"], how="left")
    long["VARIABLE"] = long["VARIABLE"].astype(str).str.split("_").str[0]
    long["depth_m"] = pd.to_numeric(long["HEIGHT"], errors="coerce") * -1
    long["replicate"] = 1
    long["is_timeseries"] = True
    long["gravimetric_water_content_gH2O_gs"] = np.nan
    long = long.drop_duplicates()

    wide = (
        long.pivot_table(
            index=["datetime_UTC", "SITE_ID", "depth_m", "replicate", "is_timeseries", "interval_min", "gravimetric_water_content_gH2O_gs"],
            columns="VARIABLE",
            values="value",
            aggfunc="first",
        )
        .reset_index()
    )

    wide["SWC"] = pd.to_numeric(wide.get("SWC"), errors="coerce")
    wide["SWP"] = pd.to_numeric(wide.get("SWP"), errors="coerce")
    wide["volumetric_water_content_m3_m3"] = np.where(wide["SWC"].isin([9999.0, -9999.0]), np.nan, wide["SWC"])
    wide["water_potential_kPa"] = np.where(wide["SWP"].isin([9999.0, -9999.0]), np.nan, wide["SWP"])
    wide = wide.rename(columns={"SITE_ID": "site_id"})

    ls16_h.append(ensure_harmonized_cols(wide))

df16_harmonized = pd.concat(ls16_h, ignore_index=True)
harmonized_data.append(df16_harmonized)
harmonized_ids.append(dsid(idx))

loc16 = mdf16.rename(columns={"SITE_ID": "site_id", "LOCATION_LAT": "latitude", "LOCATION_LONG": "longitude"})[
    ["site_id", "latitude", "longitude"]
].copy()
loc16["source_dataset_id"] = dsid(idx)
loc16 = add_loc_qc(loc16)
loc_data.append(loc16)

# %%
# =============================================================
# Dataset 17
# =============================================================
idx = 17
f17 = as_list(map_json[idx]["data_payload_files"])
m17 = as_list(map_json[idx]["location_metadata_files"])[0]

ls17 = [read_ds_csv(idx, x) for x in f17]
mdf17 = read_ds_csv(idx, m17)

ls17_h = []
for i, d in enumerate(ls17):
    siten = f17[i]
    x = d.iloc[1:].copy()
    x["datetime_UTC"] = parse_local_to_utc(x["DateTime"], "%Y-%m-%d %H:%M:%S", "America/Denver")
    x["interval_min"] = interval_min(x["datetime_UTC"])

    site_guess = re.split(r"/|\.", siten)
    x["site_id"] = site_guess[2] if len(site_guess) > 2 else np.nan

    mc_cols = [c for c in x.columns if re.search(r"MC", c)]
    long = x.melt(id_vars=["datetime_UTC", "interval_min", "site_id"], value_vars=mc_cols, var_name="name", value_name="value")
    m = long["name"].str.extract(r"(.*)_(.*)")
    long["depth_m"] = pd.to_numeric(m[1].str.replace("m", "", regex=False), errors="coerce")
    long["volumetric_water_content_m3_m3"] = pd.to_numeric(long["value"], errors="coerce")
    long["replicate"] = 1
    long["is_timeseries"] = True
    long["water_potential_kPa"] = np.nan
    long["gravimetric_water_content_gH2O_gs"] = np.nan

    ls17_h.append(ensure_harmonized_cols(long))

df17_harmonized = pd.concat(ls17_h, ignore_index=True)
harmonized_data.append(df17_harmonized)
harmonized_ids.append(dsid(idx))

loc17_tmp = utm32613_to_latlon(mdf17, "Easting", "Northing")
loc17 = pd.DataFrame(
    {
        "site_id": loc17_tmp["ID"],
        "latitude": loc17_tmp["latitude"],
        "longitude": loc17_tmp["longitude"],
    }
)
loc17["source_dataset_id"] = dsid(idx)
loc17 = add_loc_qc(loc17)
loc17 = loc17[loc17["site_id"].astype(str).str.contains("TMC", na=False)]
loc_data.append(loc17)

# %%
# =============================================================
# Dataset 18
# =============================================================
idx = 18
f18 = as_list(map_json[idx]["data_payload_files"])[0]
m18 = as_list(map_json[idx]["location_metadata_files"])[0]

ddf18 = read_ds_csv(idx, f18, encoding="latin1")
mdf18 = read_ds_csv(idx, m18, encoding="latin1")

x = ddf18.copy()
x["datetime_UTC"] = parse_local_to_utc(x["Date_Collected"], "%m/%d/%Y", "America/Denver")
x["interval_min"] = np.nan
x["site_id"] = (x["Field_Site"].astype(str) + "_" + x["Plot"].astype(str) + "_" + x["Topographic_Position"].astype(str)).str.replace(r"_$", "", regex=True)
x["depth_m"] = np.select(
    [
        x["Depth_Increment"].eq("0-5 cm"),
        x["Depth_Increment"].isin(["5-15 cm", "15-May"]),
        x["Depth_Increment"].eq("15 cm +"),
    ],
    [0.025, 0.10, 0.15],
    default=np.nan,
)
x["is_timeseries"] = False
x["water_potential_kPa"] = np.nan
x["volumetric_water_content_m3_m3"] = np.nan
x["gravimetric_water_content_gH2O_gs"] = pd.to_numeric(x["Soil Water Content (g H2O per gram  soil)"], errors="coerce")
x["replicate"] = x["Replicate"]

df18_harmonized = ensure_harmonized_cols(x)
harmonized_data.append(df18_harmonized)
harmonized_ids.append(dsid(idx))

loc18 = mdf18.copy()
loc18["site_id"] = (loc18["Field_Site"].astype(str) + "_" + loc18["Plot"].astype(str) + "_" + loc18["Topographic_Position"].astype(str)).str.replace(r"_$", "", regex=True)
loc18["latitude"] = pd.to_numeric(loc18["Latitude"].astype(str).str.extract(r"([-+]?\d*\.?\d+)")[0], errors="coerce")
loc18["longitude"] = pd.to_numeric(loc18["Longitude"].astype(str).str.extract(r"([-+]?\d*\.?\d+)")[0], errors="coerce")
loc18["source_dataset_id"] = dsid(idx)
loc18 = loc18[["site_id", "latitude", "longitude", "source_dataset_id"]].drop_duplicates()
loc18 = add_loc_qc(loc18)
loc_data.append(loc18)

# %%
# =============================================================
# Dataset 19-22 excluded
# =============================================================

# %%
# =============================================================
# Dataset 23
# =============================================================
idx = 23
m23 = as_list(map_json[REF_IDX]["location_metadata_files"])[0]

ddf23 = read_ds_csv(idx, "WM_SWC.csv")
sdf23 = read_ds_csv(idx, "sensor_metadata.csv")
pdf23 = read_ds_csv(idx, "plot_metadata.csv")
mdf23 = read_ds_csv(REF_IDX, m23)

x = ddf23[ddf23["Sensor.Type"] == "SWC"].copy()
x["datetime_UTC"] = parse_local_to_utc(x["Date Time"], "%Y-%m-%d %H:%M:%S", "America/Denver")

smeta = sdf23[sdf23["Sensor Type"] == "SWC"].copy()
smeta["Sensor.SN"] = pd.to_numeric(smeta["Sensor.SN"], errors="coerce")
smeta = smeta[["Sensor.SN", "Depth.cm"]]

x["Sensor.SN"] = pd.to_numeric(x["Sensor.SN"], errors="coerce")
x = x.merge(smeta, on="Sensor.SN", how="left")
x = x.merge(pdf23, on="Plot.Location", how="left")
x = x[x["Treatment"] == "control"].copy()

x["site_id"] = x["Point.Location"].astype(str) + "_" + x["Veg"].astype(str)
x["depth_m"] = pd.to_numeric(x["Depth.cm"], errors="coerce") / 100
x["is_timeseries"] = True
x["volumetric_water_content_m3_m3"] = pd.to_numeric(x["Measurement"], errors="coerce")
x["water_potential_kPa"] = np.nan
x["gravimetric_water_content_gH2O_gs"] = np.nan

x["rep_key"] = x["site_id"].astype(str) + "|" + x["Sensor.SN"].astype(str) + "|" + x["depth_m"].astype(str)
x["replicate"] = pd.factorize(x["rep_key"])[0] + 1

x = x.sort_values(["site_id", "depth_m", "replicate", "datetime_UTC"])
x["interval_min"] = x.groupby(["site_id", "depth_m", "replicate"])["datetime_UTC"].diff().dt.total_seconds() / 60.0
x.loc[x["interval_min"] < 0, "interval_min"] = np.nan

df23_harmonized = ensure_harmonized_cols(x)
harmonized_data.append(df23_harmonized)
harmonized_ids.append(dsid(idx))

loc23 = pd.DataFrame({"site_id": df23_harmonized["site_id"].dropna().unique()})
loc23["latitude"] = np.nan
loc23["longitude"] = np.nan
loc23 = loc23[loc23["site_id"].isin(df23_harmonized["site_id"].dropna().unique())].copy()
loc23["source_dataset_id"] = dsid(idx)
loc23 = add_loc_qc(loc23).drop_duplicates()
loc_data.append(loc23)

loc23 = mdf23.rename(columns={"Location_ID": "site_id", "Latitude": "latitude", "Longitude": "longitude"})[
    ["site_id", "latitude", "longitude"]
].copy()
loc23 = loc23[loc23["site_id"].isin(df23_harmonized["site_id"].str.split('_').str[0].dropna().unique())].copy()
loc23["source_dataset_id"] = dsid(idx)
loc23 = add_loc_qc(loc23)
loc_data.append(loc23)


# %%
# =============================================================
# Dataset 24
# =============================================================
idx = 24
f24 = as_list(map_json[idx]["data_payload_files"])[0]
m24 = as_list(map_json[idx]["location_metadata_files"])[0]

ddf24 = read_ds_csv(idx, f24, sep=";")
mdf24 = read_ds_csv(idx, m24, sep=";")

x = ddf24.copy()
keep = ["Timestamp"] + [c for c in x.columns if re.search(r"^P[12]_MP_(15|30|60)$", c)]
x = x[keep]
x["datetime_UTC"] = parse_local_to_utc(x["Timestamp"], "%Y-%m-%d", "America/Denver")
x["interval_min"] = interval_min(x["datetime_UTC"])
x = x.drop(columns=["Timestamp"])

mp_cols = [c for c in x.columns if re.search(r"^P[12]_MP_(15|30|60)$", c)]
long = x.melt(id_vars=["datetime_UTC", "interval_min"], value_vars=mp_cols, var_name="name", value_name="MP")
m = long["name"].str.extract(r"^(P[12])_(MP)_(\d+)$")
long["site_id"] = m[0]
long["depth_cm"] = m[2]
long = long[long["MP"].notna()].copy()
long["depth_m"] = pd.to_numeric(long["depth_cm"], errors="coerce") / 100
long["replicate"] = 1
long["is_timeseries"] = True
long["volumetric_water_content_m3_m3"] = np.nan
long["gravimetric_water_content_gH2O_gs"] = np.nan
long["water_potential_kPa"] = pd.to_numeric(long["MP"], errors="coerce")
long = long[long["water_potential_kPa"].notna()]

df24_harmonized = ensure_harmonized_cols(long)
harmonized_data.append(df24_harmonized)
harmonized_ids.append(dsid(idx))

loc24 = mdf24.rename(columns={"ID": "site_id", "Latitude": "latitude", "Longitude": "longitude"})[
    ["site_id", "latitude", "longitude"]
].copy()
loc24 = loc24[loc24["site_id"].isin(df24_harmonized["site_id"].dropna().unique())].drop_duplicates()
loc24["source_dataset_id"] = dsid(idx)
loc24 = add_loc_qc(loc24)
loc_data.append(loc24)

# %%
# =============================================================
# Dataset 25
# =============================================================
idx = 25
ddf25_conifer = read_ds_csv(idx, "Carbone_conifer.csv")
ddf25_aspen = read_ds_csv(idx, "Carbone_aspen.csv", header=None)
ddf25_aspen.columns = ddf25_conifer.columns

ddf25 = pd.concat(
    [
        ddf25_aspen.assign(site_id="aspen"),
        ddf25_conifer.assign(site_id="conifer"),
    ],
    ignore_index=True,
)

x = ddf25.copy()
x["datetime_UTC"] = parse_local_to_utc(
    x["Year"].astype(str) + "-" + x["Month"].astype(str) + "-" + x["Day"].astype(str) + "-" + x["Hour"].astype(str),
    "%Y-%m-%d-%H",
    "America/Denver",
)
x = x.sort_values(["site_id", "datetime_UTC"])
x["interval_min"] = x.groupby("site_id")["datetime_UTC"].diff().dt.total_seconds() / 60.0

vwc_cols = [c for c in x.columns if re.search(r"vwc", c, flags=re.IGNORECASE)]
long = x.melt(
    id_vars=["datetime_UTC", "site_id", "interval_min"],
    value_vars=vwc_cols,
    var_name="name",
    value_name="volumetric_water_content_m3_m3",
)
long["depth_m"] = pd.to_numeric(long["name"].str.extract(r"(\d+)")[0], errors="coerce") / 100
long["replicate"] = 1
long["is_timeseries"] = True
long["water_potential_kPa"] = np.nan
long["gravimetric_water_content_gH2O_gs"] = np.nan
long["volumetric_water_content_m3_m3"] = pd.to_numeric(long["volumetric_water_content_m3_m3"], errors="coerce")
long = long[long["volumetric_water_content_m3_m3"].notna()]

df25_harmonized = ensure_harmonized_cols(long)
harmonized_data.append(df25_harmonized)
harmonized_ids.append(dsid(idx))

loc25 = pd.DataFrame(
    {
        "site_id": ["aspen", "conifer"],
        "latitude": [38.9581589, 38.9581589],
        "longitude": [-106.9855848, -106.9855848],
    }
).drop_duplicates()
loc25["source_dataset_id"] = dsid(idx)
loc25 = add_loc_qc(loc25)
loc_data.append(loc25)

# %%
# =============================================================
# Dataset 26
# =============================================================
idx = 26
f26 = as_list(map_json[idx]["data_payload_files"])[0]
m26 = as_list(map_json[REF_IDX]["location_metadata_files"])[0]

ddf26 = read_ds_csv(idx, f26, index_col=0)
mdf26 = read_ds_csv(REF_IDX, m26)

x = ddf26.copy()
x["datetime_UTC"] = parse_local_to_utc(x["Collection date"], "%m/%d/%y", "America/Denver")
x["site_id"] = x["SampleSiteCode"]
x["depth_m"] = (pd.to_numeric(x["Top sample depth_cm"], errors="coerce") + pd.to_numeric(x["Bottom sample depth_cm"], errors="coerce")) / 2 / 100
x["replicate"] = 1
x["is_timeseries"] = False
x["interval_min"] = np.nan
x["volumetric_water_content_m3_m3"] = pd.to_numeric(x["water content %vol"], errors="coerce") / 100
x["gravimetric_water_content_gH2O_gs"] = np.nan
x["water_potential_kPa"] = np.nan

df26_harmonized = ensure_harmonized_cols(x)
harmonized_data.append(df26_harmonized)
harmonized_ids.append(dsid(idx))

loc26 = mdf26.rename(columns={"Location_ID": "site_id", "Latitude": "latitude", "Longitude": "longitude"})[
    ["site_id", "latitude", "longitude"]
].copy()
loc26 = loc26[loc26["site_id"].isin(df26_harmonized["site_id"].dropna().unique())]
loc26["source_dataset_id"] = dsid(idx)
loc26 = add_loc_qc(loc26)
loc_data.append(loc26)

# %%
# =============================================================
# Dataset 27
# =============================================================
idx = 27
f27 = as_list(map_json[idx]["data_payload_files"])
m27 = as_list(map_json[REF_IDX]["location_metadata_files"])[0]

ls27 = [read_ds_csv(idx, x) for x in f27]
mdf27 = read_ds_csv(REF_IDX, m27)

ls27_h = []
for i, d in enumerate(ls27):
    x = d.copy()
    dt = pd.to_datetime(x["Time"], format="%m/%d/%Y %H:%M", errors="coerce")
    dt = dt.dt.tz_localize("Etc/GMT+7", ambiguous="NaT", nonexistent="shift_forward")
    x["datetime_UTC"] = dt.dt.tz_convert("UTC")
    x["interval_min"] = interval_min(x["datetime_UTC"])

    cols = [c for c in x.columns if re.search(r"^S[1-4]_wc_\(m3/m3\)$|^S5_wp_\(kPa\)$", c)]
    long = x.melt(id_vars=["datetime_UTC", "interval_min"], value_vars=cols, var_name="name", value_name="value")

    long["variable"] = np.select(
        [
            long["name"].str.contains("_wc_", regex=False, na=False),
            long["name"].str.contains("_wp_", regex=False, na=False),
        ],
        ["volumetric_water_content_m3_m3", "water_potential_kPa"],
        default=np.nan,
    )

    fname = f27[i]
    long["depth_m"] = np.select(
        [
            long["name"].str.contains(r"^S1_", regex=True, na=False) & pd.Series([bool(re.search(r"ER-PHS4", fname))] * len(long)),
            long["name"].str.contains(r"^S1_", regex=True, na=False),
            long["name"].str.contains(r"^S2_", regex=True, na=False),
            long["name"].str.contains(r"^S3_", regex=True, na=False),
            long["name"].str.contains(r"^S4_", regex=True, na=False),
            long["name"].str.contains(r"^S5_", regex=True, na=False),
        ],
        [1.06, 1.15, 0.60, 0.30, 0.10, 0.30],
        default=np.nan,
    )

    site_match = re.search(r"ER-PHS[1-4]", fname)
    site_id_val = site_match.group(0) if site_match else np.nan
    long["site_id"] = site_id_val
    long["replicate"] = 1
    long["is_timeseries"] = True

    long = long[long["value"].notna() & long["variable"].notna() & long["depth_m"].notna()].copy()
    wide = (
        long.pivot_table(
            index=["datetime_UTC", "site_id", "depth_m", "replicate", "is_timeseries", "interval_min"],
            columns="variable",
            values="value",
            aggfunc="first",
        )
        .reset_index()
    )

    wide["volumetric_water_content_m3_m3"] = pd.to_numeric(wide.get("volumetric_water_content_m3_m3"), errors="coerce")
    wide["water_potential_kPa"] = pd.to_numeric(wide.get("water_potential_kPa"), errors="coerce")
    wide["gravimetric_water_content_gH2O_gs"] = np.nan

    ls27_h.append(ensure_harmonized_cols(wide))

df27_harmonized = pd.concat(ls27_h, ignore_index=True)
harmonized_data.append(df27_harmonized)
harmonized_ids.append(dsid(idx))

loc27 = mdf27.rename(columns={"Location_ID": "site_id", "Latitude": "latitude", "Longitude": "longitude"})[
    ["site_id", "latitude", "longitude"]
].copy()
loc27 = loc27[loc27["site_id"].isin(df27_harmonized["site_id"].dropna().unique())]
loc27["source_dataset_id"] = dsid(idx)
loc27 = add_loc_qc(loc27)
loc_data.append(loc27)

# %%
# =============================================================
# Location deduplication and harmonization
# =============================================================

# Here we find sites with identical names across datasets or
# sites within a small distance thresholds and collapse them to a
# single uuid

import uuid
from itertools import combinations

# Concat location data
loc_df = pd.concat(loc_data, ignore_index=True)
loc_df['latitude'] = pd.to_numeric(loc_df['latitude'], errors='coerce')
loc_df['longitude'] = pd.to_numeric(loc_df['longitude'], errors='coerce')

# Set thresholds and toggle site_id matching
# Matching thresholds (tune these)
coord_match_meters_strict = 5  # highly likely same footprint

# If TRUE, identical site_id across datasets is considered evidence
use_cross_dataset_site_id = True


# Function to normalize names for comparison
def normalize_name(x) -> str:
    if pd.isna(x):
        return ""
    x = str(x).lower()
    x = re.sub(r"[^a-z0-9]+", "", x)
    return x.strip()


# Function to find safe distance between sites using Haversine formula
def safe_dist_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Calculate distance in meters between two lat/lon points using Haversine formula"""
    if any(pd.isna([lon1, lat1, lon2, lat2])):
        return np.inf

    # Haversine formula
    R = 6371000  # Earth radius in meters
    phi1 = np.radians(lat1)
    phi2 = np.radians(lat2)
    delta_phi = np.radians(lat2 - lat1)
    delta_lambda = np.radians(lon2 - lon1)

    a = np.sin(delta_phi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(delta_lambda / 2) ** 2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

    return R * c


# Add site_name column (equivalent to site_id)
loc_df['site_name'] = loc_df['site_id']

# Prepare location dataframe
loc_df = loc_df.reset_index(drop=True)
loc_df['row_id'] = loc_df.index
loc_df['site_id'] = loc_df['site_id'].astype(str)
loc_df['source_dataset_id'] = loc_df['source_dataset_id'].astype(str)
loc_df['site_name_norm'] = loc_df['site_name'].apply(normalize_name)
loc_df['has_coords'] = loc_df['latitude'].notna() & loc_df['longitude'].notna()

n = len(loc_df)
if n == 0:
    raise ValueError("No rows in location file.")


# Build pairwise links
# Link rows likely to be same location
def is_match_pair(i: int, j: int, df: pd.DataFrame) -> bool:
    """Check if two rows should be considered the same location"""
    a = df.iloc[i]
    b = df.iloc[j]

    # Strong coordinate match
    d_m = safe_dist_m(a['longitude'], a['latitude'], b['longitude'], b['latitude'])
    if np.isfinite(d_m) and d_m <= coord_match_meters_strict:
        return True

    # Same site_id across different datasets
    if use_cross_dataset_site_id:
        same_site_id = (
            pd.notna(a['site_id']) and pd.notna(b['site_id']) and
            str(a['site_id']) != "" and str(b['site_id']) != "" and
            a['site_id'] == b['site_id']
        )
        if same_site_id:
            return True

    return False


# Find all matching pairs using Union-Find algorithm
class UnionFind:
    def __init__(self, n):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x):
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, x, y):
        px, py = self.find(x), self.find(y)
        if px == py:
            return
        if self.rank[px] < self.rank[py]:
            px, py = py, px
        self.parent[py] = px
        if self.rank[px] == self.rank[py]:
            self.rank[px] += 1


uf = UnionFind(n)

# Check all pairs and union matching locations
for i, j in combinations(range(n), 2):
    if is_match_pair(i, j, loc_df):
        uf.union(i, j)

# Assign component IDs
comp_map = {}
next_comp_id = 0
for i in range(n):
    root = uf.find(i)
    if root not in comp_map:
        comp_map[root] = next_comp_id
        next_comp_id += 1

loc_df['location_component_id'] = [comp_map[uf.find(i)] for i in range(n)]

# Assign stable UUID per component
comp_ids = sorted(loc_df['location_component_id'].unique())
uuid_map = pd.DataFrame({
    'location_component_id': comp_ids,
    'harmonized_location_uuid': [str(uuid.uuid4()) for _ in comp_ids]
})

loc_df = loc_df.merge(uuid_map, on='location_component_id', how='left')

# Optional canonical fields per UUID (centroid + representative name)
canon = loc_df.groupby('harmonized_location_uuid').agg(
    latitude_harmonized=('latitude', lambda x: np.nan if x.isna().all() else x.mean()),
    longitude_harmonized=('longitude', lambda x: np.nan if x.isna().all() else x.mean()),
    n_records_in_uuid=('row_id', 'count'),
    n_datasets_in_uuid=('source_dataset_id', 'nunique')
).reset_index()

# Join all together
loc_df = loc_df.merge(canon, on='harmonized_location_uuid', how='left')
loc_df = loc_df.drop(columns=['site_name', 'site_name_norm', 'has_coords', 'row_id', 'location_component_id'])
loc_df = loc_df.sort_values(['source_dataset_id', 'site_id', 'harmonized_location_uuid']).reset_index(drop=True)

# Quick QA summary
qa = loc_df.groupby('harmonized_location_uuid').size().reset_index(name='n')
qa = qa.sort_values('n', ascending=False)
qa['flag_multi'] = qa['n'] > 1

print(f"UUID groups with >1 member: {qa['flag_multi'].sum()} / {len(qa)}")

# %%
# =============================================================
# Write
# =============================================================

for ds_identifier, df in zip(harmonized_ids, harmonized_data):
    out_file = OUT_DIR / f"{ds_identifier}_harmonized.csv"
    df.to_csv(out_file, index=False)

loc_df = pd.concat(loc_data, ignore_index=True)
loc_df.to_csv(OUT_DIR / "location_data_harmonized.csv", index=False)