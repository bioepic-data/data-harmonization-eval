"""Statistical analysis for small-N nested data."""

from .stats import cluster_bootstrap_ci, mixed_effects_comparison, error_propagation_gap
from .error_taxonomy import classify_error_source
from .similarity import compute_similarity_covariate

__all__ = [
    "cluster_bootstrap_ci",
    "mixed_effects_comparison",
    "error_propagation_gap",
    "classify_error_source",
    "compute_similarity_covariate",
]
