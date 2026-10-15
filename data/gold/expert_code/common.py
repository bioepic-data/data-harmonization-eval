"""
Common library for soil moisture data harmonization.

Contains:
- Context class (shared read-only state)
- Helper functions (date parsing, coordinate conversion, etc.)
- Location deduplication logic (Union-Find algorithm)
- Output writer

This module is imported by all dataset_XX.py modules.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from itertools import combinations

import numpy as np
import pandas as pd
from pyproj import Transformer


# =============================================================
# Configuration and Paths
# =============================================================

# Default paths (relative to this file's parent)
PROJECT_ROOT = Path(__file__).parent.parent.parent
DEFAULT_BASE_DIR = PROJECT_ROOT / "data" / "intermediate" / "ess-dive_wfsfa_soil_datasets"
DEFAULT_OUT_DIR = PROJECT_ROOT / "data" / "processed" / "harmonized_output_local"
DEFAULT_MAPPING_JSON = PROJECT_ROOT / "data" / "processed" / "harmonized_soil_moisture_data" / "sm_data_harmonization_mapping.json"

# Reference dataset index (used for lookups)
REF_IDX = 0


@dataclass
class DatasetResult:
    """What each dataset's harmonize function returns."""
    dataset_id: str
    harmonized_data: pd.DataFrame
    location_data: pd.DataFrame


@dataclass
class Context:
    """Shared read-only state passed to all dataset harmonizers."""
    map_json: list
    base_dir: Path = DEFAULT_BASE_DIR
    out_dir: Path = DEFAULT_OUT_DIR
    ref_idx: int = REF_IDX

    @classmethod
    def load(cls, mapping_path: Path, base_dir: Path):
        """Load context from mapping JSON and base directory."""
        with open(mapping_path, "r", encoding="utf-8") as f:
            map_json = json.load(f)
        return cls(map_json=map_json, base_dir=Path(base_dir))

    def dsid(self, idx: int) -> str:
        """Get dataset identifier for index."""
        return self.map_json[idx]["dataset_identifier"]

    def ds_path(self, idx: int) -> Path:
        """Get path to dataset directory."""
        return self.base_dir / self.dsid(idx)

    def read_ds_csv(self, idx: int, filename: str, encoding='utf-8', errors='ignore', **kwargs) -> pd.DataFrame:
        """Read a CSV file from dataset directory."""
        return pd.read_csv(self.ds_path(idx) / filename, encoding=encoding, **kwargs)


# =============================================================
# Helper Functions (verbatim from monolith)
# =============================================================

def as_list(x):
    """Convert to list if not already."""
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def parse_local_to_utc(series: pd.Series, fmt: str | None, tz: str) -> pd.Series:
    """Parse datetime series from local time to UTC."""
    dt = pd.to_datetime(series, format=fmt, errors="coerce")
    dt = dt.dt.tz_localize(tz, ambiguous="NaT", nonexistent="shift_forward")
    return dt.dt.tz_convert("UTC")


def utm32613_to_latlon(df: pd.DataFrame, e_col: str, n_col: str) -> pd.DataFrame:
    """Convert UTM Zone 13N coordinates to lat/lon."""
    tr = Transformer.from_crs("EPSG:32613", "EPSG:4326", always_xy=True)
    e = pd.to_numeric(df[e_col], errors="coerce").values
    n = pd.to_numeric(df[n_col], errors="coerce").values
    lon, lat = tr.transform(e, n)
    out = df.copy()
    out["longitude"] = lon
    out["latitude"] = lat
    return out


def ensure_harmonized_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure all harmonized columns are present."""
    cols = [
        "datetime_UTC",
        "site_id",
        "depth_m",
        "replicate",
        "is_timeseries",
        "volumetric_water_content_m3_m3",
        "gravimetric_water_content_gH2O_gs",
        "water_potential_kPa",
    ]
    for c in cols:
        if c not in df.columns:
            df[c] = np.nan
    return df[cols]


def add_loc_qc(df: pd.DataFrame) -> pd.DataFrame:
    """Add QC flag for missing location data."""
    if "qc_flag" not in df.columns:
        df["qc_flag"] = np.where(
            df["latitude"].isna() | df["longitude"].isna(), "g2", None
        )
    return df


# =============================================================
# Location Deduplication (verbatim from monolith lines 1097-1258)
# =============================================================

def harmonize_locations(loc_data_list: list[pd.DataFrame]) -> pd.DataFrame:
    """
    Deduplicate and harmonize location data across datasets.

    Uses Union-Find algorithm to group sites that are:
    - Within 5 meters of each other (likely same footprint)
    - Have identical site_id across datasets

    Returns DataFrame with harmonized_location_uuid and centroid coordinates.
    """
    # Concat location data from all datasets
    loc_df = pd.concat(loc_data_list, ignore_index=True)
    loc_df['latitude'] = pd.to_numeric(loc_df['latitude'], errors='coerce')
    loc_df['longitude'] = pd.to_numeric(loc_df['longitude'], errors='coerce')

    # Set thresholds and toggle site_id matching
    coord_match_meters_strict = 5  # highly likely same footprint
    use_cross_dataset_site_id = True

    # Function to normalize names for comparison
    def normalize_name(x) -> str:
        if pd.isna(x):
            return ""
        x = str(x).lower()
        x = re.sub(r"[^a-z0-9]+", "", x)
        return x.strip()

    # Function to find safe distance between sites using Haversine formula
    def safe_dist_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
        """Calculate distance in meters between two lat/lon points using Haversine formula"""
        if any(pd.isna([lon1, lat1, lon2, lat2])):
            return np.inf

        # Haversine formula
        R = 6371000  # Earth radius in meters
        phi1 = np.radians(lat1)
        phi2 = np.radians(lat2)
        delta_phi = np.radians(lat2 - lat1)
        delta_lambda = np.radians(lon2 - lon1)

        a = np.sin(delta_phi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(delta_lambda / 2) ** 2
        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

        return R * c

    # Add site_name column (equivalent to site_id)
    loc_df['site_name'] = loc_df['site_id']

    # Prepare location dataframe
    loc_df = loc_df.reset_index(drop=True)
    loc_df['row_id'] = loc_df.index
    loc_df['site_id'] = loc_df['site_id'].astype(str)
    loc_df['source_dataset_id'] = loc_df['source_dataset_id'].astype(str)
    loc_df['site_name_norm'] = loc_df['site_name'].apply(normalize_name)
    loc_df['has_coords'] = loc_df['latitude'].notna() & loc_df['longitude'].notna()

    n = len(loc_df)
    if n == 0:
        raise ValueError("No rows in location file.")

    # Build pairwise links
    def is_match_pair(i: int, j: int, df: pd.DataFrame) -> bool:
        """Check if two rows should be considered the same location"""
        a = df.iloc[i]
        b = df.iloc[j]

        # Strong coordinate match
        d_m = safe_dist_m(a['longitude'], a['latitude'], b['longitude'], b['latitude'])
        if np.isfinite(d_m) and d_m <= coord_match_meters_strict:
            return True

        # Same site_id across different datasets
        if use_cross_dataset_site_id:
            same_site_id = (
                pd.notna(a['site_id']) and pd.notna(b['site_id']) and
                str(a['site_id']) != "" and str(b['site_id']) != "" and
                a['site_id'] == b['site_id']
            )
            if same_site_id:
                return True

        return False

    # Find all matching pairs using Union-Find algorithm
    class UnionFind:
        def __init__(self, n):
            self.parent = list(range(n))
            self.rank = [0] * n

        def find(self, x):
            if self.parent[x] != x:
                self.parent[x] = self.find(self.parent[x])
            return self.parent[x]

        def union(self, x, y):
            px, py = self.find(x), self.find(y)
            if px == py:
                return
            if self.rank[px] < self.rank[py]:
                px, py = py, px
            self.parent[py] = px
            if self.rank[px] == self.rank[py]:
                self.rank[px] += 1

    uf = UnionFind(n)

    # Check all pairs and union matching locations
    for i, j in combinations(range(n), 2):
        if is_match_pair(i, j, loc_df):
            uf.union(i, j)

    # Assign component IDs
    comp_map = {}
    next_comp_id = 0
    for i in range(n):
        root = uf.find(i)
        if root not in comp_map:
            comp_map[root] = next_comp_id
            next_comp_id += 1

    loc_df['location_component_id'] = [comp_map[uf.find(i)] for i in range(n)]

    # Assign stable UUID per component
    comp_ids = sorted(loc_df['location_component_id'].unique())
    uuid_map = pd.DataFrame({
        'location_component_id': comp_ids,
        'harmonized_location_uuid': [str(uuid.uuid4()) for _ in comp_ids]
    })

    loc_df = loc_df.merge(uuid_map, on='location_component_id', how='left')

    # Optional canonical fields per UUID (centroid + representative name)
    canon = loc_df.groupby('harmonized_location_uuid').agg(
        latitude_harmonized=('latitude', lambda x: np.nan if x.isna().all() else x.mean()),
        longitude_harmonized=('longitude', lambda x: np.nan if x.isna().all() else x.mean()),
        n_records_in_uuid=('row_id', 'count'),
        n_datasets_in_uuid=('source_dataset_id', 'nunique')
    ).reset_index()

    # Join all together
    loc_df = loc_df.merge(canon, on='harmonized_location_uuid', how='left')
    loc_df = loc_df.drop(columns=['site_name', 'site_name_norm', 'has_coords', 'row_id', 'location_component_id'])
    loc_df = loc_df.sort_values(['source_dataset_id', 'site_id', 'harmonized_location_uuid']).reset_index(drop=True)

    # Quick QA summary
    qa = loc_df.groupby('harmonized_location_uuid').size().reset_index(name='n')
    qa = qa.sort_values('n', ascending=False)
    qa['flag_multi'] = qa['n'] > 1

    print(f"UUID groups with >1 member: {qa['flag_multi'].sum()} / {len(qa)}")

    return loc_df


# =============================================================
# Output Writer
# =============================================================

def write_outputs(results: list[DatasetResult], loc_df: pd.DataFrame, out_dir: Path):
    """Write harmonized data and location files."""
    out_dir.mkdir(parents=True, exist_ok=True)

    # Write per-dataset files
    for result in results:
        df_out = result.harmonized_data.copy()

        # Sort for consistency across files
        df_out = df_out.sort_values(by=["datetime_UTC", "site_id", "depth_m", "replicate"])

        # Write to file
        out_file = out_dir / f"{result.dataset_id}_harmonized.csv"
        df_out.to_csv(out_file, index=False)
        print(f"Wrote {result.dataset_id}_harmonized.csv")

    # Write location file
    loc_df.to_csv(out_dir / "location_data_harmonized_with_uuid.csv", index=False)
    print("Wrote location_data_harmonized_with_uuid.csv")
    print(f"\nAll outputs written to: {out_dir}")
