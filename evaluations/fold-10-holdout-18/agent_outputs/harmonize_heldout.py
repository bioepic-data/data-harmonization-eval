from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

RAW_DIR = Path('/h/jmc/ess-dive_wfsfa_soil_datasets/ess-dive-b924878d23c9dd7-20250214T163427929')
RAW_FILE = '2017_East_River_Pumphouse_Soil_Water_Content_and_pH__1_.csv'
OUT_DIR = Path('/scratch/jmc/data-harmonization-eval/.runs/fold-10-holdout-18/agent_outputs')
COLS = [
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

def site_id_from_row(row: pd.Series) -> str:
    parts = [
        row.get('Location'),
        row.get('Field_Site'),
        row.get('Block'),
        row.get('Plot'),
        f"rep{row.get('Replicate')}",
    ]
    topo = row.get('Topographic_Position')
    if pd.notna(topo) and str(topo).strip():
        parts.append(topo)
    cleaned = []
    for part in parts:
        s = str(part).strip().replace(' ', '_').replace('/', '_')
        cleaned.append(s)
    return '|'.join(cleaned)

def depth_to_m(value: object) -> float:
    return {
        '0-5 cm': 0.025,
        '5-15 cm': 0.10,
        '15-May': 0.10,
        '15 cm +': 0.15,
    }.get(str(value).strip(), np.nan)

def harmonize() -> pd.DataFrame:
    df = pd.read_csv(RAW_DIR / RAW_FILE, encoding='latin1')
    out = pd.DataFrame()
    dt = pd.to_datetime(df['Date_Collected'], format='%m/%d/%Y', errors='coerce')
    dt = dt.dt.tz_localize('America/Denver', ambiguous='NaT', nonexistent='shift_forward').dt.tz_convert('UTC')
    out['datetime_UTC'] = dt.dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    out['site_id'] = df.apply(site_id_from_row, axis=1)
    out['depth_m'] = df['Depth_Increment'].map(depth_to_m).astype(float)
    out['replicate'] = pd.to_numeric(df['Replicate'], errors='coerce')
    out['is_timeseries'] = False
    out['interval_min'] = np.nan
    out['volumetric_water_content_m3_m3'] = np.nan
    out['gravimetric_water_content_gH2O_gs'] = pd.to_numeric(
        df['Soil Water Content (g H2O per gram  soil)'], errors='coerce'
    )
    out['water_potential_kPa'] = np.nan
    out = out[out['gravimetric_water_content_gH2O_gs'].notna()].copy()
    return out[COLS]

if __name__ == '__main__':
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    harmonize().to_csv(OUT_DIR / 'heldout_harmonized.csv', index=False)
