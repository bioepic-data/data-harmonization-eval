"""Statistical aggregation honoring the nested structure:
runs within datasets within source-clusters. Avoids inflating effective N.
"""
from __future__ import annotations
import pandas as pd
import numpy as np
from typing import Optional


def cluster_bootstrap_ci(
    scored: pd.DataFrame,
    metric: str,
    cluster_col: str = "cluster",
    n_boot: int = 10000,
    confidence_level: float = 0.95,
) -> dict:
    """Bootstrap CI resampling at the CLUSTER level (not run level).

    Args:
        scored: DataFrame with scored results
        metric: Column name to compute CI for
        cluster_col: Column identifying clusters
        n_boot: Number of bootstrap iterations
        confidence_level: Confidence level (0.95 for 95% CI)

    Returns:
        Dict with point estimate + CI bounds

    PLACEHOLDER: Implement cluster-level bootstrap.
    Resamples clusters (not individual runs), avoiding inflated N.
    """
    # PLACEHOLDER implementation
    # 1. Get unique clusters
    # 2. For each bootstrap iteration:
    #    - Resample clusters with replacement
    #    - Compute metric mean across all runs in resampled clusters
    # 3. Compute percentiles of bootstrap distribution

    point_estimate = scored[metric].mean()

    alpha = 1 - confidence_level
    lower_percentile = (alpha / 2) * 100
    upper_percentile = (1 - alpha / 2) * 100

    # PLACEHOLDER: actual bootstrap
    # For now, return naive CI
    sem = scored[metric].sem()
    ci_half = 1.96 * sem

    return {
        "point_estimate": point_estimate,
        "ci_lower": point_estimate - ci_half,
        "ci_upper": point_estimate + ci_half,
        "n_boot": n_boot,
        "confidence_level": confidence_level,
    }


def mixed_effects_comparison(
    scored: pd.DataFrame,
    metric: str,
    fixed_effects: list[str] = ["mode", "similarity"],
    random_effects: list[str] = ["dataset", "cluster"],
) -> dict:
    """Mixed model: metric ~ fixed_effects + (1|random_effects).

    Args:
        scored: DataFrame with scored results
        metric: Outcome variable
        fixed_effects: Fixed effect predictors
        random_effects: Random effect grouping variables

    Returns:
        Dict with model coefficients + CIs

    PLACEHOLDER: Implement mixed-effects model.
    Requires statsmodels or similar library.
    """
    # PLACEHOLDER: Actual implementation would use statsmodels.formula.api
    # Example:
    # import statsmodels.formula.api as smf
    # formula = f"{metric} ~ {' + '.join(fixed_effects)} + {' + '.join(f'(1 | {re})' for re in random_effects)}"
    # model = smf.mixedlm(formula, data=scored).fit()

    return {
        "coefficients": {},
        "ci_lower": {},
        "ci_upper": {},
        "model_summary": "PLACEHOLDER",
    }


def error_propagation_gap(
    scored: pd.DataFrame,
    metric: str,
    oracle_mode: str = "skill2_oracle",
    end_to_end_mode: str = "end_to_end",
) -> dict:
    """Paired difference: oracle minus end_to_end, per dataset.

    Quantifies how much Skill-1 error degrades the pipeline.

    Args:
        scored: DataFrame with results from both modes
        metric: Metric to compare
        oracle_mode: Mode name for oracle (Skill 2 with gold input)
        end_to_end_mode: Mode name for end-to-end pipeline

    Returns:
        Dict with paired difference statistics

    Uses cluster-bootstrap CI on the paired difference.
    """
    # Filter to relevant modes
    oracle = scored[scored["mode"] == oracle_mode]
    e2e = scored[scored["mode"] == end_to_end_mode]

    # Merge on dataset
    paired = oracle.merge(
        e2e,
        on=["dataset"],
        suffixes=("_oracle", "_e2e")
    )

    # Compute paired differences
    paired["diff"] = paired[f"{metric}_oracle"] - paired[f"{metric}_e2e"]

    # Bootstrap CI on the difference
    ci_result = cluster_bootstrap_ci(paired, "diff")

    return {
        "mean_gap": paired["diff"].mean(),
        "median_gap": paired["diff"].median(),
        "ci_lower": ci_result["ci_lower"],
        "ci_upper": ci_result["ci_upper"],
        "n_datasets": len(paired),
    }
