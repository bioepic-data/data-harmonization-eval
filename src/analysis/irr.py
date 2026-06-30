"""Inter-rater reliability: expert vs second rater.

For Phase B, a subset of novel datasets are harmonized by two experts
independently. This provides the human ceiling: agent performance is
interpreted relative to expert-vs-expert agreement.
"""
from __future__ import annotations
import pandas as pd
from pathlib import Path


def compute_irr(
    expert1_csv: Path,
    expert2_csv: Path,
    float_tol: float = 1e-6,
) -> dict:
    """Compute inter-rater reliability between two expert harmonizations.

    Uses same cell-agreement metric as agent evaluation.

    Args:
        expert1_csv: First expert's harmonized output
        expert2_csv: Second expert's harmonized output
        float_tol: Tolerance for numeric comparisons

    Returns:
        Dict with IRR metrics (same structure as agent scoring)
    """
    from src.execution.output_loader import compare_csv_outputs

    return compare_csv_outputs(expert1_csv, expert2_csv, float_tol)


def compute_human_ceiling(
    irr_results: list[dict],
) -> dict:
    """Compute human performance ceiling from IRR results.

    Args:
        irr_results: List of IRR comparison dicts

    Returns:
        Dict with summary statistics representing human ceiling
    """
    cell_agreements = [r["cell_agreement_overall"] for r in irr_results]

    return {
        "mean_irr": sum(cell_agreements) / len(cell_agreements),
        "median_irr": sorted(cell_agreements)[len(cell_agreements) // 2],
        "min_irr": min(cell_agreements),
        "max_irr": max(cell_agreements),
        "n_comparisons": len(cell_agreements),
        "interpretation": (
            "Agent performance above this ceiling suggests overfitting to "
            "first expert's idiosyncrasies; below suggests room for improvement."
        ),
    }
