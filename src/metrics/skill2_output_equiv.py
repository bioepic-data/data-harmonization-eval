"""PRIMARY ENDPOINT: output-data equivalence.

Run BOTH the agent's generated code and the expert's code on the same raw
data, then compare the resulting harmonized tables. Robust to stylistic
differences in code: two correct harmonizations score 1.0 even if the
python differs entirely.
"""
from __future__ import annotations
import pandas as pd
import numpy as np
from pathlib import Path

from src.execution.output_loader import compare_csv_outputs


def compare_harmonized(
    agent_df: pd.DataFrame,
    gold_df: pd.DataFrame,
    float_tol: float = 1e-6,
) -> dict:
    """Return cell-level agreement metrics after aligning on keys.

    This is a wrapper around output_loader.compare_csv_outputs
    that works with in-memory DataFrames.

    Steps:
      1. Align on natural keys (datetime_UTC, site_id, depth_m, replicate).
      2. Report row-alignment recall/precision (rows present in both).
      3. For aligned rows, per-column cell agreement:
           - numeric cols: within float_tol
           - categorical/string cols: exact
      4. Aggregate to overall cell-agreement fraction + per-column breakdown.

    Returns:
        Dict with:
            - row_alignment_f1
            - cell_agreement_overall
            - cell_agreement_by_column
            - n_rows_agent, n_rows_gold
            - sample_mismatches
    """
    # IMPLEMENTATION: This is already implemented in output_loader.compare_csv_outputs
    # We provide a DataFrame interface here

    # Save to temp files for comparison
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        agent_path = Path(f.name)
        agent_df.to_csv(agent_path, index=False)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        gold_path = Path(f.name)
        gold_df.to_csv(gold_path, index=False)

    try:
        result = compare_csv_outputs(agent_path, gold_path, float_tol)
        return result
    finally:
        agent_path.unlink(missing_ok=True)
        gold_path.unlink(missing_ok=True)


def score_output_equivalence(
    agent_csv_path: Path,
    expert_csv_path: Path,
    config: dict,
) -> dict:
    """Score harmonized output equivalence (primary endpoint).

    Args:
        agent_csv_path: Path to agent's harmonized output
        expert_csv_path: Path to expert's harmonized output
        config: Experiment config (for tolerances)

    Returns:
        Dict with output equivalence metrics
    """
    float_tol = config.get("thresholds", {}).get("float_tolerance", 1e-6)

    comparison = compare_csv_outputs(agent_csv_path, expert_csv_path, float_tol)

    # Add pass/fail against threshold
    min_agreement = config.get("thresholds", {}).get("min_cell_agreement", 0.95)
    comparison["passes_threshold"] = (
        comparison["cell_agreement_overall"] >= min_agreement
    )

    return comparison
