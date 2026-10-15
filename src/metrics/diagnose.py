"""Rule-based diagnosis of why a fold's output differs from the reference.

Each detector emits a finding carrying the **evidence** that triggered it, not
a conclusion about cause. A suspected cause ("the agent skipped a filter") is a
hypothesis to be checked against the gold mapping's ``transformation`` text;
stating it as fact in the finding would launder an inference into a result.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

import numpy as np
import pandas as pd

#: Conversion factors that show up as systematic scale errors.
KNOWN_SCALES = {
    100.0: "percent vs fraction",
    0.01: "fraction vs percent",
    1000.0: "kPa vs Pa",
    0.001: "Pa vs kPa",
    101.325: "bar vs kPa",
    1 / 101.325: "kPa vs bar",
}

SEVERITY_ORDER = {"critical": 3, "major": 2, "minor": 1, "info": 0}


@dataclass
class Finding:
    code: str
    severity: str
    message: str
    evidence: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)


def _close(value: float, target: float, rel: float = 0.02) -> bool:
    return abs(value - target) <= rel * abs(target)


def diagnose(scores: dict, agent: pd.DataFrame, gold: pd.DataFrame) -> list[dict]:
    """Produce findings for one fold from its scores and frames."""
    findings: list[Finding] = []
    l0 = scores["L0"]
    cw = scores["crosswalk"]

    # --- row count -------------------------------------------------------
    ratio = l0.get("row_count_ratio")
    if ratio is not None and not _close(ratio, 1.0, 0.05):
        direction = "more" if ratio > 1 else "fewer"
        findings.append(
            Finding(
                code="ROW_INFLATION" if ratio > 1 else "ROW_DEFICIT",
                severity="critical" if abs(np.log(ratio)) > np.log(1.25) else "major",
                message=f"agent emitted {ratio:.3g}x the reference row count ({direction} rows)",
                evidence={"n_agent": l0["n_agent"], "n_gold": l0["n_gold"], "ratio": ratio},
            )
        )

    # --- uniform timestamp shift ----------------------------------------
    offset = scores.get("time_offset") or {}
    if offset.get("detected"):
        corrected = (scores.get("offset_corrected") or {}).get("L3") or {}
        findings.append(
            Finding(
                code="TZ_SHIFT",
                severity="critical",
                message=(
                    f"every timestamp is offset by {offset['offset_hours']:+d} h from the "
                    f"reference; correcting it raises L3 F1 to {corrected.get('f1', 0):.3f}"
                ),
                evidence={
                    "offset_hours": offset["offset_hours"],
                    "overlap_at_zero": offset.get("overlap_at_zero"),
                    "overlap_at_offset": offset.get("overlap_at_offset"),
                    "corrected_L3_f1": corrected.get("f1"),
                },
            )
        )

    # --- site vocabulary -------------------------------------------------
    if cw["kind"] == "suffix_stripped" or (
        cw["n_agent_sites"] and cw["n_gold_sites"] and cw["kind"] not in ("identity",)
    ):
        if cw["kind"] == "suffix_stripped":
            findings.append(
                Finding(
                    code="SITE_VOCAB_COLLAPSE",
                    severity="major",
                    message=(
                        "reference site names extend the agent's with a qualifier the "
                        "agent did not emit; sites are only matchable after stripping it"
                    ),
                    evidence={
                        "n_agent_sites": cw["n_agent_sites"],
                        "n_gold_sites": cw["n_gold_sites"],
                        "crosswalk_kind": cw["kind"],
                        "gold_examples": cw.get("gold_only", [])[:5],
                    },
                )
            )
    if cw.get("agent_only"):
        findings.append(
            Finding(
                code="SITE_SUPERSET",
                severity="critical",
                message=(
                    f"{len(cw['agent_only'])} site(s) present in the agent output have no "
                    "reference counterpart; the reference may apply a row filter the agent omitted"
                ),
                evidence={"agent_only_sites": cw["agent_only"][:20]},
            )
        )
    if cw.get("gold_only"):
        findings.append(
            Finding(
                code="SITE_MISSING",
                severity="critical",
                message=f"{len(cw['gold_only'])} reference site(s) absent from the agent output",
                evidence={"gold_only_sites": cw["gold_only"][:20]},
            )
        )

    # --- empty site ids --------------------------------------------------
    if "site_id" in agent.columns:
        blank = agent["site_id"].isna() | (agent["site_id"].astype("string").fillna("") == "")
        if blank.any():
            findings.append(
                Finding(
                    code="EMPTY_SITE_ID",
                    severity="major",
                    message=f"{int(blank.sum())} agent rows have an empty site_id (a required field)",
                    evidence={"n_rows": int(blank.sum())},
                )
            )

    # --- unit scale ------------------------------------------------------
    for col, stats in l0["columns"].items():
        mr = stats.get("median_ratio")
        if mr is None or mr == 0 or not np.isfinite(mr):
            continue
        for factor, label in KNOWN_SCALES.items():
            if _close(mr, factor, 0.05):
                findings.append(
                    Finding(
                        code="UNIT_SCALE",
                        severity="critical",
                        message=f"{col} medians differ by ~{factor:g}x ({label})",
                        evidence={
                            "column": col,
                            "median_ratio": mr,
                            "agent_median": stats.get("agent_median"),
                            "gold_median": stats.get("gold_median"),
                        },
                    )
                )
                break

    # --- sign ------------------------------------------------------------
    wp = l0["columns"].get("water_potential_kPa", {})
    if wp.get("agent_min") is not None and wp.get("gold_max") is not None:
        if wp["agent_min"] > 0 and wp["gold_max"] <= 0:
            findings.append(
                Finding(
                    code="SIGN_ERROR",
                    severity="critical",
                    message="water potential is positive in the agent output but negative in the reference",
                    evidence={"agent_min": wp["agent_min"], "gold_max": wp["gold_max"]},
                )
            )

    # --- null inflation --------------------------------------------------
    for col, stats in l0["columns"].items():
        a, g = stats.get("agent_null_rate"), stats.get("gold_null_rate")
        if a is None or g is None:
            continue
        if a - g > 0.10:
            findings.append(
                Finding(
                    code="NULL_INFLATION",
                    severity="major",
                    message=f"{col} is null in {a:.1%} of agent rows vs {g:.1%} of reference rows",
                    evidence={"column": col, "agent_null_rate": a, "gold_null_rate": g},
                )
            )
        elif g - a > 0.10:
            findings.append(
                Finding(
                    code="NULL_DEFICIT",
                    severity="major",
                    message=(
                        f"{col} is populated in the agent output ({a:.1%} null) where the "
                        f"reference is mostly null ({g:.1%}); values may be invented or zero-filled"
                    ),
                    evidence={"column": col, "agent_null_rate": a, "gold_null_rate": g},
                )
            )

    # --- duplicate natural keys -----------------------------------------
    key = ["datetime_UTC", "site_id", "depth_m", "replicate"]
    if all(k in agent.columns for k in key):
        dup_a = int(agent.duplicated(subset=key).sum())
        dup_g = int(gold.duplicated(subset=key).sum()) if all(k in gold.columns for k in key) else 0
        if dup_a > dup_g:
            findings.append(
                Finding(
                    code="DUPLICATE_KEYS",
                    severity="major",
                    message=(
                        f"{dup_a} agent rows duplicate the natural key "
                        f"(reference has {dup_g}); the key should identify a row"
                    ),
                    evidence={"agent_duplicates": dup_a, "gold_duplicates": dup_g},
                )
            )

    # --- missingness pattern --------------------------------------------
    l2cells = scores["L2"]["cells"]["by_column"]
    for col, stats in l2cells.items():
        nm = stats.get("null_mask_agreement")
        if nm is not None and nm < 0.95 and stats.get("n"):
            findings.append(
                Finding(
                    code="NULL_PATTERN_MISMATCH",
                    severity="major",
                    message=(
                        f"{col} null positions disagree on {1 - nm:.1%} of paired rows; "
                        "a value may be substituted where the reference records missing"
                    ),
                    evidence={"column": col, "null_mask_agreement": nm},
                )
            )

    # --- gap structure ---------------------------------------------------
    gap = scores["L2"].get("gap_structure") or {}
    share = gap.get("top_site_share")
    if gap.get("n_unmatched_gold") and share is not None and share > 0.8:
        findings.append(
            Finding(
                code="SYSTEMATIC_GAP",
                severity="major",
                message=(
                    f"{share:.0%} of unmatched reference rows fall in a single site; "
                    "the omission is systematic rather than scattered"
                ),
                evidence=gap,
            )
        )

    findings.sort(key=lambda f: -SEVERITY_ORDER.get(f.severity, 0))
    return [f.as_dict() for f in findings]


def diagnose_location(loc: dict) -> list[dict]:
    """Findings about the agent's location table and coordinate resolution."""
    findings: list[Finding] = []
    if not loc.get("available"):
        return []

    resolvable = loc.get("n_gold_sites_with_coords") or 0
    agent_coords = loc.get("n_agent_rows_with_coords") or 0
    if resolvable and agent_coords == 0:
        findings.append(
            Finding(
                code="COORD_UNRESOLVED",
                severity="critical",
                message=(
                    f"agent emitted no coordinates, but the reference resolves {resolvable} "
                    "site(s); an available location source appears not to have been consulted"
                ),
                evidence={
                    "n_gold_sites_with_coords": resolvable,
                    "n_agent_rows_with_coords": agent_coords,
                },
            )
        )

    qc = loc.get("qc_flag") or {}
    if qc.get("n_compared") and qc.get("accuracy") is not None and qc["accuracy"] < 0.5:
        findings.append(
            Finding(
                code="QC_FLAG_MISMATCH",
                severity="major",
                message=(
                    f"qc_flag disagrees with the reference provenance on "
                    f"{1 - qc['accuracy']:.0%} of {qc['n_compared']} compared site(s)"
                ),
                evidence=qc,
            )
        )

    coords = loc.get("coordinates") or {}
    if coords.get("n_compared") and coords.get("median_error_m") is not None:
        if coords["median_error_m"] > 100:
            findings.append(
                Finding(
                    code="COORD_ERROR",
                    severity="major",
                    message=(
                        f"median coordinate error {coords['median_error_m']:.0f} m "
                        f"across {coords['n_compared']} site(s)"
                    ),
                    evidence=coords,
                )
            )

    site = loc.get("site_set") or {}
    if site.get("recall") is not None and site["recall"] < 1.0 and site.get("n_gold", 0):
        findings.append(
            Finding(
                code="LOCATION_SITE_RECALL",
                severity="minor",
                message=(
                    f"location table covers {site['recall']:.0%} of reference sites "
                    "(name-vocabulary differences may account for some of this)"
                ),
                evidence=site,
            )
        )

    findings.sort(key=lambda f: -SEVERITY_ORDER.get(f.severity, 0))
    return [f.as_dict() for f in findings]
