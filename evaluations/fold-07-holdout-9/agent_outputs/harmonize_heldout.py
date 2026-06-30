from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd

PACKAGE_ID = "ess-dive-460e696d8210ed3-20260309T155937802"
RAW_BASE = Path("/h/jmc/ess-dive_wfsfa_soil_datasets")
RAW_FILE = RAW_BASE / PACKAGE_ID / "NEON_plot_TDR.csv"
OUT_FILE = Path(__file__).resolve().parent / "heldout_harmonized.csv"

HARMONIZED_COLUMNS = [
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


def parse_local_date_to_utc(series: pd.Series) -> pd.Series:
    dt = pd.to_datetime(series, format="%Y-%m-%d", errors="coerce")
    dt = dt.dt.tz_localize("America/Denver", ambiguous="NaT", nonexistent="shift_forward")
    return dt.dt.tz_convert("UTC")


def ensure_harmonized_cols(df: pd.DataFrame) -> pd.DataFrame:
    for col in HARMONIZED_COLUMNS:
        if col not in df.columns:
            df[col] = np.nan
    return df[HARMONIZED_COLUMNS]


def harmonize() -> pd.DataFrame:
    df = pd.read_csv(RAW_FILE)
    df["datetime_UTC"] = parse_local_date_to_utc(df["Collection Date"])
    df = df[df["datetime_UTC"].notna()].copy()

    long = df.melt(
        id_vars=["datetime_UTC", "SampleSiteCode"],
        value_vars=["VWC_1", "VWC_2"],
        var_name="source_variable",
        value_name="volumetric_water_content_m3_m3",
    )
    long["volumetric_water_content_m3_m3"] = pd.to_numeric(
        long["volumetric_water_content_m3_m3"], errors="coerce"
    )
    long = long[
        long["volumetric_water_content_m3_m3"].notna()
        & (long["volumetric_water_content_m3_m3"] != -9999)
    ].copy()
    long["volumetric_water_content_m3_m3"] = long["volumetric_water_content_m3_m3"] / 100.0

    long["site_id"] = long["SampleSiteCode"].astype(str)
    long["replicate"] = pd.to_numeric(
        long["source_variable"].str.extract(r"VWC_(\d+)")[0], errors="coerce"
    ).astype("Int64")
    long["depth_m"] = np.nan
    long["is_timeseries"] = False
    long["interval_min"] = np.nan
    long["gravimetric_water_content_gH2O_gs"] = np.nan
    long["water_potential_kPa"] = np.nan

    out = ensure_harmonized_cols(long)
    out = out.sort_values(["datetime_UTC", "site_id", "replicate"], kind="stable").reset_index(drop=True)
    out["datetime_UTC"] = out["datetime_UTC"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return out


if __name__ == "__main__":
    harmonized = harmonize()
    harmonized.to_csv(OUT_FILE, index=False)
    print(f"wrote {OUT_FILE}")
    print(f"rows {len(harmonized)}")
    print("columns " + ",".join(harmonized.columns))
