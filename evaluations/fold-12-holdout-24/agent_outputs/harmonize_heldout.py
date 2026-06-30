from __future__ import annotations
from pathlib import Path
import re
from datetime import datetime
import numpy as np
import pandas as pd

SANDBOX = Path('/scratch/jmc/data-harmonization-eval/.runs/fold-12-holdout-24')
ACTION_LOG = SANDBOX / 'AGENT_ACTION_LOG.md'
OUT_DIR = SANDBOX / 'agent_outputs'
BASE_DIR = Path('/h/jmc/ess-dive_wfsfa_soil_datasets')
PACKAGE_ID = 'ess-dive-daa156d2129c471-20250716T160748658'
DATA_FILE = 'Iso_MP_Sap_DataDaily_ESSDiveUpload_R1.csv'
LOC_FILE = 'Locations.csv'
RAW_DIR = BASE_DIR / PACKAGE_ID
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


def log(action: str, subject: str, reason: str) -> None:
    ts = datetime.now().astimezone().isoformat()
    with ACTION_LOG.open('a', encoding='utf-8') as fh:
        fh.write(f'{ts} | action={action} | subject={subject} | reason={reason}\n')


def parse_local_to_utc(series: pd.Series, fmt: str | None, tz: str) -> pd.Series:
    dt = pd.to_datetime(series, format=fmt, errors='coerce')
    dt = dt.dt.tz_localize(tz, ambiguous='NaT', nonexistent='shift_forward')
    return dt.dt.tz_convert('UTC')


def ensure_harmonized_cols(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in SCHEMA:
        if col not in out.columns:
            out[col] = np.nan
    return out[SCHEMA]


def main() -> None:
    data_path = RAW_DIR / DATA_FILE
    loc_path = RAW_DIR / LOC_FILE
    output_path = OUT_DIR / 'heldout_harmonized.csv'

    log('read', str(data_path), 'load heldout semicolon-delimited measurement payload')
    df = pd.read_csv(data_path, sep=';')
    log('read', str(loc_path), 'load heldout location metadata for selected site ids')
    loc = pd.read_csv(loc_path, sep=';')

    mp_cols = [c for c in df.columns if re.fullmatch(r'P[12]_MP_\d+', c)]
    if not mp_cols:
        raise ValueError('No P1/P2 matrix potential columns found')

    x = df[['Timestamp'] + mp_cols].copy()
    x['datetime_UTC'] = parse_local_to_utc(x['Timestamp'], '%Y-%m-%d', 'America/Denver')
    for col in mp_cols:
        x[col] = pd.to_numeric(x[col], errors='coerce')

    long = x.melt(
        id_vars=['datetime_UTC'],
        value_vars=mp_cols,
        var_name='source_variable',
        value_name='water_potential_kPa',
    )
    parsed = long['source_variable'].str.extract(r'^(P[12])_MP_(\d+)$')
    long['site_id'] = parsed[0]
    long['depth_m'] = pd.to_numeric(parsed[1], errors='coerce') / 100.0
    long['replicate'] = 1
    long['is_timeseries'] = True
    long['volumetric_water_content_m3_m3'] = np.nan
    long['gravimetric_water_content_gH2O_gs'] = np.nan

    long = long.sort_values(['site_id', 'depth_m', 'datetime_UTC']).reset_index(drop=True)
    long['interval_min'] = (
        long.groupby(['site_id', 'depth_m'])['datetime_UTC']
        .diff()
        .dt.total_seconds()
        .div(60.0)
    )

    valid_sites = set(loc['ID'].astype(str))
    missing_sites = sorted(set(long['site_id'].astype(str)) - valid_sites)
    if missing_sites:
        raise ValueError(f'Missing Locations.csv rows for site ids: {missing_sites}')

    harmonized = ensure_harmonized_cols(long)
    log('write', str(output_path), 'write heldout harmonized CSV with target schema')
    harmonized.to_csv(output_path, index=False)
    print(f'wrote {output_path}')
    print(f'rows={len(harmonized)}')
    print('schema=' + ','.join(harmonized.columns))


if __name__ == '__main__':
    main()
