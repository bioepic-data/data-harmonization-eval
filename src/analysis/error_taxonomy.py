"""Error taxonomy: classify end-to-end failures by root cause.

Categories:
  1. Skill-1 error propagated (curator error caused downstream failure)
  2. Skill-2 error independent (harmonizer error despite correct input)
  3. Interface inconsistency (bundle schema mismatch)
  4. Genuinely ambiguous (expert also uncertain)
"""
from __future__ import annotations
from typing import Literal


ErrorCategory = Literal[
    "skill1_propagated",
    "skill2_independent",
    "interface_inconsistency",
    "genuinely_ambiguous"
]


def classify_error_source(
    skill1_metrics: dict,
    skill2_oracle_metrics: dict,
    end_to_end_metrics: dict,
    expert_confidence: dict,
) -> ErrorCategory:
    """Classify the root cause of an end-to-end failure.

    Logic:
        1. If Skill 1 made an error AND Skill 2 (oracle) succeeded:
           -> skill1_propagated
        2. If Skill 1 was correct AND Skill 2 (oracle) failed:
           -> skill2_independent
        3. If both failed in different ways:
           -> Check bundle schema validity
              -> If invalid: interface_inconsistency
              -> Else: genuinely_ambiguous
        4. If expert had low confidence:
           -> genuinely_ambiguous

    Args:
        skill1_metrics: Skill 1 scores
        skill2_oracle_metrics: Skill 2 scores with oracle input
        end_to_end_metrics: End-to-end pipeline scores
        expert_confidence: Expert confidence scores

    Returns:
        Error category
    """
    # PLACEHOLDER: Implement classification logic

    # Check if Skill 1 made decision error
    skill1_decision_correct = skill1_metrics.get("decision", {}).get("correct", False)

    # Check if Skill 2 (oracle) succeeded
    skill2_oracle_success = (
        skill2_oracle_metrics.get("output_equivalence", {}).get("passes_threshold", False)
    )

    # Check if end-to-end succeeded
    e2e_success = (
        end_to_end_metrics.get("output_equivalence", {}).get("passes_threshold", False)
    )

    # Classify
    if not skill1_decision_correct and skill2_oracle_success:
        return "skill1_propagated"

    if skill1_decision_correct and not skill2_oracle_success:
        return "skill2_independent"

    # Check expert confidence
    if expert_confidence.get("decision") is not None:
        if expert_confidence["decision"] < 0.7:
            return "genuinely_ambiguous"

    # Default to interface issue if both failed
    return "interface_inconsistency"


def compute_error_distribution(
    all_results: list[dict],
) -> dict:
    """Compute distribution of error categories across all failures.

    Args:
        all_results: List of result dicts with error classifications

    Returns:
        Dict with counts and percentages per category
    """
    from collections import Counter

    categories = [r.get("error_category") for r in all_results if r.get("error_category")]
    counts = Counter(categories)

    total = sum(counts.values())

    return {
        "counts": dict(counts),
        "percentages": {cat: count / total * 100 for cat, count in counts.items()},
        "total_failures": total,
    }
