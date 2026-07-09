#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import json
import numpy as np
import pandas as pd

FOLD_DIR = Path('/scratch/jmc/data-harmonization-eval/.runs/fold-03-holdout-4')
OUT_DIR = FOLD_DIR / 'agent_outputs'
LOG_PATH = FOLD_DIR / 'AGENT_ACTION_LOG.md'
CURATOR_BUNDLE_PATH = OUT_DIR / 'curator_bundle.json'
HELDOUT_CSV_PATH = OUT_DIR / 'heldout_harmonized.csv'
PACKAGE_ID = 'ess-dive-6c7085e9c544cc6-20250424T164534831'
RAW_DIR = Path('/h/jmc/ess-dive_wfsfa_soil_datasets') / PACKAGE_ID / 'Johnsen_Bi_2025_DAE_Manuscript_Data_Package'
DATA_PATH = RAW_DIR / 'df_data.csv'
META_PATH = RAW_DIR / 'df_meta.csv'

TARGET_COLS = [
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


def log_line(action: str, subject: str, reason: str) -> None:
    ts = pd.Timestamp.now(tz='UTC').isoformat()
    with LOG_PATH.open('a', encoding='utf-8') as fh:
        fh.write(f'- {ts} | {action} | {subject} | reason: {reason}\n')


def ensure_harmonized_cols(df: pd.DataFrame) -> pd.DataFrame:
    for col in TARGET_COLS:
        if col not in df.columns:
            df[col] = np.nan
    return df[TARGET_COLS]


def parse_local_date_to_utc_iso(series: pd.Series) -> pd.Series:
    dt = pd.to_datetime(series, format='%Y-%m-%d', errors='coerce')
    dt = dt.dt.tz_localize('America/Denver', ambiguous='NaT', nonexistent='shift_forward')
    dt = dt.dt.tz_convert('UTC')
    return dt.dt.strftime('%Y-%m-%dT%H:%M:%SZ')


def harmonize() -> pd.DataFrame:
    log_line('read', str(CURATOR_BUNDLE_PATH), 'load curator bundle generated in phase 1')
    with CURATOR_BUNDLE_PATH.open('r', encoding='utf-8') as fh:
        bundle = json.load(fh)
    if bundle.get('package_id') != PACKAGE_ID:
        raise ValueError(f'Unexpected package_id in curator bundle: {bundle.get("package_id")}')

    log_line('read', str(DATA_PATH), 'read held-out raw measurement payload df_data.csv')
    ddf = pd.read_csv(DATA_PATH)
    log_line('read', str(META_PATH), 'read held-out raw row-aligned metadata df_meta.csv')
    mdf = pd.read_csv(META_PATH)

    if len(ddf) != len(mdf):
        raise ValueError(f'Row count mismatch: df_data={len(ddf)} df_meta={len(mdf)}')
    required_data = {'swc', 'swp'}
    required_meta = {'site', 'datetime'}
    missing_data = required_data.difference(ddf.columns)
    missing_meta = required_meta.difference(mdf.columns)
    if missing_data or missing_meta:
        raise ValueError(f'Missing required columns: data={sorted(missing_data)} meta={sorted(missing_meta)}')

    x = pd.concat([mdf.reset_index(drop=True), ddf.reset_index(drop=True)], axis=1)
    out = pd.DataFrame(index=x.index)
    out['datetime_UTC'] = parse_local_date_to_utc_iso(x['datetime'])
    out['site_id'] = x['site'].astype(str)
    out['depth_m'] = np.nan
    out['replicate'] = 1
    out['is_timeseries'] = True
    out['interval_min'] = 1440.0
    out['volumetric_water_content_m3_m3'] = pd.to_numeric(x['swc'], errors='coerce')
    out['gravimetric_water_content_gH2O_gs'] = np.nan
    out['water_potential_kPa'] = pd.to_numeric(x['swp'], errors='coerce')
    out = ensure_harmonized_cols(out)
    out = out[out['datetime_UTC'].notna()].copy()
    return out


if __name__ == '__main__':
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df = harmonize()
    log_line('write', str(HELDOUT_CSV_PATH), 'write harmonized held-out target-schema CSV')
    df.to_csv(HELDOUT_CSV_PATH, index=False)
    log_line('exit_status=0', str(HELDOUT_CSV_PATH), f'wrote {len(df)} harmonized rows')
    print(f'wrote {HELDOUT_CSV_PATH} rows={len(df)}')
