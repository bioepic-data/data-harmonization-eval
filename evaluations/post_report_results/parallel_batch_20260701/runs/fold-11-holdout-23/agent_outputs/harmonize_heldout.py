from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

RUN_DIR = Path('/scratch/jmc/data-harmonization-eval/.runs/fold-11-holdout-23')
RAW_DIR = Path('/h/jmc/ess-dive_wfsfa_soil_datasets/ess-dive-a99be52b7a6114c-20230504T210134503379')
OUT_DIR = RUN_DIR / 'agent_outputs'
LOG_PATH = RUN_DIR / 'AGENT_ACTION_LOG.md'
OUTPUT_PATH = OUT_DIR / 'heldout_harmonized.csv'

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


def log_action(action: str, subject: Path | str, reason: str) -> None:
    ts = datetime.now(timezone.utc).astimezone().isoformat()
    with LOG_PATH.open('a') as log:
        log.write(f'{ts} | action={action} | subject={subject} | reason={reason}\n')


def read_csv_logged(path: Path, reason: str, **kwargs) -> pd.DataFrame:
    log_action('file read', path, reason)
    return pd.read_csv(path, **kwargs)


def local_mst_to_utc_string(series: pd.Series) -> pd.Series:
    dt = pd.to_datetime(series, errors='coerce')
    utc = dt.dt.tz_localize('Etc/GMT+7').dt.tz_convert('UTC')
    return utc.dt.strftime('%Y-%m-%dT%H:%M:%SZ')


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    swc = read_csv_logged(RAW_DIR / 'WM_SWC.csv', 'read held-out SWC payload for harmonization')
    sensors = read_csv_logged(RAW_DIR / 'sensor_metadata.csv', 'read held-out sensor metadata for depth/site joins')

    swc = swc.copy()
    sensors = sensors.copy()
    swc_sensors = sensors.loc[sensors['Sensor Type'].eq('SWC')].copy()
    swc['Sensor.SN'] = pd.to_numeric(swc['Sensor.SN'], errors='coerce').astype('Int64')
    swc_sensors['Sensor.SN'] = pd.to_numeric(swc_sensors['Sensor.SN'], errors='coerce').round().astype('Int64')
    meta_cols = [
        'Sensor.SN',
        'Point.Location',
        'Plot.Location',
        'Zone',
        'Depth.cm',
        'Veg',
        'Notes',
        'start',
        'stop',
    ]
    merged = swc.merge(swc_sensors[meta_cols], on='Sensor.SN', how='left', suffixes=('', '.meta'))

    for col in ['Plot.Location', 'Point.Location', 'Veg']:
        meta_col = f'{col}.meta'
        if meta_col in merged.columns:
            merged[f'{col}.resolved'] = merged[meta_col].combine_first(merged[col])
        else:
            merged[f'{col}.resolved'] = merged[col]

    merged['depth_m'] = pd.to_numeric(merged['Depth.cm'], errors='coerce') / 100.0
    valid = (
        merged['depth_m'].notna()
        & merged['Plot.Location.resolved'].notna()
        & merged['Point.Location.resolved'].notna()
        & merged['Veg.resolved'].notna()
    )
    x = merged.loc[valid].copy()

    x['site_id'] = (
        x['Plot.Location.resolved'].astype(str)
        + '_'
        + x['Point.Location.resolved'].astype(str)
        + '_'
        + x['Veg.resolved'].astype(str)
    )

    present_sensors = x[['Sensor.SN', 'site_id', 'depth_m']].drop_duplicates().copy()
    present_sensors = present_sensors.sort_values(['site_id', 'depth_m', 'Sensor.SN'])
    present_sensors['replicate'] = present_sensors.groupby(['site_id', 'depth_m'], dropna=False).cumcount() + 1
    x = x.merge(present_sensors[['Sensor.SN', 'replicate']], on='Sensor.SN', how='left')

    dt_local = pd.to_datetime(x['Date Time'], errors='coerce')
    dt_utc = dt_local.dt.tz_localize('Etc/GMT+7').dt.tz_convert('UTC')
    x['datetime_UTC'] = dt_utc.dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    x['_dt_utc'] = dt_utc

    x = x.sort_values(['site_id', 'depth_m', 'replicate', '_dt_utc', 'Sensor.SN']).copy()
    x['interval_min'] = (
        x.groupby(['site_id', 'depth_m', 'replicate'], dropna=False)['_dt_utc']
        .diff()
        .dt.total_seconds()
        .div(60.0)
    )
    x['is_timeseries'] = True
    x['volumetric_water_content_m3_m3'] = pd.to_numeric(x['Measurement'], errors='coerce')
    x['gravimetric_water_content_gH2O_gs'] = np.nan
    x['water_potential_kPa'] = np.nan
    x['replicate'] = pd.to_numeric(x['replicate'], errors='coerce').astype('Int64')

    out = x[SCHEMA].copy()
    log_action('write', OUTPUT_PATH, 'write held-out harmonized CSV')
    out.to_csv(OUTPUT_PATH, index=False)


if __name__ == '__main__':
    main()
