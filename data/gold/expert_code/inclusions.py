"""
Dataset registry for soil moisture harmonization.

Maps dataset indices to their harmonize functions.
Indices correspond to the map_json array index.
"""

from importlib import import_module

# Indices of included datasets (matches map_json)
# Datasets 11-14 and 19-22 are excluded per map_json
DATASET_INDICES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 16, 17, 18, 23, 24, 25, 26, 27]

# Map index → harmonize function (lazy import)
# Each dataset_{XX}.py module must have a harmonize(ctx) function
DATASETS = {
    idx: import_module(f"dataset_{idx:02d}").harmonize
    for idx in DATASET_INDICES
}
