"""Load and compare harmonized CSV outputs.

After executing agent and expert code, this module loads the resulting
harmonized tables for comparison (the primary evaluation endpoint).
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional
import pandas as pd
import numpy as np

from src.schemas.target_schema import HARMONIZED_COLUMNS, TargetSchema


def load_harmonized_csv(
    csv_path: Path,
    validate_schema: bool = True,
) -> tuple[pd.DataFrame, dict]:
    """Load a harmonized CSV and optionally validate schema.

    Args:
        csv_path: Path to harmonized CSV
        validate_schema: Whether to validate against target schema

    Returns:
        Tuple of (DataFrame, validation_report)
        validation_report is None if validate_schema=False
    """
    # Load CSV
    df = pd.read_csv(csv_path)

    # Parse datetime_UTC if present
    if "datetime_UTC" in df.columns:
        df["datetime_UTC"] = pd.to_datetime(df["datetime_UTC"], utc=True)

    # Validate schema if requested
    validation_report = None
    if validate_schema:
        validation_report = TargetSchema.validate_full(df)

    return df, validation_report


def compare_csv_outputs(
    agent_csv_path: Path,
    expert_csv_path: Path,
    float_tol: float = 1e-6,
) -> dict:
    """Compare agent and expert harmonized outputs.

    This is the primary evaluation metric: do the two harmonizations
    produce the same data?

    Args:
        agent_csv_path: Agent's harmonized output
        expert_csv_path: Expert's harmonized output (ground truth)
        float_tol: Tolerance for floating point comparisons

    Returns:
        Dict with comparison metrics:
            - row_counts: (agent, expert)
            - row_alignment_recall: fraction of expert rows in agent output
            - row_alignment_precision: fraction of agent rows in expert output
            - row_alignment_f1
            - cell_agreement_overall: fraction of aligned cells that match
            - cell_agreement_by_column: per-column agreement
            - mismatches: sample of mismatched cells

    Alignment is based on natural keys: (datetime_UTC, site_id, depth_m, replicate)
    """
    # Load both CSVs
    agent_df, agent_valid = load_harmonized_csv(agent_csv_path)
    expert_df, expert_valid = load_harmonized_csv(expert_csv_path)

    # Identify key columns (for row alignment)
    key_cols = ["datetime_UTC", "site_id", "depth_m", "replicate"]

    # Ensure key columns exist
    for col in key_cols:
        if col not in agent_df.columns or col not in expert_df.columns:
            return {
                "error": f"Missing key column: {col}",
                "row_alignment_f1": 0.0,
                "cell_agreement_overall": 0.0,
            }

    # Create composite keys for matching
    agent_df["_key"] = agent_df[key_cols].astype(str).agg("_".join, axis=1)
    expert_df["_key"] = expert_df[key_cols].astype(str).agg("_".join, axis=1)

    # Row alignment metrics
    agent_keys = set(agent_df["_key"])
    expert_keys = set(expert_df["_key"])

    aligned_keys = agent_keys & expert_keys
    recall = len(aligned_keys) / len(expert_keys) if expert_keys else 0.0
    precision = len(aligned_keys) / len(agent_keys) if agent_keys else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )

    # Cell-level agreement (for aligned rows only)
    if not aligned_keys:
        return {
            "row_counts": (len(agent_df), len(expert_df)),
            "row_alignment_recall": recall,
            "row_alignment_precision": precision,
            "row_alignment_f1": f1,
            "cell_agreement_overall": 0.0,
            "cell_agreement_by_column": {},
        }

    # Merge aligned rows
    agent_aligned = agent_df[agent_df["_key"].isin(aligned_keys)].set_index("_key").sort_index()
    expert_aligned = expert_df[expert_df["_key"].isin(aligned_keys)].set_index("_key").sort_index()

    # Compare cell values
    value_cols = [
        "volumetric_water_content_m3_m3",
        "gravimetric_water_content_gH2O_gs",
        "water_potential_kPa",
        "is_timeseries",
        "interval_min",
    ]

    cell_agreement = {}
    total_cells = 0
    matching_cells = 0
    mismatches = []

    for col in value_cols:
        if col not in agent_aligned.columns or col not in expert_aligned.columns:
            continue

        agent_vals = agent_aligned[col]
        expert_vals = expert_aligned[col]

        # Handle NaN equality
        both_nan = agent_vals.isna() & expert_vals.isna()

        # Numeric comparison with tolerance
        if col in ["volumetric_water_content_m3_m3", "gravimetric_water_content_gH2O_gs",
                   "water_potential_kPa", "interval_min"]:
            close_enough = np.isclose(agent_vals, expert_vals, rtol=float_tol, atol=float_tol, equal_nan=False)
            matches = both_nan | close_enough
        else:
            # Exact comparison for bool/string
            matches = both_nan | (agent_vals == expert_vals)

        n_match = matches.sum()
        n_total = len(matches)

        cell_agreement[col] = n_match / n_total if n_total > 0 else 0.0
        total_cells += n_total
        matching_cells += n_match

        # Sample mismatches for debugging
        if n_match < n_total:
            mismatch_idx = matches[~matches].index[:5]  # first 5 mismatches
            for idx in mismatch_idx:
                mismatches.append({
                    "key": idx,
                    "column": col,
                    "agent_value": agent_vals.loc[idx],
                    "expert_value": expert_vals.loc[idx],
                })

    overall_agreement = matching_cells / total_cells if total_cells > 0 else 0.0

    return {
        "row_counts": (len(agent_df), len(expert_df)),
        "row_alignment_recall": recall,
        "row_alignment_precision": precision,
        "row_alignment_f1": f1,
        "cell_agreement_overall": overall_agreement,
        "cell_agreement_by_column": cell_agreement,
        "aligned_rows": len(aligned_keys),
        "total_cells_compared": total_cells,
        "matching_cells": matching_cells,
        "sample_mismatches": mismatches[:10],  # first 10 for inspection
        "schema_valid_agent": TargetSchema.is_valid(agent_df),
        "schema_valid_expert": TargetSchema.is_valid(expert_df),
    }
