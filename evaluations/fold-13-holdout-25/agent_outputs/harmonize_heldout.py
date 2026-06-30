from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd

PACKAGE_ID = "ess-dive-e67ab1151ebc525-20230929T190307767"
RAW_DIR = Path("/h/jmc/ess-dive_wfsfa_soil_datasets") / PACKAGE_ID
OUT_PATH = Path("/scratch/jmc/data-harmonization-eval/.runs/fold-13-holdout-25/agent_outputs/heldout_harmonized.csv")

COLUMNS = [
    "Year", "Month", "Day", "Hour",
    "CO2-50cm", "CO2-15cm", "CO2-5cm", "CO2-0cm", "CO2-above",
    "T-50cm", "T-15cm", "T-5cm", "T-0cm", "T-above",
    "VWC-50cm", "VWC-15cm", "VWC-5cm",
    "DecagonT-50cm", "DecagonT-15cm", "DecagonT-5cm",
    "EC-50cm", "EC-15cm", "EC-5cm", "BatteryVoltage",
]
TARGET_COLUMNS = [
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
VWC_COLUMNS = ["VWC-50cm", "VWC-15cm", "VWC-5cm"]
DEPTH_M = {"VWC-50cm": 0.50, "VWC-15cm": 0.15, "VWC-5cm": 0.05}


def read_source(filename: str, headerless: bool) -> pd.DataFrame:
    path = RAW_DIR / filename
    if headerless:
        return pd.read_csv(path, header=None, names=COLUMNS)
    return pd.read_csv(path)


def local_timestamp_to_utc(df: pd.DataFrame) -> pd.Series:
    local = pd.to_datetime(
        {
            "year": pd.to_numeric(df["Year"], errors="coerce"),
            "month": pd.to_numeric(df["Month"], errors="coerce"),
            "day": pd.to_numeric(df["Day"], errors="coerce"),
            "hour": pd.to_numeric(df["Hour"], errors="coerce"),
        },
        errors="coerce",
    )
    localized = local.dt.tz_localize("Etc/GMT+7", ambiguous="NaT", nonexistent="NaT")
    return localized.dt.tz_convert("UTC")


def harmonize_one(filename: str, site_id: str, headerless: bool) -> pd.DataFrame:
    df = read_source(filename, headerless=headerless).copy()
    df["datetime_UTC"] = local_timestamp_to_utc(df)
    df = df[df["datetime_UTC"].notna()].copy()

    long = df.melt(
        id_vars=["datetime_UTC"],
        value_vars=VWC_COLUMNS,
        var_name="source_variable",
        value_name="volumetric_water_content_m3_m3",
    )
    long["volumetric_water_content_m3_m3"] = pd.to_numeric(
        long["volumetric_water_content_m3_m3"], errors="coerce"
    )
    long = long[long["volumetric_water_content_m3_m3"].between(0, 1, inclusive="both")].copy()

    long["site_id"] = site_id
    long["depth_m"] = long["source_variable"].map(DEPTH_M).astype(float)
    long["replicate"] = 1
    long["is_timeseries"] = True
    long["gravimetric_water_content_gH2O_gs"] = np.nan
    long["water_potential_kPa"] = np.nan

    long = long.sort_values(["site_id", "depth_m", "datetime_UTC"]).reset_index(drop=True)
    long["interval_min"] = (
        long.groupby(["site_id", "depth_m"])["datetime_UTC"].diff().dt.total_seconds() / 60.0
    )
    long["datetime_UTC"] = long["datetime_UTC"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return long[TARGET_COLUMNS]


def main() -> None:
    parts = [
        harmonize_one("Carbone_aspen.csv", "Carbone_aspen", headerless=True),
        harmonize_one("Carbone_conifer.csv", "Carbone_conifer", headerless=False),
    ]
    out = pd.concat(parts, ignore_index=True)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_PATH, index=False)
    print(f"wrote {OUT_PATH}")
    print(f"rows {len(out)}")
    print("schema " + ",".join(out.columns))


if __name__ == "__main__":
    main()
