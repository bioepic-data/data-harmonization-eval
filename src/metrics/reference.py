"""Adapter from the BERDL lakehouse to the canonical 8-column gold frame.

The reference is
``bervodata.watershed_sfa_soil_moisture.ddt_soil_moisture_observation``
(6.4M rows, 19 datasets). It is the same expert ground truth as
``data/gold/expert_code`` -- its per-dataset row counts match the pilot's -- but
complete and queryable, where the repo only ships 49-row snippets.

Three translations are not obvious and are each load-bearing:

* water potential is stored in **pascals**; the harmonized schema is kPa (/1000)
* ``site_id`` is not a column -- it lives in ``sdt_location.site_identifier``,
  reached via ``sdt_location_name`` (which is ``<dataset_id>__<site_id>``)
* dataset identifiers use ``-`` here but ``_`` in the repo's gold mapping
"""
from __future__ import annotations

import functools
import json
import re
from pathlib import Path

import pandas as pd

DB = "bervodata.watershed_sfa_soil_moisture"
OBS = f"{DB}.ddt_soil_moisture_observation"
LOC = f"{DB}.sdt_location"
DATASET = f"{DB}.sdt_dataset"

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLD_MAPPING = REPO_ROOT / "data" / "gold" / "sm_data_harmonization_mapping.json"

#: lakehouse column -> canonical harmonized column
COLUMN_MAP = {
    "datetime_utc": "datetime_UTC",
    "site_identifier": "site_id",
    "depth_below_soil_surface_meter": "depth_m",
    "replicate_series_count_unit": "replicate",
    "is_time_series": "is_timeseries",
    "volumetric_water_content_ratio_unit": "volumetric_water_content_m3_m3",
    "gravimetric_water_content_ratio_unit": "gravimetric_water_content_gH2O_gs",
}

#: Pascals -> kilopascals. Omitting this is a silent 1000x error.
PASCAL_TO_KPA = 1000.0

#: Observed coverage of the reference, recorded so reports can caveat rather
#: than silently present a near-vacuous agreement figure.
REFERENCE_COVERAGE = {
    "gravimetric_water_content_gH2O_gs": 0.000065,
    "water_potential_kPa": 0.0928,
    "volumetric_water_content_m3_m3": 0.9486,
    "depth_m": 0.8303,
}


def normalize_dataset_id(identifier: str) -> str:
    """Canonical form for cross-source identifier matching.

    The gold mapping writes ``ess-dive_b924..._2025...`` while the lakehouse
    writes ``ess-dive-b924...-2025...``.
    """
    return re.sub(r"[_-]", "-", identifier).lower()


@functools.lru_cache(maxsize=1)
def _gold_mapping() -> list[dict]:
    return json.loads(GOLD_MAPPING.read_text())


@functools.lru_cache(maxsize=1)
def target_to_identifier() -> dict[int, str]:
    """Dataset index -> normalised ESS-DIVE identifier, for all 28 packages."""
    return {
        e["index"]: normalize_dataset_id(e["dataset_identifier"])
        for e in _gold_mapping()
        if e.get("dataset_identifier")
    }


def gold_entry(target: int) -> dict | None:
    for e in _gold_mapping():
        if e.get("index") == target:
            return e
    return None


def get_session():
    """Spark session, resolved lazily so imports work off-cluster."""
    from berdl_notebook_utils.setup_spark_session import get_spark_session

    return get_spark_session()


def _norm_expr(col: str) -> str:
    return f"LOWER(REGEXP_REPLACE({col}, '[_-]', '-'))"


def load_gold(target: int, spark=None) -> pd.DataFrame:
    """Canonical 8-column gold frame for one target dataset.

    Joins through ``sdt_location`` to recover ``site_id`` and converts water
    potential out of pascals. Returns pandas because the per-dataset slice is
    at most ~1.25M rows; the join and unit conversion happen in Spark.
    """
    spark = spark or get_session()
    ident = target_to_identifier()[target]
    sql = f"""
        SELECT
            o.datetime_utc,
            l.site_identifier,
            o.depth_below_soil_surface_meter,
            o.replicate_series_count_unit,
            o.is_time_series,
            o.volumetric_water_content_ratio_unit,
            o.gravimetric_water_content_ratio_unit,
            o.soil_micropore_matric_water_potential_pascal / {PASCAL_TO_KPA}
                AS water_potential_kPa
        FROM {OBS} o
        LEFT JOIN {LOC} l ON o.sdt_location_name = l.sdt_location_name
        WHERE {_norm_expr('o.sdt_dataset_name')} = '{ident}'
    """
    df = spark.sql(sql).toPandas()
    return df.rename(columns=COLUMN_MAP)


def gold_row_count(target: int, spark=None) -> int:
    spark = spark or get_session()
    ident = target_to_identifier()[target]
    row = spark.sql(
        f"SELECT COUNT(*) AS n FROM {OBS} WHERE {_norm_expr('sdt_dataset_name')} = '{ident}'"
    ).collect()[0]
    return int(row["n"])


def load_gold_locations(target: int, spark=None) -> pd.DataFrame:
    """Reference sites with coordinates and provenance for one dataset.

    ``geolocation_resolution_method`` is the ground truth for the agents'
    ``qc_flag``: the registry-lookup method corresponds to ``g1`` and the
    not-available method to ``g2``.
    """
    spark = spark or get_session()
    ident = target_to_identifier()[target]
    sql = f"""
        SELECT l.site_identifier AS site_id,
               l.latitude_degree  AS latitude,
               l.longitude_degree AS longitude,
               l.geolocation_resolution_method
        FROM {LOC} l
        WHERE {_norm_expr('l.sdt_dataset_name')} = '{ident}'
    """
    return spark.sql(sql).toPandas()


#: Mapping from the lakehouse's 10-value provenance vocabulary onto the
#: harmonized qc_flag vocabulary. Methods that do not imply a qc_flag map to
#: None (coordinates reported directly in the source need no flag).
def qc_flag_from_method(method: str | None) -> str | None:
    if not method:
        return None
    m = method.lower()
    if "varadharajan" in m or "registration" in m:
        return "g1"
    if "not reported" in m and "not otherwise available" in m:
        return "g2"
    return None


def dataset_provenance(target: int, spark=None) -> dict:
    """Per-package provenance used as difficulty covariates."""
    spark = spark or get_session()
    ident = target_to_identifier()[target]
    rows = spark.sql(
        f"""
        SELECT doi_link, is_imported, depth_resolution_method,
               harmonized_file_row_count
        FROM {DATASET}
        WHERE {_norm_expr('sdt_dataset_name')} = '{ident}'
        """
    ).collect()
    return rows[0].asDict() if rows else {}
