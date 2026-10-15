"""Schema conformance, wrapping :class:`src.schemas.target_schema.TargetSchema`.

Two behaviours of that class need guarding rather than reimplementing:

* ``is_valid()`` ignores range violations, so a volumetric water content of 95
  (percent mistaken for a fraction) passes it. Ranges are scored separately
  here and are part of this module's verdict.
* ``validate_required_fields()`` raises ``KeyError`` when ``datetime_UTC`` or
  ``site_id`` is absent, so it must run after the column check.
"""
from __future__ import annotations

import pandas as pd

from src.schemas.target_schema import HARMONIZED_COLUMNS, TargetSchema


def score(df: pd.DataFrame) -> dict:
    columns = TargetSchema.validate_columns(df)
    out: dict = {
        "has_all_columns": columns["has_all_columns"],
        "has_only_columns": columns["has_only_columns"],
        "missing_columns": columns["missing_columns"],
        "extra_columns": columns["extra_columns"],
        "column_order_correct": list(df.columns) == HARMONIZED_COLUMNS,
    }

    # A CSV carries no dtypes -- what pandas infers on read is a property of
    # the reader, not of the agent. ``TargetSchema.validate_dtypes`` would flag
    # every run for reading datetime_UTC as text. The answerable question is
    # whether each column *coerces* to its expected type without loss, so the
    # raw dtype check is reported for reference but kept out of the verdict.
    dtypes = TargetSchema.validate_dtypes(df)
    out["raw_dtypes_informational"] = [list(map(str, t)) for t in dtypes["incorrect_dtypes"]]
    out["coercion"] = _coercibility(df)
    out["n_uncoercible_columns"] = sum(
        1 for v in out["coercion"].values() if v["uncoercible"] > 0
    )

    # validate_ranges compares against float bounds and raises TypeError on a
    # string-typed column -- which is exactly what a raw CSV read can produce.
    # Hand it a numerically coerced copy so one stray value cannot sink a run.
    ranges = TargetSchema.validate_ranges(_numeric_copy(df))
    out["n_out_of_range_columns"] = len(ranges["out_of_range"])
    out["out_of_range"] = [list(map(str, t)) for t in ranges["out_of_range"]]

    if columns["has_all_columns"] or not (
        {"datetime_UTC", "site_id"} - set(df.columns)
    ):
        required = TargetSchema.validate_required_fields(df)
        out["passes_required_fields"] = required["passes_required_fields"]
        out["required_field_issues"] = required["issues"]
    else:
        out["passes_required_fields"] = False
        out["required_field_issues"] = ["datetime_UTC or site_id column absent"]

    # Unlike TargetSchema.is_valid, ranges count toward the verdict.
    out["conformant"] = bool(
        out["has_all_columns"]
        and out["has_only_columns"]
        and out["n_uncoercible_columns"] == 0
        and out["passes_required_fields"]
        and out["n_out_of_range_columns"] == 0
    )
    return out


def _numeric_copy(df: pd.DataFrame) -> pd.DataFrame:
    """Copy with range-checked columns coerced to float; others left alone."""
    from src.schemas.target_schema import VALID_RANGES

    out = df.copy()
    for col in VALID_RANGES:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def _coercibility(df: pd.DataFrame) -> dict:
    """Per column: how many non-empty values fail to parse as the target type."""
    numeric = {
        "depth_m",
        "replicate",
        "volumetric_water_content_m3_m3",
        "gravimetric_water_content_gH2O_gs",
        "water_potential_kPa",
    }
    out: dict[str, dict] = {}
    for col in HARMONIZED_COLUMNS:
        if col not in df.columns:
            continue
        s = df[col]
        present = s.notna() & (s.astype("string").fillna("").str.strip() != "")
        n_present = int(present.sum())
        if col == "datetime_UTC":
            parsed = pd.to_datetime(s.where(present), utc=True, errors="coerce", format="mixed")
            bad = int((present & parsed.isna()).sum())
        elif col in numeric:
            parsed = pd.to_numeric(s.where(present), errors="coerce")
            bad = int((present & parsed.isna()).sum())
        elif col == "is_timeseries":
            allowed = {"true", "false", "1", "0", "yes", "no"}
            as_text = s.where(present).astype("string").str.strip().str.lower()
            bad = int((present & ~as_text.isin(allowed)).sum())
        else:  # site_id is free text
            bad = 0
        out[col] = {"n_present": n_present, "uncoercible": bad}
    return out
