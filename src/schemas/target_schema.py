"""Target harmonized schema definition and validation.

Every harmonized dataset must conform to this exact 9-column schema.
This module provides validation utilities and constants.
"""
from __future__ import annotations
from enum import Enum
from typing import Literal
import pandas as pd
import numpy as np


# The canonical column list (order matters)
HARMONIZED_COLUMNS = [
    "datetime_UTC",
    "site_id",
    "depth_m",
    "replicate",
    "is_timeseries",
    "interval_min",
    "volumetric_water_content_m3_m3",
    "gravimetric_water_content_gH2O_gs",
    "water_potential_kPa",
]


class QCFlagVocabulary(str, Enum):
    """Controlled vocabulary for qc_flag values."""
    D1 = "d1"  # depth approximated from reported range
    G1 = "g1"  # coordinates from Varadharajan et al. (not in source)
    G2 = "g2"  # coordinates not available from any source


# Expected dtypes for validation
EXPECTED_DTYPES = {
    "datetime_UTC": "datetime64[ns, UTC]",
    "site_id": "object",  # string
    "depth_m": "float64",
    "replicate": "float64",  # allows NaN
    "is_timeseries": "bool",
    "interval_min": "float64",  # allows NaN
    "volumetric_water_content_m3_m3": "float64",
    "gravimetric_water_content_gH2O_gs": "float64",
    "water_potential_kPa": "float64",
}


# Valid ranges for numeric columns (for sanity checks)
VALID_RANGES = {
    "depth_m": (0.0, 100.0),  # 0 to 100 meters
    "interval_min": (0.0, 1e6),  # up to ~2 years
    "volumetric_water_content_m3_m3": (0.0, 1.0),  # fraction
    "gravimetric_water_content_gH2O_gs": (0.0, 10.0),  # g/g, generous upper bound
    "water_potential_kPa": (-1e6, 0.0),  # negative, up to -1 MPa
}


class TargetSchema:
    """Validator for harmonized dataset schema conformance."""

    @staticmethod
    def validate_columns(df: pd.DataFrame) -> dict[str, bool]:
        """Check if DataFrame has exactly the required columns.

        Returns:
            dict with 'has_all_columns', 'has_only_columns', 'missing', 'extra'
        """
        has_all = all(col in df.columns for col in HARMONIZED_COLUMNS)
        has_only = set(df.columns) == set(HARMONIZED_COLUMNS)
        missing = [col for col in HARMONIZED_COLUMNS if col not in df.columns]
        extra = [col for col in df.columns if col not in HARMONIZED_COLUMNS]

        return {
            "has_all_columns": has_all,
            "has_only_columns": has_only,
            "missing_columns": missing,
            "extra_columns": extra,
        }

    @staticmethod
    def validate_dtypes(df: pd.DataFrame) -> dict[str, list]:
        """Check if columns have expected data types.

        Returns:
            dict with 'correct_dtypes' and 'incorrect_dtypes'
        """
        correct = []
        incorrect = []

        for col in HARMONIZED_COLUMNS:
            if col not in df.columns:
                continue

            expected = EXPECTED_DTYPES[col]
            actual = str(df[col].dtype)

            # Special handling for datetime (multiple valid representations)
            if "datetime" in expected:
                if "datetime64" in actual:
                    correct.append(col)
                else:
                    incorrect.append((col, expected, actual))
            # Special handling for object (string)
            elif expected == "object":
                if actual == "object":
                    correct.append(col)
                else:
                    incorrect.append((col, expected, actual))
            # Numeric types
            else:
                if actual == expected:
                    correct.append(col)
                else:
                    incorrect.append((col, expected, actual))

        return {
            "correct_dtypes": correct,
            "incorrect_dtypes": incorrect,
        }

    @staticmethod
    def validate_ranges(df: pd.DataFrame) -> dict[str, list]:
        """Check if numeric values fall within expected ranges.

        Returns:
            dict with 'in_range' and 'out_of_range' lists
        """
        in_range = []
        out_of_range = []

        for col, (min_val, max_val) in VALID_RANGES.items():
            if col not in df.columns:
                continue

            # Check non-NaN values
            valid_mask = ~df[col].isna()
            values = df.loc[valid_mask, col]

            if len(values) == 0:
                continue

            if (values >= min_val).all() and (values <= max_val).all():
                in_range.append(col)
            else:
                n_out = ((values < min_val) | (values > max_val)).sum()
                out_of_range.append((col, n_out, values.min(), values.max()))

        return {
            "in_range": in_range,
            "out_of_range": out_of_range,
        }

    @staticmethod
    def validate_required_fields(df: pd.DataFrame) -> dict[str, any]:
        """Check that required fields are not all-NaN.

        datetime_UTC and site_id must have values.
        At least one moisture variable must have values.
        """
        issues = []

        # Required: datetime_UTC
        if df["datetime_UTC"].isna().all():
            issues.append("datetime_UTC is all NaN")

        # Required: site_id
        if df["site_id"].isna().all():
            issues.append("site_id is all NaN")

        # Required: at least one moisture variable
        moisture_cols = [
            "volumetric_water_content_m3_m3",
            "gravimetric_water_content_gH2O_gs",
            "water_potential_kPa",
        ]
        has_any_moisture = any(
            not df[col].isna().all() for col in moisture_cols if col in df.columns
        )
        if not has_any_moisture:
            issues.append("All moisture variables are NaN")

        return {
            "passes_required_fields": len(issues) == 0,
            "issues": issues,
        }

    @classmethod
    def validate_full(cls, df: pd.DataFrame) -> dict:
        """Run all validation checks.

        Returns:
            Comprehensive validation report
        """
        return {
            "columns": cls.validate_columns(df),
            "dtypes": cls.validate_dtypes(df),
            "ranges": cls.validate_ranges(df),
            "required_fields": cls.validate_required_fields(df),
        }

    @classmethod
    def is_valid(cls, df: pd.DataFrame) -> bool:
        """Quick check: does DataFrame pass all validations?"""
        report = cls.validate_full(df)

        return (
            report["columns"]["has_all_columns"]
            and report["columns"]["has_only_columns"]
            and len(report["dtypes"]["incorrect_dtypes"]) == 0
            and report["required_fields"]["passes_required_fields"]
        )
