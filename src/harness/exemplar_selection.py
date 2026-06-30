"""Exemplar selection and dataset similarity computation.

For reproducible exemplar selection and similarity-based analysis.
Similarity is a key covariate: does performance degrade for datasets
far from their nearest exemplar?
"""
from __future__ import annotations
import numpy as np
from typing import Optional
import json
from pathlib import Path


def compute_dataset_similarity(
    dataset_a_features: dict,
    dataset_b_features: dict,
    weights: Optional[dict] = None,
) -> float:
    """Compute similarity score between two datasets.

    Features include:
        - File structure (wide vs long format)
        - Variable types present (VWC, GWC, potential)
        - Time series vs discrete
        - Location data format (lat/lon vs UTM)
        - Depth encoding (explicit column vs embedded in names)

    Args:
        dataset_a_features: Feature dict for dataset A
        dataset_b_features: Feature dict for dataset B
        weights: Optional weights for feature importance

    Returns:
        Similarity score in [0, 1], where 1 = identical structure

    PLACEHOLDER: Implement feature extraction and similarity metric.
    Could use Jaccard, cosine, or custom weighted distance.
    """
    # Default weights (can be tuned)
    if weights is None:
        weights = {
            "file_format": 0.3,
            "variable_types": 0.25,
            "timeseries_match": 0.2,
            "location_format": 0.15,
            "depth_encoding": 0.1,
        }

    # PLACEHOLDER: Extract and compare features
    # This is a sketch; actual implementation needs feature engineering

    similarity_components = {}

    # File format similarity (wide vs long)
    if dataset_a_features.get("format") == dataset_b_features.get("format"):
        similarity_components["file_format"] = 1.0
    else:
        similarity_components["file_format"] = 0.0

    # Variable types Jaccard similarity
    vars_a = set(dataset_a_features.get("variables", []))
    vars_b = set(dataset_b_features.get("variables", []))
    if vars_a or vars_b:
        jaccard = len(vars_a & vars_b) / len(vars_a | vars_b)
        similarity_components["variable_types"] = jaccard
    else:
        similarity_components["variable_types"] = 0.0

    # Time series match
    ts_match = (
        dataset_a_features.get("is_timeseries") == dataset_b_features.get("is_timeseries")
    )
    similarity_components["timeseries_match"] = 1.0 if ts_match else 0.0

    # Location format match
    loc_match = (
        dataset_a_features.get("location_format") == dataset_b_features.get("location_format")
    )
    similarity_components["location_format"] = 1.0 if loc_match else 0.0

    # Depth encoding match
    depth_match = (
        dataset_a_features.get("depth_encoding") == dataset_b_features.get("depth_encoding")
    )
    similarity_components["depth_encoding"] = 1.0 if depth_match else 0.0

    # Weighted average
    total_similarity = sum(
        similarity_components[k] * weights[k]
        for k in similarity_components
    )

    return total_similarity


def select_exemplar(
    target_features: dict,
    candidate_pool: list[dict],
    candidate_indices: list[int],
    strategy: str = "most_similar",
) -> tuple[int, float]:
    """Select best exemplar from pool for a target dataset.

    Args:
        target_features: Feature dict for target dataset
        candidate_pool: List of feature dicts for candidates
        candidate_indices: Corresponding dataset indices
        strategy: Selection strategy ("most_similar", "random", "diverse")

    Returns:
        Tuple of (selected_index, similarity_score)

    Strategies:
        - most_similar: Pick candidate with highest similarity
        - random: Random selection (for ablation)
        - diverse: Pick least similar (for robustness testing)
    """
    if strategy == "random":
        idx = np.random.choice(len(candidate_pool))
        selected_index = candidate_indices[idx]
        similarity = compute_dataset_similarity(
            target_features, candidate_pool[idx]
        )
        return selected_index, similarity

    # Compute similarities to all candidates
    similarities = [
        compute_dataset_similarity(target_features, cand)
        for cand in candidate_pool
    ]

    if strategy == "most_similar":
        idx = np.argmax(similarities)
    elif strategy == "diverse":
        idx = np.argmin(similarities)
    else:
        raise ValueError(f"Unknown strategy: {strategy}")

    return candidate_indices[idx], similarities[idx]


def extract_dataset_features(
    package_metadata: dict,
    mapping_entry: Optional[dict] = None,
) -> dict:
    """Extract structural features from dataset metadata.

    Args:
        package_metadata: ESS-DIVE metadata JSON
        mapping_entry: Optional expert mapping JSON entry

    Returns:
        Feature dict for similarity computation

    PLACEHOLDER: Implement feature extraction from metadata.
    """
    features = {}

    # From package metadata
    if "dataset" in package_metadata:
        dataset = package_metadata["dataset"]

        # Extract variable types from keywords or description
        description = " ".join(dataset.get("description", []))
        features["variables"] = []
        if "VWC" in description or "volumetric water content" in description.lower():
            features["variables"].append("VWC")
        if "GWC" in description or "gravimetric water content" in description.lower():
            features["variables"].append("GWC")
        if "potential" in description.lower() or "matric" in description.lower():
            features["variables"].append("water_potential")

    # From expert mapping (if available, for gold datasets)
    if mapping_entry:
        # Infer format from mapping patterns
        mappings = mapping_entry.get("harmonization_mappings", {})
        if isinstance(mappings, dict):
            # Check for wide format indicators (embedded depth in column names)
            for var, patterns in mappings.items():
                if isinstance(patterns, dict):
                    for pattern_key, pattern in patterns.items():
                        if isinstance(pattern, dict):
                            source = pattern.get("source_pattern", "")
                            if "at_" in source or re.search(r"\d+cm", source):
                                features["format"] = "wide"
                                break

            if "format" not in features:
                features["format"] = "long"

        # Time series
        # PLACEHOLDER: infer from interval_min in mapping or data
        features["is_timeseries"] = True  # default assumption

        # Location format
        location_files = mapping_entry.get("location_metadata_files", [])
        if location_files:
            # Check if UTM or lat/lon
            # PLACEHOLDER: parse location file to determine
            features["location_format"] = "latlon"  # default

        # Depth encoding
        # PLACEHOLDER: check if depth is in dedicated column or embedded
        features["depth_encoding"] = "column"  # default

    return features


# For actual implementation, we'll need to import re
import re
