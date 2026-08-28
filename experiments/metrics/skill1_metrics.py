"""Skill 1 (Curator) metrics.

Scores curator output bundle field-by-field against expert labels:
- Decision accuracy (INCLUDE/EXCLUDE/FLAG)
- File selection precision/recall/F1
- Time series inference accuracy
- Interval numeric error
- Location resolution accuracy
- QC flag accuracy
- Manipulation detection accuracy
- Exemplar match quality
- Deferral calibration
"""
from __future__ import annotations
from typing import Optional
import numpy as np

from src.schemas.skill1_bundle import CuratorBundle, ExpertCuratorLabels


def score_decision(
    agent_bundle: CuratorBundle,
    expert_labels: ExpertCuratorLabels,
) -> dict:
    """Score curator decision (INCLUDE/EXCLUDE/FLAG).

    Returns:
        Dict with:
            - correct: bool
            - agent_decision: str
            - gold_decision: str
            - exclusion_reason_match: Optional[bool] (for EXCLUDE cases)
    """
    correct = (agent_bundle.curator_decision == expert_labels.gold_decision)

    result = {
        "correct": correct,
        "agent_decision": agent_bundle.curator_decision,
        "gold_decision": expert_labels.gold_decision,
    }

    # For EXCLUDE, also check if reason is similar
    if agent_bundle.curator_decision == "EXCLUDE" and expert_labels.gold_exclusion_reason:
        # PLACEHOLDER: implement semantic similarity of exclusion reasons
        # For now, exact match
        result["exclusion_reason_match"] = (
            agent_bundle.exclusion_reason == expert_labels.gold_exclusion_reason
        )

    return result


def score_file_selection(
    agent_bundle: CuratorBundle,
    expert_labels: ExpertCuratorLabels,
) -> dict:
    """Score file classification precision/recall.

    Computes P/R/F1 separately for:
        - data_payload_files
        - location_metadata_files
        - sensor_metadata_files

    Returns:
        Dict with metrics per file type
    """
    def compute_set_metrics(agent_files: list, gold_files: list) -> dict:
        agent_set = set(f.filename if hasattr(f, 'filename') else f for f in agent_files)
        gold_set = set(gold_files)

        tp = len(agent_set & gold_set)
        fp = len(agent_set - gold_set)
        fn = len(gold_set - agent_set)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )

        return {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "tp": tp,
            "fp": fp,
            "fn": fn,
        }

    return {
        "data_payload": compute_set_metrics(
            agent_bundle.data_payload_files,
            expert_labels.gold_data_payload_files
        ),
        "location_metadata": compute_set_metrics(
            agent_bundle.location_metadata_files,
            expert_labels.gold_location_metadata_files
        ),
        "sensor_metadata": compute_set_metrics(
            agent_bundle.sensor_metadata_files,
            expert_labels.get("gold_sensor_metadata_files", [])
        ),
    }


def score_timeseries_inference(
    agent_bundle: CuratorBundle,
    expert_labels: ExpertCuratorLabels,
) -> dict:
    """Score time series vs discrete determination.

    Returns:
        Dict with:
            - is_timeseries_correct: bool
            - interval_error_min: Optional[float] (if both are time series)
    """
    is_correct = (
        agent_bundle.time_series_inference.is_timeseries ==
        expert_labels.gold_is_timeseries
    )

    result = {"is_timeseries_correct": is_correct}

    # If both say time series, compare interval
    if (agent_bundle.time_series_inference.is_timeseries and
        expert_labels.gold_is_timeseries):

        agent_interval = agent_bundle.time_series_inference.interval_min
        gold_interval = expert_labels.gold_interval_min

        if agent_interval is not None and gold_interval is not None:
            result["interval_error_min"] = abs(agent_interval - gold_interval)
            result["interval_relative_error"] = (
                abs(agent_interval - gold_interval) / gold_interval
                if gold_interval > 0 else None
            )
        else:
            result["interval_error_min"] = None

    return result


def score_location_resolution(
    agent_bundle: CuratorBundle,
    expert_labels: ExpertCuratorLabels,
) -> dict:
    """Score location source and QC flag accuracy.

    Returns:
        Dict with:
            - source_correct: bool
            - qc_flag_correct: bool
    """
    source_correct = (
        agent_bundle.location_resolution.source ==
        expert_labels.gold_location_source
    )

    qc_flag_correct = (
        agent_bundle.location_resolution.qc_flag_recommendation ==
        expert_labels.gold_qc_flag
    )

    return {
        "source_correct": source_correct,
        "qc_flag_correct": qc_flag_correct,
    }


def score_manipulation_detection(
    agent_bundle: CuratorBundle,
    expert_labels: ExpertCuratorLabels,
) -> dict:
    """Score experimental manipulation detection.

    Returns:
        Dict with:
            - detected_correctly: bool
            - type_match: Optional[bool] (if detected)
    """
    detected_correctly = (
        agent_bundle.experimental_context.manipulation_detected ==
        expert_labels.gold_manipulation_detected
    )

    result = {"detected_correctly": detected_correctly}

    # If both detected manipulation, check type match
    if (agent_bundle.experimental_context.manipulation_detected and
        expert_labels.gold_manipulation_detected):

        result["type_match"] = (
            agent_bundle.experimental_context.manipulation_type ==
            expert_labels.gold_manipulation_type
        )

    return result


def score_exemplar_selection(
    agent_bundle: CuratorBundle,
    expert_labels: ExpertCuratorLabels,
    similarity_scores: Optional[dict] = None,
) -> dict:
    """Score exemplar selection quality.

    Returns:
        Dict with:
            - matches_expert: bool (if expert selected one)
            - similarity_to_selected: Optional[float]
            - rank_of_selected: Optional[int] (rank by similarity)
    """
    result = {}

    if expert_labels.gold_exemplar_index is not None:
        agent_exemplar = (
            agent_bundle.similar_dataset_reference.index
            if agent_bundle.similar_dataset_reference
            else None
        )

        result["matches_expert"] = (
            agent_exemplar == expert_labels.gold_exemplar_index
        )
        result["agent_exemplar"] = agent_exemplar
        result["gold_exemplar"] = expert_labels.gold_exemplar_index

    # If similarity scores provided, report similarity to selected
    if similarity_scores and agent_bundle.similar_dataset_reference:
        selected_idx = agent_bundle.similar_dataset_reference.index
        result["similarity_to_selected"] = similarity_scores.get(selected_idx)

    return result


def score_deferral_calibration(
    agent_bundle: CuratorBundle,
    expert_labels: ExpertCuratorLabels,
) -> dict:
    """Score FLAG/deferral calibration.

    Was the decision to defer (FLAG_FOR_REVIEW) appropriate?
    Check against expert confidence scores.

    Returns:
        Dict with:
            - was_flagged: bool
            - should_have_flagged: bool (based on expert confidence)
            - calibration_correct: bool
    """
    was_flagged = (agent_bundle.curator_decision == "FLAG_FOR_REVIEW")

    # Should flag if expert had low confidence
    confidence_threshold = 0.7
    should_flag = (
        expert_labels.confidence_decision is not None and
        expert_labels.confidence_decision < confidence_threshold
    )

    return {
        "was_flagged": was_flagged,
        "should_have_flagged": should_flag,
        "calibration_correct": (was_flagged == should_flag),
        "expert_confidence": expert_labels.confidence_decision,
    }


def score_skill1(
    agent_bundle: CuratorBundle,
    expert_labels: ExpertCuratorLabels,
    similarity_scores: Optional[dict] = None,
) -> dict:
    """Comprehensive Skill 1 scoring.

    Combines all sub-metrics into one report.

    Returns:
        Dict with all skill1 metrics
    """
    return {
        "decision": score_decision(agent_bundle, expert_labels),
        "file_selection": score_file_selection(agent_bundle, expert_labels),
        "timeseries": score_timeseries_inference(agent_bundle, expert_labels),
        "location": score_location_resolution(agent_bundle, expert_labels),
        "manipulation": score_manipulation_detection(agent_bundle, expert_labels),
        "exemplar": score_exemplar_selection(agent_bundle, expert_labels, similarity_scores),
        "deferral": score_deferral_calibration(agent_bundle, expert_labels),
    }
