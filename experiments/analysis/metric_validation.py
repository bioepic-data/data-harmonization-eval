"""Metric validation: correlate automated metrics vs expert rubric.

In Phase A, a subset of runs are also scored by expert using a rubric.
This script correlates automated scores with expert scores to validate
that automated metrics meaningfully reflect quality.

If correlation is high, we can confidently use automated metrics in Phase B.
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd
import numpy as np
from scipy.stats import spearmanr, pearsonr


def load_expert_rubric_scores(rubric_path: Path) -> pd.DataFrame:
    """Load expert rubric scores for subset of Phase A runs.

    PLACEHOLDER: Load from data/gold/expert_rubric_scores.csv

    Expected columns:
        - run_id
        - expert_decision_quality (1-5 scale)
        - expert_file_selection_quality (1-5)
        - expert_harmonization_quality (1-5)
        - expert_documentation_quality (1-5)
        - expert_overall_quality (1-5)
    """
    raise NotImplementedError("Expert rubric scores not available")


def load_automated_scores(results_path: Path) -> pd.DataFrame:
    """Load automated metric scores from Phase A."""
    return pd.read_csv(results_path)


def correlate_metrics(
    automated: pd.DataFrame,
    expert_rubric: pd.DataFrame,
) -> dict:
    """Correlate automated metrics with expert rubric scores.

    Args:
        automated: DataFrame with automated metrics
        expert_rubric: DataFrame with expert rubric scores

    Returns:
        Dict with correlation statistics
    """
    # Merge on run_id
    merged = automated.merge(expert_rubric, on="run_id")

    correlations = {}

    # Correlate automated decision accuracy vs expert decision quality
    if "decision_correct" in merged.columns and "expert_decision_quality" in merged.columns:
        r_pearson, p_pearson = pearsonr(
            merged["decision_correct"],
            merged["expert_decision_quality"]
        )
        r_spearman, p_spearman = spearmanr(
            merged["decision_correct"],
            merged["expert_decision_quality"]
        )
        correlations["decision_quality"] = {
            "pearson_r": r_pearson,
            "pearson_p": p_pearson,
            "spearman_r": r_spearman,
            "spearman_p": p_spearman,
        }

    # Correlate automated cell agreement vs expert harmonization quality
    if "cell_agreement_overall" in merged.columns and "expert_harmonization_quality" in merged.columns:
        r_pearson, p_pearson = pearsonr(
            merged["cell_agreement_overall"],
            merged["expert_harmonization_quality"]
        )
        r_spearman, p_spearman = spearmanr(
            merged["cell_agreement_overall"],
            merged["expert_harmonization_quality"]
        )
        correlations["harmonization_quality"] = {
            "pearson_r": r_pearson,
            "pearson_p": p_pearson,
            "spearman_r": r_spearman,
            "spearman_p": p_spearman,
        }

    return correlations


def main():
    """Validate automated metrics against expert rubric scores."""
    # PLACEHOLDER: Load data
    try:
        expert_rubric = load_expert_rubric_scores(
            Path("data/gold/expert_rubric_scores.csv")
        )
    except NotImplementedError:
        print("Expert rubric scores not available. Exiting.")
        return

    automated = load_automated_scores(
        Path("results/scored/phase_a_results.csv")
    )

    # Compute correlations
    correlations = correlate_metrics(automated, expert_rubric)

    # Print results
    print("Metric Validation Results")
    print("=" * 50)

    for metric_name, stats in correlations.items():
        print(f"\n{metric_name}:")
        print(f"  Pearson r:  {stats['pearson_r']:.3f} (p={stats['pearson_p']:.4f})")
        print(f"  Spearman r: {stats['spearman_r']:.3f} (p={stats['spearman_p']:.4f})")

    # Interpretation
    print("\nInterpretation:")
    for metric_name, stats in correlations.items():
        r = stats["spearman_r"]
        if r > 0.7:
            interpretation = "Strong correlation - automated metric is reliable"
        elif r > 0.5:
            interpretation = "Moderate correlation - use with caution"
        else:
            interpretation = "Weak correlation - automated metric may not capture expert judgment"

        print(f"  {metric_name}: {interpretation}")


if __name__ == "__main__":
    main()
