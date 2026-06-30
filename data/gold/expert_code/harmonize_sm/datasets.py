"""Registry of per-dataset expert harmonizers.

Each ``dataset_NN.py`` exposes ``harmonize(ctx) -> DatasetResult``. This maps a
dataset's mapping-JSON index to its harmonizer, so the runner can include or
omit whole datasets just by selecting keys — which is what makes leave-one-
cluster-out a matter of *not importing* a module rather than text-splicing the
monolith.

The indices here are exactly the 19 datasets the expert harmonizes; the
reference dataset (0) and the globally-excluded datasets (11-14, 19-22) have no
module, so requesting them as a hold-out is rejected upstream.
"""
from __future__ import annotations

from importlib import import_module

# Datasets the expert harmonizes, in monolith order.
DATASET_INDICES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 16, 17, 18, 23, 24, 25, 26, 27]

DATASETS = {idx: import_module(f"dataset_{idx:02d}").harmonize for idx in DATASET_INDICES}
