#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

RUN_DIR = Path('/scratch/jmc/data-harmonization-eval/.runs/fold-05-holdout-7')
LOG_PATH = RUN_DIR / 'AGENT_ACTION_LOG.md'
OUT_DIR = RUN_DIR / 'agent_outputs'
PACKAGE_ID = 'ess-dive-38e901ec3d7bd24-20230504T211548257225'
RAW_DIR = Path('/h/jmc/ess-dive_wfsfa_soil_datasets') / PACKAGE_ID
PAYLOAD = RAW_DIR / 'BM_Merged_T_VWC_0616_1018.csv'
OUT_CSV = OUT_DIR / 'heldout_harmonized.csv'

HARMONIZED_COLS = [
    'datetime_UTC',
    'site_id',
    'depth_m',
    'replicate',
    'is_timeseries',
    'interval_min',
    'volumetric_water_content_m3_m3',
    'gravimetric_water_content_gH2O_gs',
    'water_potential_kPa',
]


def log(action: str, subject: str, reason: str) -> None:
    ts = datetime.now(timezone.utc).astimezone().isoformat()
    with LOG_PATH.open('a', encoding='utf-8') as f:
        f.write(f'- {ts} | action={action} | subject=`{subject}` | reason={reason}\n')


def parse_local_to_utc(series: pd.Series, fmt: str, tz: str) -> pd.Series:
    dt = pd.to_datetime(series, format=fmt, errors='coerce')
    dt = dt.dt.tz_localize(tz, ambiguous='NaT', nonexistent='shift_forward')
    return dt.dt.tz_convert('UTC')


def ensure_harmonized_cols(df: pd.DataFrame) -> pd.DataFrame:
    for col in HARMONIZED_COLS:
        if col not in df.columns:
            df[col] = np.nan
    return df[HARMONIZED_COLS]


def main() -> None:
    log('read', str(PAYLOAD), 'read held-out primary VWC payload for harmonization')
    df = pd.read_csv(PAYLOAD)

    x = pd.DataFrame()
    dt_utc = parse_local_to_utc(df['date.time'], '%m/%d/%y %H:%M', 'America/Denver')
    x['datetime_dt'] = dt_utc
    x['datetime_UTC'] = dt_utc.dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    x['site_id'] = 'BM'
    x['depth_m'] = pd.to_numeric(df['Depth (cm)'], errors='coerce') / 100.0
    x['replicate'] = 1
    x['is_timeseries'] = True
    x['volumetric_water_content_m3_m3'] = pd.to_numeric(df['Volumetric Water Content'], errors='coerce')
    x['gravimetric_water_content_gH2O_gs'] = np.nan
    x['water_potential_kPa'] = np.nan

    x = x[x['datetime_dt'].notna() & x['depth_m'].notna() & x['volumetric_water_content_m3_m3'].notna()].copy()
    x = x.sort_values(['site_id', 'depth_m', 'replicate', 'datetime_dt']).reset_index(drop=True)
    x['interval_min'] = (
        x.groupby(['site_id', 'depth_m', 'replicate'])['datetime_dt']
        .diff()
        .dt.total_seconds()
        .div(60.0)
    )
    x.loc[x['interval_min'] < 0, 'interval_min'] = np.nan

    out = ensure_harmonized_cols(x)
    log('write', str(OUT_CSV), 'write required heldout_harmonized.csv output')
    out.to_csv(OUT_CSV, index=False)


if __name__ == '__main__':
    main()
