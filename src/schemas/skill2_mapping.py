"""Pydantic models for Skill 2 change-mapping JSON schema.

The harmonizer produces a structured change-mapping JSON documenting all
transformations applied. This schema validates that output and enables
automated scoring of documentation completeness.
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, Any


class MappingPattern(BaseModel):
    """A single transformation pattern for one variable."""
    source_pattern: str  # regex or column name
    source_files: list[str]
    destination_variable: str
    transformation: str  # plain-language description
    unit_conversion: Optional[str] = None


class TransformationRule(BaseModel):
    """Collection of patterns for transforming a target variable."""
    # Key is pattern_1, pattern_2, etc.
    # Value is MappingPattern
    patterns: dict[str, MappingPattern] = Field(default_factory=dict)


class HarmonizationMapping(BaseModel):
    """Complete change-mapping JSON for one dataset.

    This is the documentation output from Skill 2, scored for completeness
    and accuracy against the actual transformations in the generated code.
    """
    index: int
    dataset_identifier: str
    doi: str
    archive_repository: str = "ESS-DIVE"

    # File classifications (should match curator bundle)
    data_payload_files: Optional[list[str]] = None
    location_metadata_files: Optional[list[str]] = None
    sensor_metadata_files: Optional[list[str]] = None

    # Mapping documentation
    # Can be dict (for included datasets) or string (for excluded: "EXCLUDED: reason")
    harmonization_mappings: dict[str, TransformationRule] | str

    # Optional metadata
    notes: Optional[str] = None
    qc_flags_applied: Optional[list[str]] = None

    class Config:
        """Pydantic config."""
        extra = "allow"  # allow additional metadata fields


class Skill2Output(BaseModel):
    """Complete output from Skill 2 (harmonizer).

    Includes both the executable Python code and the change-mapping JSON
    documentation.
    """
    package_id: str

    # Generated outputs
    python_code: str
    mapping_json: HarmonizationMapping

    # Execution metadata
    executed_successfully: Optional[bool] = None
    execution_error: Optional[str] = None

    # Output data metadata (if code executed)
    output_rows: Optional[int] = None
    output_columns: Optional[list[str]] = None
    output_file_path: Optional[str] = None

    # Provenance
    skill_version: Optional[str] = None
    run_id: Optional[str] = None
    timestamp: Optional[str] = None
    input_bundle_hash: Optional[str] = None  # hash of input curator bundle

    class Config:
        """Pydantic config."""
        extra = "forbid"


class ExpertHarmonizationReference(BaseModel):
    """Expert's harmonization outputs for ground truth comparison.

    In Phase A, this comes from the 19 pre-harmonized datasets.
    In Phase B, this comes from the expert's blind harmonization of novel data.
    """
    package_id: str
    dataset_index: int

    # Expert outputs
    expert_python_code: str
    expert_mapping_json: dict[str, Any]
    expert_harmonized_csv_path: str

    # Expert metadata
    expert_id: Optional[str] = None
    harmonization_date: Optional[str] = None

    # For inter-rater reliability (Phase B)
    second_expert_csv_path: Optional[str] = None
    irr_agreement_score: Optional[float] = None

    class Config:
        """Pydantic config."""
        extra = "forbid"
