"""Pydantic contract for the curator output bundle.

This is the interface between Skill 1 and Skill 2. Validating against it
catches malformed bundles before they pollute downstream scoring, and it
defines exactly which fields are independently scorable in skill1_metrics.
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Literal, Optional


class DataFile(BaseModel):
    """Metadata about a single file in the package."""
    filename: str
    columns: list[str]
    row_count_estimate: Optional[int] = None
    file_size_mb: Optional[float] = None
    column_preview: Optional[str] = None


class SiteCoordinate(BaseModel):
    """Geographic coordinates for a single site."""
    site_id: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    easting: Optional[float] = None
    northing: Optional[float] = None
    epsg: Optional[int] = None  # coordinate reference system (e.g., 32613 for UTM)
    elevation_m: Optional[float] = None


class LocationResolution(BaseModel):
    """Information about how site coordinates were resolved."""
    source: Literal[
        "location_metadata_file",
        "data_payload",
        "package_metadata",
        "readme",
        "varadharajan_lookup",
        "unresolvable"
    ]
    qc_flag_recommendation: Optional[Literal["g1", "g2"]] = None
    site_coordinates: list[SiteCoordinate] = Field(default_factory=list)


class TimeSeriesInference(BaseModel):
    """Determination of whether dataset is time series or discrete sampling."""
    is_timeseries: bool
    interval_min: Optional[float] = None
    reasoning: str


class ExperimentalContext(BaseModel):
    """Information about potential experimental manipulations."""
    manipulation_detected: bool
    manipulation_type: Optional[str] = None  # e.g., "warming", "irrigation"
    has_control_data: Optional[bool] = None
    recommendation: Literal["include_all", "exclude_all", "flag_for_review"]


class SimilarDatasetReference(BaseModel):
    """Reference to a similar dataset in the exemplar pool."""
    index: int  # dataset index in mapping JSON
    reason: str  # why this dataset is similar


class CuratorBundle(BaseModel):
    """Complete output bundle from Skill 1 (curator).

    This is the validated interface between curator and harmonizer.
    Every field here is independently scorable against expert ground truth.
    """
    package_id: str
    doi: str
    curator_decision: Literal["INCLUDE", "EXCLUDE", "FLAG_FOR_REVIEW"]
    exclusion_reason: Optional[str] = None

    # File classifications
    data_payload_files: list[DataFile] = Field(default_factory=list)
    location_metadata_files: list[DataFile] = Field(default_factory=list)
    sensor_metadata_files: list[DataFile] = Field(default_factory=list)

    # Documentation
    readme_content: Optional[str] = None

    # Scientific inferences
    location_resolution: LocationResolution
    time_series_inference: TimeSeriesInference
    experimental_context: ExperimentalContext

    # Exemplar selection
    similar_dataset_reference: Optional[SimilarDatasetReference] = None

    # Uncertainties
    open_questions: list[str] = Field(default_factory=list)

    # Metadata
    skill_version: Optional[str] = None
    run_id: Optional[str] = None
    timestamp: Optional[str] = None

    class Config:
        """Pydantic config."""
        extra = "forbid"  # catch schema drift
        validate_assignment = True


class ExpertCuratorLabels(BaseModel):
    """Ground truth labels for Skill 1 evaluation.

    Expert's authoritative answers for each scorable field in CuratorBundle.
    Used as reference standard in Phase A cross-validation.
    """
    package_id: str

    # Ground truth decisions
    gold_decision: Literal["INCLUDE", "EXCLUDE", "FLAG_FOR_REVIEW"]
    gold_exclusion_reason: Optional[str] = None

    # Ground truth file classifications
    gold_data_payload_files: list[str]  # filenames
    gold_location_metadata_files: list[str]
    gold_sensor_metadata_files: list[str]

    # Ground truth inferences
    gold_is_timeseries: bool
    gold_interval_min: Optional[float] = None
    gold_location_source: str
    gold_qc_flag: Optional[Literal["g1", "g2"]] = None

    # Ground truth experimental context
    gold_manipulation_detected: bool
    gold_manipulation_type: Optional[str] = None

    # Ground truth exemplar (if expert would have selected one)
    gold_exemplar_index: Optional[int] = None

    # Expert confidence scores (for calibration analysis)
    confidence_decision: Optional[float] = None  # 0-1
    confidence_timeseries: Optional[float] = None
    confidence_manipulation: Optional[float] = None

    class Config:
        """Pydantic config."""
        extra = "forbid"
