"""Statistical analysis for small-N nested data."""

from .sandbox import execute_python_code, SafeExecutionResult
from ..metrics.output_loader import load_harmonized_csv, compare_csv_outputs
from .stats import cluster_bootstrap_ci, mixed_effects_comparison, error_propagation_gap
from .error_taxonomy import classify_error_source
from .similarity import compute_similarity_covariate

__all__ = [
    "execute_python_code",
    "SafeExecutionResult",
    "load_harmonized_csv",
    "compare_csv_outputs",
    "cluster_bootstrap_ci",
    "mixed_effects_comparison",
    "error_propagation_gap",
    "classify_error_source",
    "compute_similarity_covariate",
]
