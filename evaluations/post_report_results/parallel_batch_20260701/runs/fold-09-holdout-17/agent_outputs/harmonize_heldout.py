from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone
import re
import numpy as np
import pandas as pd

FOLD_DIR = Path('/scratch/jmc/data-harmonization-eval/.runs/fold-09-holdout-17')
ACTION_LOG = FOLD_DIR / 'AGENT_ACTION_LOG.md'
OUT_DIR = FOLD_DIR / 'agent_outputs'
BASE_DIR = Path('/h/jmc/ess-dive_wfsfa_soil_datasets')
PACKAGE_ID = 'ess-dive-be919d7d5d42c94-20240130T205332180'
DATASET_DIR = BASE_DIR / PACKAGE_ID
PAYLOAD_FILES = [
    'FieldData/Soil_Moisture_Data/TMC1.csv',
    'FieldData/Soil_Moisture_Data/TMC2.csv',
    'FieldData/Soil_Moisture_Data/TMC4.csv',
    'FieldData/Soil_Moisture_Data/TMC5.csv',
    'FieldData/Soil_Moisture_Data/TMC6.csv',
]
TARGET_COLUMNS = [
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
    with ACTION_LOG.open('a', encoding='utf-8') as fh:
        fh.write(f'{ts} | action={action} | subject={subject} | reason={reason}\n')


def parse_local_to_utc(series: pd.Series, fmt: str | None, tz: str) -> pd.Series:
    dt = pd.to_datetime(series, format=fmt, errors='coerce')
    dt = dt.dt.tz_localize(tz, ambiguous='NaT', nonexistent='shift_forward')
    return dt.dt.tz_convert('UTC')


def ensure_harmonized_cols(df: pd.DataFrame) -> pd.DataFrame:
    for col in TARGET_COLUMNS:
        if col not in df.columns:
            df[col] = np.nan
    return df[TARGET_COLUMNS]


def harmonize_file(rel_path: str) -> pd.DataFrame:
    path = DATASET_DIR / rel_path
    trace('read', str(path), 'read held-out soil moisture CSV for harmonization')
    df = pd.read_csv(path, skiprows=[1])
    site_id = Path(rel_path).stem
    vwc_cols = [c for c in df.columns if re.fullmatch(r'MC_\d+(?:\.\d+)?m', c)]
    x = df[['DateTime'] + vwc_cols].copy()
    x['datetime_UTC'] = parse_local_to_utc(x['DateTime'], '%Y-%m-%d %H:%M:%S', 'America/Denver')
    x = x.dropna(subset=['datetime_UTC']).sort_values('datetime_UTC')
    x['site_id'] = site_id
    long = x.melt(
        id_vars=['datetime_UTC', 'site_id'],
        value_vars=vwc_cols,
        var_name='source_variable',
        value_name='volumetric_water_content_m3_m3',
    )
    long['depth_m'] = pd.to_numeric(
        long['source_variable'].str.extract(r'MC_(\d+(?:\.\d+)?)m')[0],
        errors='coerce',
    )
    long['volumetric_water_content_m3_m3'] = pd.to_numeric(
        long['volumetric_water_content_m3_m3'],
        errors='coerce',
    )
    long = long.dropna(subset=['datetime_UTC', 'depth_m', 'volumetric_water_content_m3_m3'])
    long = long.sort_values(['site_id', 'depth_m', 'datetime_UTC']).reset_index(drop=True)
    long['replicate'] = 1
    long['is_timeseries'] = True
    long['interval_min'] = long.groupby(['site_id', 'depth_m'])['datetime_UTC'].diff().dt.total_seconds() / 60.0
    long['gravimetric_water_content_gH2O_gs'] = np.nan
    long['water_potential_kPa'] = np.nan
    return ensure_harmonized_cols(long)


def main() -> None:
    frames = [harmonize_file(rel_path) for rel_path in PAYLOAD_FILES]
    out = pd.concat(frames, ignore_index=True)
    out_path = OUT_DIR / 'heldout_harmonized.csv'
    trace('write', str(out_path), 'write held-out harmonized CSV')
    out.to_csv(out_path, index=False)
    print(f'wrote {out_path}')
    print(f'rows {len(out)}')
    print('columns ' + ','.join(out.columns))


if __name__ == '__main__':
    main()
