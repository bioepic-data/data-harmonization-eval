from __future__ import annotations

from pathlib import Path
import os
import numpy as np
import pandas as pd

PKG_ID = "ess-dive-8ac2940c708a515-20230504T210140482233"
RAW_DIR = Path(os.environ.get("HELDOUT_RAW_DIR", "/h/jmc/ess-dive_wfsfa_soil_datasets")) / PKG_ID
OUT_DIR = Path(__file__).resolve().parent
OUT_CSV = OUT_DIR / "heldout_harmonized.csv"


def parse_local_to_utc(series: pd.Series, fmt: str | None, tz: str) -> pd.Series:
    dt = pd.to_datetime(series, format=fmt, errors="coerce")
    dt = dt.dt.tz_localize(tz, ambiguous="NaT", nonexistent="shift_forward")
    return dt.dt.tz_convert("UTC")


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
    for col in cols:
        if col not in df.columns:
            df[col] = np.nan
    return df[cols]


def harmonize() -> pd.DataFrame:
    swc = pd.read_csv(RAW_DIR / "SM_SWC.csv")
    sensors = pd.read_csv(RAW_DIR / "Microclimate_Sensors.csv")

    smeta = sensors[sensors["Sensor Type"].astype(str).eq("SWC")].copy()
    smeta["Sensor.SN"] = pd.to_numeric(smeta["Sensor.SN"], errors="coerce").astype("Int64")
    smeta = smeta[["Sensor.SN", "SFA_Location", "Site", "Treatment", "Subplot", "Start", "Stop"]]

    x = swc.copy()
    x["Sensor.SN"] = pd.to_numeric(x["Sensor.SN"], errors="coerce").astype("Int64")
    x = x.merge(smeta, on=["Sensor.SN", "SFA_Location"], how="left", validate="many_to_one")

    # Remove experimental snowmelt manipulation plots; retain control sensors only.
    x = x[x["Treatment"].eq("ctl")].copy()

    x["datetime_UTC_dt"] = parse_local_to_utc(x["Date Time"], "%Y-%m-%d %H:%M:%S", "America/Denver")
    x["site_id"] = x["SFA_Location"].astype(str)
    x["depth_m"] = np.nan

    sensor_keys = x[["site_id", "Sensor.SN"]].drop_duplicates().sort_values(["site_id", "Sensor.SN"])
    sensor_keys["replicate"] = sensor_keys.groupby("site_id").cumcount() + 1
    x = x.merge(sensor_keys, on=["site_id", "Sensor.SN"], how="left", validate="many_to_one")

    x["is_timeseries"] = True
    x["volumetric_water_content_m3_m3"] = pd.to_numeric(x["Measurement"], errors="coerce")
    x["gravimetric_water_content_gH2O_gs"] = np.nan
    x["water_potential_kPa"] = np.nan

    x = x.sort_values(["site_id", "replicate", "datetime_UTC_dt"])
    x["interval_min"] = x.groupby(["site_id", "replicate"])["datetime_UTC_dt"].diff().dt.total_seconds() / 60.0
    x.loc[x["interval_min"] < 0, "interval_min"] = np.nan
    x["datetime_UTC"] = x["datetime_UTC_dt"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    x = x[x["volumetric_water_content_m3_m3"].notna()].copy()
    return ensure_harmonized_cols(x)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = harmonize()
    out.to_csv(OUT_CSV, index=False)
    print(f"wrote {OUT_CSV}")
    print(f"rows={len(out)}")
    print("columns=" + ",".join(out.columns))


if __name__ == "__main__":
    main()
