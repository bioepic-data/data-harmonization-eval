from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import math

FOLD_DIR = Path('/scratch/jmc/data-harmonization-eval/.runs/fold-02-holdout-15-26')
OUT_DIR = FOLD_DIR / 'agent_outputs'
LOG_PATH = FOLD_DIR / 'AGENT_ACTION_LOG.md'
RAW_BASE = Path('/h/jmc/ess-dive_wfsfa_soil_datasets')

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

DATASETS = {
    15: {
        'package_id': 'ess-dive-987726ef1235abc-20230504T210342929747',
        'doi': 'doi:10.15485/1648526',
        'title': 'Time-domain reflectometer survey across the East River Watershed, Colorado',
        'file': 'TDR_survey_ER_20190701.csv',
        'nominal_date': '2019-07-02',
        'timezone': 'America/Denver',
        'depth_m': 0.25,
        'description': 'Near-surface point measurements of soil temperature, volumetric water content, and electrical conductivity using TDR at 25 cm depth across East River hillslopes in early July 2019.',
        'temporal_coverage': {'startDate': '2019-07-02', 'endDate': '2019-07-07'},
    },
    26: {
        'package_id': 'ess-dive-f782da867133296-20230504T211008637996',
        'doi': 'doi:10.15485/1671826',
        'title': 'Soil bulk density and texture data collected during field survey associated with NEON AOP survey, East River, CO 2018',
        'file': 'ER18_soil_physical.csv',
        'timezone': 'America/Denver',
        'description': 'Soil cores collected from surface and subsurface depths for bulk density, volumetric water content, and texture across East River and nearby watersheds in summer 2018.',
        'temporal_coverage': {'startDate': '2018-06-12', 'endDate': '2018-10-15'},
    },
}


def log_action(action: str, subject: str, reason: str) -> None:
    ts = datetime.now(timezone.utc).astimezone().isoformat()
    with LOG_PATH.open('a', encoding='utf-8') as fh:
        fh.write(f'- {ts} | action={action} | subject={subject} | reason={reason}\n')


def raw_path(idx: int) -> Path:
    meta = DATASETS[idx]
    return RAW_BASE / meta['package_id'] / meta['file']


def read_raw_csv(idx: int) -> pd.DataFrame:
    path = raw_path(idx)
    log_action('read', str(path), f'read held-out dataset {idx} raw CSV for harmonization')
    return pd.read_csv(path)


def parse_local_date_to_utc(series: pd.Series, fmt: str | None = None, tz: str = 'America/Denver') -> pd.Series:
    dt = pd.to_datetime(series, format=fmt, errors='coerce')
    dt = dt.dt.tz_localize(tz, ambiguous='NaT', nonexistent='shift_forward')
    return dt.dt.tz_convert('UTC')


def iso_utc(series: pd.Series) -> pd.Series:
    return series.dt.strftime('%Y-%m-%dT%H:%M:%SZ')



def utm13n_to_latlon(easting: pd.Series, northing: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    # WGS84 inverse Transverse Mercator for UTM zone 13N.
    a = 6378137.0
    ecc_sq = 0.0066943799901413165
    k0 = 0.9996
    ecc_prime_sq = ecc_sq / (1.0 - ecc_sq)
    e1 = (1.0 - math.sqrt(1.0 - ecc_sq)) / (1.0 + math.sqrt(1.0 - ecc_sq))
    x = pd.to_numeric(easting, errors='coerce').to_numpy(dtype=float) - 500000.0
    y = pd.to_numeric(northing, errors='coerce').to_numpy(dtype=float)
    long_origin = -105.0
    m = y / k0
    mu = m / (a * (1.0 - ecc_sq / 4.0 - 3.0 * ecc_sq**2 / 64.0 - 5.0 * ecc_sq**3 / 256.0))
    phi1 = (
        mu
        + (3.0 * e1 / 2.0 - 27.0 * e1**3 / 32.0) * np.sin(2.0 * mu)
        + (21.0 * e1**2 / 16.0 - 55.0 * e1**4 / 32.0) * np.sin(4.0 * mu)
        + (151.0 * e1**3 / 96.0) * np.sin(6.0 * mu)
    )
    n1 = a / np.sqrt(1.0 - ecc_sq * np.sin(phi1) ** 2)
    t1 = np.tan(phi1) ** 2
    c1 = ecc_prime_sq * np.cos(phi1) ** 2
    r1 = a * (1.0 - ecc_sq) / ((1.0 - ecc_sq * np.sin(phi1) ** 2) ** 1.5)
    d = x / (n1 * k0)
    lat = phi1 - (n1 * np.tan(phi1) / r1) * (
        d**2 / 2.0
        - (5.0 + 3.0 * t1 + 10.0 * c1 - 4.0 * c1**2 - 9.0 * ecc_prime_sq) * d**4 / 24.0
        + (61.0 + 90.0 * t1 + 298.0 * c1 + 45.0 * t1**2 - 252.0 * ecc_prime_sq - 3.0 * c1**2) * d**6 / 720.0
    )
    lon = np.deg2rad(long_origin) + (
        d
        - (1.0 + 2.0 * t1 + c1) * d**3 / 6.0
        + (5.0 - 2.0 * c1 + 28.0 * t1 - 3.0 * c1**2 + 8.0 * ecc_prime_sq + 24.0 * t1**2) * d**5 / 120.0
    ) / np.cos(phi1)
    lat = np.rad2deg(lat)
    lon = np.rad2deg(lon)
    lat[np.isnan(x) | np.isnan(y)] = np.nan
    lon[np.isnan(x) | np.isnan(y)] = np.nan
    return lon, lat

def ensure_target_columns(df: pd.DataFrame) -> pd.DataFrame:
    for col in TARGET_COLUMNS:
        if col not in df.columns:
            df[col] = np.nan
    return df[TARGET_COLUMNS].copy()


def harmonize_dataset_15() -> tuple[pd.DataFrame, pd.DataFrame]:
    ddf = read_raw_csv(15)
    meta = DATASETS[15]
    base = ddf.copy()
    base['datetime_UTC'] = iso_utc(parse_local_date_to_utc(pd.Series([meta['nominal_date']] * len(base)), '%Y-%m-%d', meta['timezone']))
    base['site_id'] = base['GPS_id'].astype(str)
    base['depth_m'] = float(meta['depth_m'])
    base['is_timeseries'] = False
    base['interval_min'] = np.nan
    base['gravimetric_water_content_gH2O_gs'] = np.nan
    base['water_potential_kPa'] = np.nan

    long = base.melt(
        id_vars=['datetime_UTC', 'site_id', 'depth_m', 'is_timeseries', 'interval_min', 'gravimetric_water_content_gH2O_gs', 'water_potential_kPa'],
        value_vars=['TDR_SM(VWC%)_1', 'TDR_SM(VWC%)_2', 'TDR_SM(VWC%)_3'],
        var_name='source_variable',
        value_name='volumetric_water_content_m3_m3',
    )
    long['replicate'] = pd.to_numeric(long['source_variable'].str.extract(r'_(\d+)$')[0], errors='coerce')
    long['volumetric_water_content_m3_m3'] = pd.to_numeric(long['volumetric_water_content_m3_m3'], errors='coerce') / 100.0
    long = long[long['volumetric_water_content_m3_m3'].notna()].copy()
    harmonized = ensure_target_columns(long)

    loc_src = ddf[['GPS_id', 'Site', 'Easting_m', 'Northing_m', 'Elevation_m']].copy()
    lon, lat = utm13n_to_latlon(loc_src['Easting_m'], loc_src['Northing_m'])
    loc_src['site_id'] = loc_src['GPS_id'].astype(str)
    loc_src['latitude'] = lat
    loc_src['longitude'] = lon
    loc_src['source_dataset_id'] = meta['package_id']
    loc_src['qc_flag'] = pd.Series(np.nan, index=loc_src.index, dtype=object)
    loc_src.loc[loc_src['latitude'].isna() | loc_src['longitude'].isna(), 'qc_flag'] = 'g2'
    loc = loc_src[['site_id', 'Site', 'Easting_m', 'Northing_m', 'Elevation_m', 'latitude', 'longitude', 'source_dataset_id', 'qc_flag']].drop_duplicates()
    return harmonized, loc


def harmonize_dataset_26() -> tuple[pd.DataFrame, pd.DataFrame]:
    ddf = read_raw_csv(26)
    meta = DATASETS[26]
    x = ddf.copy()
    x['datetime_UTC'] = iso_utc(parse_local_date_to_utc(x['Collection date'], '%m/%d/%y', meta['timezone']))
    x['site_id'] = x['SampleSiteCode'].astype(str)
    top = pd.to_numeric(x['Top sample depth_cm'], errors='coerce')
    bottom = pd.to_numeric(x['Bottom sample depth_cm'], errors='coerce')
    x['depth_m'] = ((top + bottom) / 2.0) / 100.0
    x['replicate'] = np.nan
    x['is_timeseries'] = False
    x['interval_min'] = np.nan
    x['volumetric_water_content_m3_m3'] = pd.to_numeric(x['water content %vol'], errors='coerce') / 100.0
    wet = pd.to_numeric(x['Soil Wet Weight (g)'], errors='coerce')
    dry = pd.to_numeric(x['Soil Dry Weight (g)'], errors='coerce')
    x['gravimetric_water_content_gH2O_gs'] = (wet - dry) / dry
    x.loc[(dry <= 0) | wet.isna() | dry.isna(), 'gravimetric_water_content_gH2O_gs'] = np.nan
    x['water_potential_kPa'] = np.nan
    x = x[x['volumetric_water_content_m3_m3'].notna() | x['gravimetric_water_content_gH2O_gs'].notna()].copy()
    harmonized = ensure_target_columns(x)
    loc = pd.DataFrame({
        'site_id': sorted(ddf['SampleSiteCode'].dropna().astype(str).unique()),
        'latitude': np.nan,
        'longitude': np.nan,
        'source_dataset_id': meta['package_id'],
        'qc_flag': 'g2',
    })
    return harmonized, loc


def build_mapping() -> list[dict]:
    return [
        {
            'index': 15,
            'dataset_identifier': DATASETS[15]['package_id'],
            'doi': DATASETS[15]['doi'],
            'archive_repository': 'ESS-DIVE',
            'data_payload_files': [DATASETS[15]['file']],
            'location_metadata_files': [DATASETS[15]['file']],
            'sensor_metadata_files': None,
            'harmonization_mappings': {
                'datetime': {'pattern_1': {'source_pattern': 'package temporalCoverage startDate; filename date TDR_survey_ER_20190701.csv', 'source_files': [DATASETS[15]['file']], 'destination_variable': 'datetime_UTC', 'transformation': 'Assign nominal survey date from package temporal coverage start (2019-07-02) and convert local America/Denver date to UTC.', 'unit_conversion': None}},
                'site_id': {'pattern_1': {'source_pattern': 'GPS_id', 'source_files': [DATASETS[15]['file']], 'destination_variable': 'site_id', 'transformation': 'Use GPS_id as the point-level site identifier because each row has separate coordinates.', 'unit_conversion': None}},
                'depth': {'pattern_1': {'source_pattern': 'package description reports TDR at 25 cm', 'source_files': [DATASETS[15]['file']], 'destination_variable': 'depth_m', 'transformation': 'Assign constant sampling depth 0.25 m.', 'unit_conversion': 'Divide reported 25 cm depth by 100 to convert to m.'}},
                'replicate': {'pattern_1': {'source_pattern': 'TDR_SM(VWC%)_1, TDR_SM(VWC%)_2, TDR_SM(VWC%)_3', 'source_files': [DATASETS[15]['file']], 'destination_variable': 'replicate', 'transformation': 'Parse trailing integer from repeated TDR VWC columns after wide-to-long reshape.', 'unit_conversion': None}},
                'volumetric_water_content': {'pattern_1': {'source_pattern': 'TDR_SM(VWC%)_i', 'source_files': [DATASETS[15]['file']], 'destination_variable': 'volumetric_water_content_m3_m3', 'transformation': 'Reshape replicate VWC percent columns to long rows and drop missing readings.', 'unit_conversion': 'Divide by 100 to convert percent VWC to m3/m3.'}},
                'latitude': {'pattern_1': {'source_pattern': 'Northing_m', 'source_files': [DATASETS[15]['file']], 'destination_variable': 'latitude', 'transformation': 'Reproject EPSG:32613 northing/easting to WGS84 latitude for location metadata.', 'unit_conversion': 'EPSG:32613 to EPSG:4326.'}},
                'longitude': {'pattern_1': {'source_pattern': 'Easting_m', 'source_files': [DATASETS[15]['file']], 'destination_variable': 'longitude', 'transformation': 'Reproject EPSG:32613 easting/northing to WGS84 longitude for location metadata.', 'unit_conversion': 'EPSG:32613 to EPSG:4326.'}},
            },
        },
        {
            'index': 26,
            'dataset_identifier': DATASETS[26]['package_id'],
            'doi': DATASETS[26]['doi'],
            'archive_repository': 'ESS-DIVE',
            'data_payload_files': [DATASETS[26]['file']],
            'location_metadata_files': None,
            'sensor_metadata_files': None,
            'harmonization_mappings': {
                'datetime': {'pattern_1': {'source_pattern': 'Collection date', 'source_files': [DATASETS[26]['file']], 'destination_variable': 'datetime_UTC', 'transformation': 'Parse collection date as local America/Denver date and convert to UTC.', 'unit_conversion': None}},
                'site_id': {'pattern_1': {'source_pattern': 'SampleSiteCode', 'source_files': [DATASETS[26]['file']], 'destination_variable': 'site_id', 'transformation': 'Direct column mapping.', 'unit_conversion': None}},
                'depth': {'pattern_1': {'source_pattern': 'Top sample depth_cm, Bottom sample depth_cm', 'source_files': [DATASETS[26]['file']], 'destination_variable': 'depth_m', 'transformation': 'Use midpoint of reported depth range.', 'unit_conversion': 'Average top and bottom depths in cm, then divide by 100 to convert to m.'}},
                'volumetric_water_content': {'pattern_1': {'source_pattern': 'water content %vol', 'source_files': [DATASETS[26]['file']], 'destination_variable': 'volumetric_water_content_m3_m3', 'transformation': 'Direct calculated volumetric water-content column from source data; rows without any moisture measure are excluded.', 'unit_conversion': 'Divide by 100 to convert percent volumetric water content to m3/m3.'}},
                'gravimetric_water_content': {'pattern_1': {'source_pattern': 'Soil Wet Weight (g), Soil Dry Weight (g)', 'source_files': [DATASETS[26]['file']], 'destination_variable': 'gravimetric_water_content_gH2O_gs', 'transformation': 'Compute (wet weight - dry weight) / dry weight for rows with both weights.', 'unit_conversion': 'g water per g dry soil from gram weights.'}},
                'latitude': {'pattern_1': {'source_pattern': None, 'source_files': [DATASETS[26]['file']], 'destination_variable': 'latitude', 'transformation': 'No per-site coordinates in payload; package metadata only provides a bounding box, so exact row coordinates are unresolved.', 'unit_conversion': None}},
                'longitude': {'pattern_1': {'source_pattern': None, 'source_files': [DATASETS[26]['file']], 'destination_variable': 'longitude', 'transformation': 'No per-site coordinates in payload; package metadata only provides a bounding box, so exact row coordinates are unresolved.', 'unit_conversion': None}},
            },
        },
    ]


def build_curator_bundle(df15: pd.DataFrame, loc15: pd.DataFrame, df26: pd.DataFrame, loc26: pd.DataFrame) -> dict:
    return {
        'datasets': [
            {
                'package_id': DATASETS[15]['package_id'],
                'doi': DATASETS[15]['doi'],
                'title': DATASETS[15]['title'],
                'curator_decision': 'INCLUDE',
                'exclusion_reason': None,
                'data_payload_files': [{'filename': DATASETS[15]['file'], 'columns': ['GPS_id', 'Sample_id', 'id', 'Site', 'Easting_m', 'Northing_m', 'Elevation_m', 'TDR_T(C)_1', 'TDR_T(C)_2', 'TDR_T(C)_3', 'TDR_SM(VWC%)_1', 'TDR_SM(VWC%)_2', 'TDR_SM(VWC%)_3', 'TDR_EC(mS/m)_1', 'TDR_EC(mS/m)_2', 'TDR_EC(mS/m)_3'], 'row_count_estimate': 101, 'file_size_bytes': raw_path(15).stat().st_size, 'soil_moisture_columns': ['TDR_SM(VWC%)_1', 'TDR_SM(VWC%)_2', 'TDR_SM(VWC%)_3']}],
                'location_metadata_files': [{'filename': DATASETS[15]['file'], 'columns': ['GPS_id', 'Site', 'Easting_m', 'Northing_m', 'Elevation_m']}],
                'sensor_metadata_files': None,
                'readme_content': None,
                'location_resolution': {'source': 'data_payload', 'qc_flag_recommendation': None, 'site_coordinates_preview': loc15[['site_id', 'latitude', 'longitude']].head(10).to_dict(orient='records'), 'site_coordinate_count': int(loc15['site_id'].nunique())},
                'time_series_inference': {'is_timeseries': False, 'interval_min': None, 'reasoning': 'One spatial survey with repeated TDR readings per point; no row-level time sequence.'},
                'experimental_context': {'manipulation_detected': False, 'manipulation_type': None, 'has_control_data': None, 'recommendation': 'include_all'},
                'similar_dataset_reference': {'index': 9, 'reason': 'Discrete VWC survey with UTM coordinates and replicate VWC columns.'},
                'open_questions': ['Row-level dates are absent; the harmonizer assigns package temporalCoverage startDate 2019-07-02 as the nominal survey date.'],
                'harmonized_rows': int(len(df15)),
            },
            {
                'package_id': DATASETS[26]['package_id'],
                'doi': DATASETS[26]['doi'],
                'title': DATASETS[26]['title'],
                'curator_decision': 'INCLUDE',
                'exclusion_reason': None,
                'data_payload_files': [{'filename': DATASETS[26]['file'], 'columns': ['Unnamed: 0', 'SampleSiteCode', 'SampleID', 'Soil Wet Weight (g)', 'Soil Dry Weight (g)', 'Lab #', 'SiteID', 'Whole sample wt, g', '>2mm portion wt, g', 'SAND', 'SILT', 'CLAY', 'IGSN', 'Top sample depth_cm', 'Bottom sample depth_cm', 'Collection date', 'BD_tot g/cm3', '<2mm portion wt, g', 'BD_2mm g/cm3', 'BD_wet g/cm3', 'water content %vol', 'mineral density g/cm3', 'sand density g/cm3', 'silt density g/cm3', 'clay density g/cm3'], 'row_count_estimate': 586, 'file_size_bytes': raw_path(26).stat().st_size, 'soil_moisture_columns': ['water content %vol', 'Soil Wet Weight (g)', 'Soil Dry Weight (g)']}],
                'location_metadata_files': None,
                'sensor_metadata_files': None,
                'readme_content': None,
                'location_resolution': {'source': 'package_metadata_bbox_only', 'qc_flag_recommendation': 'g2', 'site_coordinates': [], 'site_coordinate_count': 0},
                'time_series_inference': {'is_timeseries': False, 'interval_min': None, 'reasoning': 'Discrete soil-core collection dates; no repeated sensor time series per site/depth.'},
                'experimental_context': {'manipulation_detected': False, 'manipulation_type': None, 'has_control_data': None, 'recommendation': 'include_all'},
                'similar_dataset_reference': {'index': 18, 'reason': 'Discrete lab soil-water-content sampling with dated samples and depth ranges.'},
                'open_questions': ['Exact per-site coordinates are not in the payload; package metadata provides only a bounding box.', 'Depth is represented as the midpoint of reported ranges, corresponding to qc_flag d1 in mapping notes.'],
                'harmonized_rows': int(len(df26)),
            },
        ]
    }


def write_json(path: Path, obj: object, reason: str) -> None:
    log_action('write', str(path), reason)
    path.write_text(json.dumps(obj, indent=2) + '\n', encoding='utf-8')


def write_csv(path: Path, df: pd.DataFrame, reason: str) -> None:
    log_action('write', str(path), reason)
    df.to_csv(path, index=False)


def write_text(path: Path, text: str, reason: str) -> None:
    log_action('write', str(path), reason)
    path.write_text(text, encoding='utf-8')


def main() -> None:
    log_action('command', 'harmonize_heldout.py main', 'generate all held-out benchmark outputs')
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df15, loc15 = harmonize_dataset_15()
    df26, loc26 = harmonize_dataset_26()
    heldout = pd.concat([df15, df26], ignore_index=True)

    write_csv(OUT_DIR / 'heldout_harmonized_dataset_15.csv', df15, 'write optional per-dataset harmonized rows for held-out index 15')
    write_csv(OUT_DIR / 'heldout_harmonized_dataset_26.csv', df26, 'write optional per-dataset harmonized rows for held-out index 26')
    write_csv(OUT_DIR / 'heldout_harmonized.csv', heldout, 'write concatenated held-out target-schema harmonized rows')
    write_json(OUT_DIR / 'mapping.json', build_mapping(), 'write held-out mapping entries')
    write_json(OUT_DIR / 'curator_bundle.json', build_curator_bundle(df15, loc15, df26, loc26), 'write curator decisions and structured inputs')

    notes = f'''# Held-out Mapping Notes\n\n## Dataset 15\n\n- Included: direct TDR volumetric water-content measurements.\n- Rows: {len(df15)} long-format VWC readings from 101 survey points and up to three replicate TDR columns.\n- Date handling: the CSV lacks row-level dates; package temporal coverage starts on 2019-07-02, so all rows use 2019-07-02 local midnight converted to UTC.\n- Depth handling: package metadata states the TDR survey was at 25 cm, mapped to depth_m = 0.25.\n- Site handling: GPS_id is used as point-level site_id; coordinates are embedded as EPSG:32613 Easting/Northing in the payload.\n\n## Dataset 26\n\n- Included: soil-core volumetric water content and computable gravimetric water content from wet/dry weights.\n- Rows: {len(df26)} rows with at least one moisture measurement; rows containing only texture/bulk-density fields were excluded from the target moisture table.\n- Depth handling: reported top and bottom sample depths are converted to midpoint depth in meters; this is a depth-range approximation (qc d1 conceptually, but qc_flag is not part of the target CSV schema).\n- Location handling: no per-site coordinates are present in the payload; package metadata has only a bounding box, so exact site coordinates would be g2 if a location table were emitted.\n\n## Output Schema\n\nThe concatenated CSV contains exactly these columns: {', '.join(TARGET_COLUMNS)}.\n'''
    write_text(OUT_DIR / 'mapping_notes.md', notes, 'write harmonization decisions and unresolved assumptions')

    summary = {'dataset_15_rows': int(len(df15)), 'dataset_26_rows': int(len(df26)), 'heldout_rows': int(len(heldout)), 'columns': TARGET_COLUMNS}
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
