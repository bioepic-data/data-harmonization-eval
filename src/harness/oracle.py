"""Oracle: inject gold curator output as harmonizer input.

This module creates "oracle" bundles from expert ground truth,
enabling Skill 2 evaluation independent of Skill 1 errors.
"""
from __future__ import annotations
from pathlib import Path
import json
from typing import Optional

from src.schemas.skill1_bundle import (
    CuratorBundle,
    DataFile,
    LocationResolution,
    TimeSeriesInference,
    ExperimentalContext,
    SimilarDatasetReference,
)


def create_oracle_bundle(
    expert_labels_path: Path,
    package_metadata_path: Path,
    dataset_index: int,
) -> CuratorBundle:
    """Create a curator bundle from expert ground truth labels.

    This "oracle" bundle represents what Skill 1 SHOULD have produced
    for a dataset. Using it as input to Skill 2 isolates harmonizer
    quality from curator errors.

    Args:
        expert_labels_path: Path to expert labels JSON
        package_metadata_path: Path to ESS-DIVE package metadata
        dataset_index: Index in mapping JSON

    Returns:
        CuratorBundle populated with expert ground truth
    """
    # Load expert labels
    with open(expert_labels_path) as f:
        labels = json.load(f)

    # Load package metadata for reference
    with open(package_metadata_path) as f:
        metadata = json.load(f)

    # Extract package ID and DOI
    package_id = metadata.get("id", "")
    doi = metadata.get("dataset", {}).get("@id", "")

    # Build bundle from expert labels
    bundle = CuratorBundle(
        package_id=package_id,
        doi=doi,

        # Expert decision
        curator_decision=labels["gold_decision"],
        exclusion_reason=labels.get("gold_exclusion_reason"),

        # Expert file classifications
        data_payload_files=[
            DataFile(filename=f, columns=[])  # columns filled from actual files
            for f in labels["gold_data_payload_files"]
        ],
        location_metadata_files=[
            DataFile(filename=f, columns=[])
            for f in labels["gold_location_metadata_files"]
        ],
        sensor_metadata_files=[
            DataFile(filename=f, columns=[])
            for f in labels.get("gold_sensor_metadata_files", [])
        ],

        # Expert location resolution
        location_resolution=LocationResolution(
            source=labels["gold_location_source"],
            qc_flag_recommendation=labels.get("gold_qc_flag"),
            site_coordinates=[],  # filled from actual location data
        ),

        # Expert time series inference
        time_series_inference=TimeSeriesInference(
            is_timeseries=labels["gold_is_timeseries"],
            interval_min=labels.get("gold_interval_min"),
            reasoning="Expert determination"
        ),

        # Expert experimental context
        experimental_context=ExperimentalContext(
            manipulation_detected=labels["gold_manipulation_detected"],
            manipulation_type=labels.get("gold_manipulation_type"),
            has_control_data=None,
            recommendation="include_all" if labels["gold_decision"] == "INCLUDE" else "exclude_all"
        ),

        # Expert exemplar selection
        similar_dataset_reference=(
            SimilarDatasetReference(
                index=labels["gold_exemplar_index"],
                reason="Expert-selected exemplar"
            ) if labels.get("gold_exemplar_index") is not None else None
        ),

        # Metadata
        skill_version="oracle",
        run_id=f"oracle_{dataset_index}",
        timestamp=None,
    )

    return bundle


def load_all_oracle_bundles(
    expert_labels_dir: Path,
    metadata_dir: Path,
) -> dict[int, CuratorBundle]:
    """Load oracle bundles for all gold datasets.

    Args:
        expert_labels_dir: Directory with expert label JSONs
        metadata_dir: Directory with ESS-DIVE metadata

    Returns:
        Dict mapping dataset index to oracle bundle
    """
    oracle_bundles = {}

    # Find all expert label files
    for labels_path in expert_labels_dir.glob("dataset_*.json"):
        # Extract dataset index from filename
        index = int(labels_path.stem.split("_")[1])

        # Find corresponding metadata file
        # PLACEHOLDER: need actual mapping from index to package ID
        metadata_path = metadata_dir / f"metadata_{index}.json"

        if metadata_path.exists():
            oracle_bundles[index] = create_oracle_bundle(
                labels_path,
                metadata_path,
                index,
            )

    return oracle_bundles
