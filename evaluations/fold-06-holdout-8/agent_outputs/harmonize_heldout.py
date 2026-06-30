from __future__ import annotations

from pathlib import Path
from datetime import datetime
import re
import numpy as np
import pandas as pd

RUN_DIR = Path('/scratch/jmc/data-harmonization-eval/.runs/fold-06-holdout-8')
LOG_PATH = RUN_DIR / 'AGENT_ACTION_LOG.md'
OUT_DIR = RUN_DIR / 'agent_outputs'
RAW_DIR = Path('/h/jmc/ess-dive_wfsfa_soil_datasets/ess-dive-61a0ecd70856892-20230808T205724993')
DATASET_IDENTIFIER = 'ess-dive-61a0ecd70856892-20230808T205724993'
SITE_ID = 'Slate River OBJ-2'
OUTPUT_COLUMNS = [
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
DATA_FILES = [
    'SLT_OBJ2_SoilSensors_2018_data.csv',
    'SLT_OBJ2_SoilSensors_2019_data.csv',
    'SLT_OBJ2_SoilSensors_2020_data.csv',
    'SLT_OBJ2_SoilSensors_2021_data.csv',
]


def log_action(action: str, subject: str, reason: str) -> None:
    with LOG_PATH.open('a', encoding='utf-8') as handle:
        handle.write(f"- {datetime.now().astimezone().isoformat()} | action={action} | subject={subject} | reason={reason}\n")


def parse_fixed_mst_to_utc(series: pd.Series) -> pd.Series:
    dt = pd.to_datetime(series, format='%Y-%m-%d %H:%M:%S', errors='coerce')
    dt = dt.dt.tz_localize('Etc/GMT+7', ambiguous='NaT', nonexistent='shift_forward')
    return dt.dt.tz_convert('UTC')


def extract_depth_m(column_name: str) -> float:
    match = re.search(r'_(\d+(?:\.\d+)?)cm\.', column_name)
    if not match:
        return np.nan
    return float(match.group(1)) / 100.0


def ensure_harmonized_cols(df: pd.DataFrame) -> pd.DataFrame:
    for col in OUTPUT_COLUMNS:
        if col not in df.columns:
            df[col] = np.nan
    return df[OUTPUT_COLUMNS]


def harmonize_file(filename: str) -> pd.DataFrame:
    path = RAW_DIR / filename
    log_action('read', str(path), 'read raw held-out data payload for harmonization')
    df = pd.read_csv(path)
    x = pd.DataFrame()
    x['datetime'] = parse_fixed_mst_to_utc(df['DateTime.MST'])
    x['datetime_UTC'] = x['datetime'].dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    x['interval_min'] = x['datetime'].diff().dt.total_seconds() / 60.0

    value_cols = [
        c for c in df.columns
        if re.match(r'^SoilMoisture_\d+(?:\.\d+)?cm\.m3\.m3$', c)
        or re.match(r'^SoilMatricPot_\d+(?:\.\d+)?cm\.kPa$', c)
    ]
    combined = pd.concat([x[['datetime_UTC', 'interval_min']], df[value_cols]], axis=1)
    long = combined.melt(
        id_vars=['datetime_UTC', 'interval_min'],
        value_vars=value_cols,
        var_name='source_variable',
        value_name='value',
    )
    long['value'] = pd.to_numeric(long['value'], errors='coerce')
    long.loc[long['value'] == -9999, 'value'] = np.nan
    long['depth_m'] = long['source_variable'].map(extract_depth_m)
    long['target_variable'] = np.where(
        long['source_variable'].str.startswith('SoilMoisture_'),
        'volumetric_water_content_m3_m3',
        'water_potential_kPa',
    )
    long = long.dropna(subset=['datetime_UTC', 'depth_m', 'target_variable']).copy()

    wide = (
        long.pivot_table(
            index=['datetime_UTC', 'interval_min', 'depth_m'],
            columns='target_variable',
            values='value',
            aggfunc='first',
            dropna=False,
        )
        .reset_index()
        .rename_axis(None, axis=1)
    )
    wide['site_id'] = SITE_ID
    wide['replicate'] = 1
    wide['is_timeseries'] = True
    wide['gravimetric_water_content_gH2O_gs'] = np.nan
    wide = ensure_harmonized_cols(wide)
    both_missing = wide['volumetric_water_content_m3_m3'].isna() & wide['water_potential_kPa'].isna()
    wide = wide.loc[~both_missing].copy()
    return wide


def main() -> None:
    frames = [harmonize_file(filename) for filename in DATA_FILES]
    out = pd.concat(frames, ignore_index=True)
    out = out.sort_values(['datetime_UTC', 'site_id', 'depth_m', 'replicate']).reset_index(drop=True)
    out = ensure_harmonized_cols(out)
    output_path = OUT_DIR / 'heldout_harmonized.csv'
    log_action('write', str(output_path), 'write required held-out harmonized CSV')
    out.to_csv(output_path, index=False)
    print(f'wrote {output_path}')
    print(f'rows {len(out)}')
    print('columns ' + ','.join(out.columns))


if __name__ == '__main__':
    main()
