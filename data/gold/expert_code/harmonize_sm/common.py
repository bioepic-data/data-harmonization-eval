"""Shared library for the expert soil-moisture harmonization.

This is the ``common`` half of the refactored expert script. It holds
everything the per-dataset modules (``dataset_NN.py``) share:

* :class:`Context` — the loaded mapping JSON plus the dataset-access helpers
  (``dsid`` / ``ds_path`` / ``read_ds_csv``) that used to be module-level
  globals in the monolith.
* the pure transformation helpers (``parse_local_to_utc`` etc.), unchanged.
* :class:`DatasetResult` — what each ``harmonize(ctx)`` returns.
* :func:`harmonize_locations` — the cross-dataset location dedup footer.
* :func:`write_outputs` — the per-dataset + location CSV writer.

The bodies of the helpers and the two footers are verbatim copies of the
expert monolith, so the harmonized outputs are identical; only the wiring
(globals -> Context, accumulator lists -> return values) changed.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer

# =============================================================
# Config / Paths (defaults; overridable via Context.load)
# =============================================================

DEFAULT_BASE_DIR = Path(Path.home(), "ess-dive_wfsfa_soil_datasets")
DEFAULT_OUT_DIR = Path("data", "processed", "ess-dive_wfsfa_soil_datasets")

# map_json[0] is the reference dataset (lookup)
REF_IDX = 0


@dataclass
class DatasetResult:
    """What a per-dataset ``harmonize(ctx)`` returns.

    ``locations`` is a list because some datasets (e.g. index 23) contribute
    more than one location frame.
    """

    dataset_id: str
    harmonized: pd.DataFrame
    locations: list = field(default_factory=list)


@dataclass
class Context:
    """Shared, read-only state passed to every per-dataset harmonizer."""

    map_json: list[dict]
    base_dir: Path = DEFAULT_BASE_DIR
    out_dir: Path = DEFAULT_OUT_DIR
    ref_idx: int = REF_IDX

    @classmethod
    def load(
        cls,
        base_dir: Path | None = None,
        out_dir: Path | None = None,
        mapping_path: Path | None = None,
    ) -> "Context":
        """Load the gold mapping JSON and build a Context.

        Mirrors the monolith's Config cell: the mapping lives next to the
        processed outputs, and the output directory is created on load.
        """
        base_dir = Path(base_dir) if base_dir is not None else DEFAULT_BASE_DIR
        out_dir = Path(out_dir) if out_dir is not None else DEFAULT_OUT_DIR
        if mapping_path is None:
            mapping_path = out_dir / "sm_data_harmonization_mapping.json"
        out_dir.mkdir(parents=True, exist_ok=True)
        with Path(mapping_path).open("r", encoding="utf-8") as f:
            map_json: list[dict] = json.load(f)
        return cls(map_json=map_json, base_dir=base_dir, out_dir=out_dir, ref_idx=REF_IDX)

    # --- dataset-access helpers (were module-level globals in the monolith) ---

    def dsid(self, idx: int) -> str:
        return self.map_json[idx]["dataset_identifier"]

    def ds_path(self, idx: int) -> Path:
        return self.base_dir / self.dsid(idx)

    def read_ds_csv(
        self, idx: int, filename: str, encoding="utf-8", errors="ignore", **kwargs
    ) -> pd.DataFrame:
        return pd.read_csv(self.ds_path(idx) / filename, encoding=encoding, **kwargs)


# =============================================================
# Helpers (verbatim from the monolith)
# =============================================================


def as_list(x):
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def parse_local_to_utc(series: pd.Series, fmt: str | None, tz: str) -> pd.Series:
    dt = pd.to_datetime(series, format=fmt, errors="coerce")
    dt = dt.dt.tz_localize(tz, ambiguous="NaT", nonexistent="shift_forward")
    return dt.dt.tz_convert("UTC")


def interval_min(s: pd.Series) -> pd.Series:
    return s.diff().dt.total_seconds() / 60.0


def utm32613_to_latlon(df: pd.DataFrame, e_col: str, n_col: str) -> pd.DataFrame:
    tr = Transformer.from_crs("EPSG:32613", "EPSG:4326", always_xy=True)
    e = pd.to_numeric(df[e_col], errors="coerce").values
    n = pd.to_numeric(df[n_col], errors="coerce").values
    lon, lat = tr.transform(e, n)
    out = df.copy()
    out["longitude"] = lon
    out["latitude"] = lat
    return out


def ensure_harmonized_cols(df: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "datetime_UTC",
        "site_id",
        "depth_m",
        "replicate",
        "is_timeseries",
        "interval_min",
        "volumetric_water_content_m3_m3",
        "gravimetric_water_content_gH2O_gs",
        "water_potential_kPa",
    ]
    for c in cols:
        if c not in df.columns:
            df[c] = np.nan
    return df[cols]


def add_loc_qc(df: pd.DataFrame) -> pd.DataFrame:
    if "qc_flag" not in df.columns:
        df["qc_flag"] = np.where(df["latitude"].isna() | df["longitude"].isna(), "g2", np.nan)
    return df


# =============================================================
# Location deduplication and harmonization (footer; verbatim body)
# =============================================================


def harmonize_locations(loc_data: list[pd.DataFrame]) -> pd.DataFrame:
    """Collapse sites with identical names / near-identical coordinates to one uuid.

    Verbatim port of the monolith's dedup cell. Returns the deduplicated
    ``loc_df`` and prints the QA summary. Note: as in the expert script, the
    written ``location_data_harmonized.csv`` is the *raw* concat of ``loc_data``
    (see :func:`write_outputs`), not this deduplicated frame.
    """
    import re
    import uuid
    from itertools import combinations

    # Concat location data
    loc_df = pd.concat(loc_data, ignore_index=True)
    loc_df['latitude'] = pd.to_numeric(loc_df['latitude'], errors='coerce')
    loc_df['longitude'] = pd.to_numeric(loc_df['longitude'], errors='coerce')

    # Set thresholds and toggle site_id matching
    # Matching thresholds (tune these)
    coord_match_meters_strict = 5  # highly likely same footprint

    # If TRUE, identical site_id across datasets is considered evidence
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
    # Link rows likely to be same location
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
# Write (footer; verbatim body)
# =============================================================


def write_outputs(
    out_dir: Path,
    harmonized_ids: list[str],
    harmonized_data: list[pd.DataFrame],
    loc_data: list[pd.DataFrame],
) -> None:
    """Write per-dataset harmonized CSVs and the concatenated location CSV."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for ds_identifier, df in zip(harmonized_ids, harmonized_data):
        out_file = out_dir / f"{ds_identifier}_harmonized.csv"
        df.to_csv(out_file, index=False)

    loc_df = pd.concat(loc_data, ignore_index=True)
    loc_df.to_csv(out_dir / "location_data_harmonized.csv", index=False)
