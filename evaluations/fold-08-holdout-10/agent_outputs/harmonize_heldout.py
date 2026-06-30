from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
import numpy as np
import pandas as pd

FOLD_DIR = Path('/scratch/jmc/data-harmonization-eval/.runs/fold-08-holdout-10')
LOG_PATH = FOLD_DIR / 'AGENT_ACTION_LOG.md'
RAW_PATH = Path('/h/jmc/ess-dive_wfsfa_soil_datasets/ess-dive-01092fc392bc46d-20240819T143818677/Soil_water_content_Fig4e.csv')
OUT_PATH = FOLD_DIR / 'agent_outputs' / 'heldout_harmonized.csv'

SCHEMA = [
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


def trace(action: str, subject: str, reason: str) -> None:
    ts = datetime.now(timezone.utc).astimezone().isoformat()
    with LOG_PATH.open('a', encoding='utf-8') as f:
        f.write(f'{ts} | action={action} | subject={subject} | reason={reason}\n')


def parse_local_to_utc(series: pd.Series, fmt: str, tz: str) -> pd.Series:
    dt = pd.to_datetime(series, format=fmt, errors='coerce')
    dt = dt.dt.tz_localize(tz, ambiguous='NaT', nonexistent='shift_forward')
    return dt.dt.tz_convert('UTC')


def ensure_harmonized_cols(df: pd.DataFrame) -> pd.DataFrame:
    for col in SCHEMA:
        if col not in df.columns:
            df[col] = np.nan
    return df[SCHEMA]


def harmonize() -> pd.DataFrame:
    trace('file_read', str(RAW_PATH), 'read held-out raw soil water content payload')
    raw = pd.read_csv(RAW_PATH)
    data = raw.iloc[1:].copy()

    value_cols = [c for c in data.columns if re.search(r'vol_water_content', c, flags=re.IGNORECASE)]
    long = data.melt(
        id_vars=['Date'],
        value_vars=value_cols,
        var_name='source_variable',
        value_name='volumetric_water_content_m3_m3',
    )

    long['datetime_UTC'] = parse_local_to_utc(long['Date'], '%Y-%m-%d', 'America/Denver')
    long['site_id'] = 'ER-' + long['source_variable'].str.extract(r'(PLM\d+)')[0]
    long['volumetric_water_content_m3_m3'] = pd.to_numeric(long['volumetric_water_content_m3_m3'], errors='coerce')
    long['depth_m'] = np.nan
    long['replicate'] = 1
    long['is_timeseries'] = True
    long['gravimetric_water_content_gH2O_gs'] = np.nan
    long['water_potential_kPa'] = np.nan

    long = long.sort_values(['site_id', 'datetime_UTC']).reset_index(drop=True)
    long['interval_min'] = long.groupby('site_id')['datetime_UTC'].diff().dt.total_seconds() / 60.0

    out = ensure_harmonized_cols(long)
    out = out[out['datetime_UTC'].notna() & out['site_id'].notna() & out['volumetric_water_content_m3_m3'].notna()].copy()
    out['datetime_UTC'] = out['datetime_UTC'].dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    return out


if __name__ == '__main__':
    df = harmonize()
    trace('file_write', str(OUT_PATH), 'write held-out harmonized CSV')
    df.to_csv(OUT_PATH, index=False)
    print(f'wrote {OUT_PATH} rows={len(df)} columns={list(df.columns)}')
