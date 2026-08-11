#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import re
import numpy as np
import pandas as pd

FOLD = Path('/scratch/jmc/data-harmonization-eval/.runs/fold-01-holdout-1-2-3-6-16-27')
LOG = FOLD / 'AGENT_ACTION_LOG.md'
OUT = FOLD / 'agent_outputs'
RAW = Path('/h/jmc/ess-dive_wfsfa_soil_datasets')
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
IDS = {
    1: 'ess-dive-beca0be9bb38ece-20250516T122010234',
    2: 'ess-dive-9fd65df885a8e87-20250715T064942543',
    3: 'ess-dive-4c1829de1b8a2ec-20260220T045039633',
    6: 'ess-dive-18e91eb74405882-20241017T173226640',
    16: 'ess-dive-b3d271f19a94e8d-20260114T204512119',
    27: 'ess-dive-c37aaf9ed6d4c0d-20230504T205923265966',
}

def log(action: str, subject: Path | str, reason: str) -> None:
    with LOG.open('a', encoding='utf-8') as f:
        f.write(f"\n- timestamp: 2026-06-30T00:00:00-07:00\n  action: {action}\n  subject: {subject}\n  reason: {reason}\n")

def read_csv_logged(path: Path, **kwargs) -> pd.DataFrame:
    log('read_file', path, 'harmonization script reading allowed held-out raw file')
    return pd.read_csv(path, **kwargs)

def write_csv_logged(df: pd.DataFrame, path: Path, reason: str) -> None:
    log('write_file', path, reason)
    df.to_csv(path, index=False)

def parse_denver(series: pd.Series, fmt: str | None = None) -> pd.Series:
    dt = pd.to_datetime(series, format=fmt, errors='coerce')
    return dt.dt.tz_localize('America/Denver', ambiguous='NaT', nonexistent='shift_forward').dt.tz_convert('UTC')

def parse_utc(series: pd.Series, fmt: str | None = None) -> pd.Series:
    return pd.to_datetime(series, format=fmt, errors='coerce', utc=True)

def parse_fixed_offset_to_utc(series: pd.Series, offset_hours: float) -> pd.Series:
    dt = pd.to_datetime(series, errors='coerce')
    return (dt - pd.to_timedelta(offset_hours, unit='h')).dt.tz_localize('UTC')

def clean_numeric(s: pd.Series) -> pd.Series:
    x = pd.to_numeric(s, errors='coerce')
    return x.mask(np.isclose(x, -9999.0))

def ensure(df: pd.DataFrame) -> pd.DataFrame:
    for c in SCHEMA:
        if c not in df.columns:
            df[c] = np.nan
    out = df[SCHEMA].copy()
    out['site_id'] = out['site_id'].astype(str)
    out['depth_m'] = pd.to_numeric(out['depth_m'], errors='coerce')
    out['replicate'] = pd.to_numeric(out['replicate'], errors='coerce')
    out['interval_min'] = pd.to_numeric(out['interval_min'], errors='coerce')
    for c in ['volumetric_water_content_m3_m3','gravimetric_water_content_gH2O_gs','water_potential_kPa']:
        out[c] = clean_numeric(out[c])
    return out

def add_intervals(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(['site_id','depth_m','replicate','datetime_UTC']).copy()
    df['interval_min'] = df.groupby(['site_id','depth_m','replicate'], dropna=False)['datetime_UTC'].diff().dt.total_seconds() / 60.0
    return df

def finalize_long(rows: list[pd.DataFrame]) -> pd.DataFrame:
    x = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=SCHEMA)
    # Combine variable-specific rows where VWC and water potential share the same key.
    keys = ['datetime_UTC','site_id','depth_m','replicate','is_timeseries']
    for v in ['volumetric_water_content_m3_m3','gravimetric_water_content_gH2O_gs','water_potential_kPa']:
        if v not in x.columns:
            x[v] = np.nan
    x = x.groupby(keys, dropna=False, as_index=False).agg({
        'volumetric_water_content_m3_m3': 'first',
        'gravimetric_water_content_gH2O_gs': 'first',
        'water_potential_kPa': 'first',
    })
    x = add_intervals(x)
    return ensure(x)

def ds1() -> pd.DataFrame:
    ds = IDS[1]
    files = ['ER_SMN10.csv','ER_SMN1B.csv','ER_SMN30.csv','ER_SMN3B.csv','ER_SMN4B.csv','ER_SMN5B.csv','ER_SMS1.csv','ER_SMS2.csv','ER_SMS3.csv']
    rows = []
    for rel in files:
        df = read_csv_logged(RAW/ds/rel)
        site = Path(rel).stem
        dt = parse_denver(df['Time'])
        for col in df.columns:
            m = re.match(r'm3_m3_(?:Water_Content|VWC)(?:_(\d+))?_at_(\d+)cm$', col)
            if m:
                rep = int(m.group(1) or 1)
                depth = int(m.group(2))/100.0
                rows.append(pd.DataFrame({'datetime_UTC': dt, 'site_id': site, 'depth_m': depth, 'replicate': rep, 'is_timeseries': True, 'volumetric_water_content_m3_m3': clean_numeric(df[col])}))
            m = re.match(r'kPa_Potential(?:_(\d+))?_at_(\d+)cm$', col)
            if m:
                rep = int(m.group(1) or 1)
                depth = int(m.group(2))/100.0
                rows.append(pd.DataFrame({'datetime_UTC': dt, 'site_id': site, 'depth_m': depth, 'replicate': rep, 'is_timeseries': True, 'water_potential_kPa': clean_numeric(df[col])}))
    return finalize_long(rows)

def ds2() -> pd.DataFrame:
    ds = IDS[2]
    files = ['ER_SMN1.csv','ER_SMN3.csv','ER_SMN4.csv','ER_SMN5.csv']
    rows = []
    for rel in files:
        df = read_csv_logged(RAW/ds/rel)
        site = Path(rel).stem.replace('_', '-')
        dt = parse_denver(df['DateTime'])
        for col in df.columns:
            m = re.match(r'Moisture_m3/m3_(\d+)cm$', col)
            if m:
                rows.append(pd.DataFrame({'datetime_UTC': dt, 'site_id': site, 'depth_m': int(m.group(1))/100.0, 'replicate': 1, 'is_timeseries': True, 'volumetric_water_content_m3_m3': clean_numeric(df[col])}))
    return finalize_long(rows)

def ds3() -> pd.DataFrame:
    ds = IDS[3]
    df = read_csv_logged(RAW/ds/'Soil_water_potential.csv')
    dt = parse_denver(df['TIMESTAMP'])
    rows = []
    for col in df.columns:
        m = re.match(r'(SD\d+)-(\d+)cm(?:_sagebrush_rhizo)?_MP(?:_(\d+))?(?:_Avg)?$', col)
        if not m:
            continue
        site, depth_cm, rep = m.group(1), int(m.group(2)), int(m.group(3) or 1)
        rows.append(pd.DataFrame({'datetime_UTC': dt, 'site_id': site, 'depth_m': depth_cm/100.0, 'replicate': rep, 'is_timeseries': True, 'water_potential_kPa': clean_numeric(df[col])}))
    return finalize_long(rows)

def ds6() -> pd.DataFrame:
    ds = IDS[6]
    df = read_csv_logged(RAW/ds/'Snodgrass_ESS.csv', skiprows=[1,2])
    dt = parse_utc(df['TIMESTAMP'])
    rows = []
    for col in ['VWC_50cm','VWC_15cm','VWC_5cm']:
        rows.append(pd.DataFrame({'datetime_UTC': dt, 'site_id': df['site'], 'depth_m': int(re.search(r'(\d+)cm', col).group(1))/100.0, 'replicate': 1, 'is_timeseries': True, 'volumetric_water_content_m3_m3': clean_numeric(df[col])}))
    return finalize_long(rows)

def ds16() -> pd.DataFrame:
    ds = IDS[16]
    root = RAW/ds/'WFSFA_EHG_SensorTowers_Wu_et_al'
    meta = read_csv_logged(root/'metadata_instrument_v1-1.csv')
    meta = meta[meta['VARIABLE'].astype(str).str.match(r'SW[CP]_')].copy()
    meta['depth_m'] = pd.to_numeric(meta['HEIGHT'], errors='coerce').abs()
    depth_map = {(r.SITE_ID, r.VARIABLE): r.depth_m for r in meta.itertuples(index=False)}
    files = ['data_ER-PHS1_v1-1.csv','data_ER-PHS2_v1-1.csv','data_ER-PHS3_v1-1.csv','data_ER-PHS4_v1-1.csv','data_SG-EHS5_v1-1.csv','data_SG-EHS6_v1-1.csv','data_SG-EHS7_v1-1.csv','data_SG-EHS8_v1-1.csv']
    rows = []
    for rel in files:
        site = re.match(r'data_(.+)_v1-1\.csv$', rel).group(1)
        df = read_csv_logged(root/rel)
        dt = parse_fixed_offset_to_utc(df['TIMESTAMP_START'], -7)
        for col in df.columns:
            if re.match(r'SWC_', col):
                rows.append(pd.DataFrame({'datetime_UTC': dt, 'site_id': site, 'depth_m': depth_map.get((site,col), np.nan), 'replicate': 1, 'is_timeseries': True, 'volumetric_water_content_m3_m3': clean_numeric(df[col])/100.0}))
            elif re.match(r'SWP_', col):
                rows.append(pd.DataFrame({'datetime_UTC': dt, 'site_id': site, 'depth_m': depth_map.get((site,col), np.nan), 'replicate': 1, 'is_timeseries': True, 'water_potential_kPa': clean_numeric(df[col])}))
    return finalize_long(rows)

def ds27() -> pd.DataFrame:
    ds = IDS[27]
    files = {
        'ER-PHS1': 'ER-PHS1_Field dataset_2019_Oct11 to_2020_Mar20.csv',
        'ER-PHS2': 'ER-PHS2_Field Dataset_2019_Oct11 to 2020_Apr03.csv',
        'ER-PHS3': 'ER-PHS3_Field dataset_2019_Oct12.csv',
        'ER-PHS4': 'ER-PHS4_Field Dataset_2019_Oct14 to 2020_Apr03.csv',
    }
    swc_depths = {
        'ER-PHS1': {'S1':0.10,'S2':0.30,'S3':0.60,'S4':1.15},
        'ER-PHS2': {'S1':0.10,'S2':0.30,'S3':0.60,'S4':1.15},
        'ER-PHS3': {'S1':0.10,'S2':0.30,'S3':0.60,'S4':1.15},
        'ER-PHS4': {'S1':0.10,'S2':0.30,'S3':0.60,'S4':1.06},
    }
    rows = []
    for site, rel in files.items():
        df = read_csv_logged(RAW/ds/rel)
        dt = parse_denver(df['Time'])
        for sensor in ['S1','S2','S3','S4']:
            col = f'{sensor}_wc_(m3/m3)'
            rows.append(pd.DataFrame({'datetime_UTC': dt, 'site_id': site, 'depth_m': swc_depths[site][sensor], 'replicate': 1, 'is_timeseries': True, 'volumetric_water_content_m3_m3': clean_numeric(df[col])}))
        rows.append(pd.DataFrame({'datetime_UTC': dt, 'site_id': site, 'depth_m': 0.30, 'replicate': 1, 'is_timeseries': True, 'water_potential_kPa': clean_numeric(df['S5_wp_(kPa)'])}))
    return finalize_long(rows)

def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    outputs = {1: ds1(), 2: ds2(), 3: ds3(), 6: ds6(), 16: ds16(), 27: ds27()}
    all_rows = []
    for idx, df in outputs.items():
        df = ensure(df)
        outputs[idx] = df
        per_path = OUT / f'heldout_dataset_{idx:02d}_harmonized.csv'
        write_csv_logged(df, per_path, f'write optional per-dataset harmonized CSV for dataset {idx}')
        x = df.copy()
        x.insert(0, 'dataset_index', idx)
        x.insert(1, 'dataset_identifier', IDS[idx])
        all_rows.append(x)
    combined = pd.concat(all_rows, ignore_index=True)
    write_csv_logged(combined, OUT/'heldout_harmonized.csv', 'write required combined held-out harmonized CSV')
    summary = pd.DataFrame([
        {'dataset_index': idx, 'dataset_identifier': IDS[idx], 'rows': len(df)}
        for idx, df in outputs.items()
    ])
    write_csv_logged(summary, OUT/'heldout_row_counts.csv', 'write row count summary for verification')
    print(summary.to_string(index=False))
    print('combined_rows', len(combined))
    print('combined_columns', list(combined.columns))

if __name__ == '__main__':
    main()
