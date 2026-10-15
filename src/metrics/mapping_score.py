"""Mapping-JSON scoring: structured fields, unit conversions, and prose steps.

The ``transformation`` field looks like free prose but is short (median 66
characters) and operational -- it names a small set of discrete steps. The
``unit_conversion`` field is not prose at all: its 153 gold values reduce to 9
templates once numerals are masked, so it is parsed deterministically.

Transformation steps are extracted by a regex pass over a controlled operation
vocabulary. This is deliberately a *lexical* extractor, applied identically to
reference and agent text so any extraction bias is symmetric. An LLM extractor
would recall more, but it must first be validated (blind, symmetric, k-repeat
self-consistency, human IRR on a subsample) because an LLM judging LLM-written
text has a self-preference bias; until that exists the lexical pass is the
honest instrument. :func:`extract_steps` is the seam to swap in.

Steps are pooled **per dataset, not per variable group**: in the reference, a
filter governing every column is recorded inside the ``depth`` group, so a
group-wise comparison would miss it.
"""
from __future__ import annotations

import re
from collections import Counter

#: Controlled operation vocabulary. Order matters only for readability.
OPERATIONS: dict[str, re.Pattern] = {
    "JOIN": re.compile(r"\bjoin(ed|ing|s)?\b|\bmerge(d|s)?\b", re.I),
    "FILTER": re.compile(r"\bfilter|\bexclud|\bremove|\bdrop\b|\bsubset|\bkeep only|\bwhere\b", re.I),
    "RENAME": re.compile(r"\brename", re.I),
    "RESHAPE_WIDE_LONG": re.compile(r"\bwide\b.{0,40}\blong\b|\bmelt\b|\bpivot|\bunpivot|\bstack\b", re.I),
    "PARSE_DATETIME": re.compile(r"parse\s+datetime|ISO\s*8601|strptime|%Y|date\s*format", re.I),
    "TIMEZONE": re.compile(r"\btimezone\b|\bUTC\b|\bGMT\b|America/|Etc/|tz_|localize", re.I),
    "PARSE_FROM_COLNAME": re.compile(
        r"from\s+'\*|column\s+variables|embedded|suffix|parse\s+(float|int)\b|column\s+name", re.I
    ),
    "ASSIGN_CONSTANT": re.compile(r"populate with|hard-?cod|\bassign\b|\bset to\b|\bconstant\b", re.I),
    "DERIVE_MIDPOINT": re.compile(r"midpoint|average of|mean of|\bmidpoint\b", re.I),
    "METADATA_LOOKUP": re.compile(r"package metadata|sensor[_ ]metadata|plot[_ ]metadata|README|lookup", re.I),
    "COORD_TRANSFORM": re.compile(r"\bUTM\b|lat/?lon|reproject|\bCRS\b|EPSG", re.I),
    "AGGREGATE": re.compile(r"\baggregat|\bgroup\s?by\b|\bresample\b|\bmean\(|\bsum\(", re.I),
    "DEDUPE": re.compile(r"\bdedup|\bduplicate", re.I),
}

#: Parameters that make a step reproducible rather than merely named.
_PARAM_HINTS = {
    "JOIN": re.compile(r"\bby\b|\bon\b", re.I),
    "FILTER": re.compile(r"==|!=|=|\bin\b", re.I),
    "RENAME": re.compile(r"\bto\b|->|→", re.I),
    "PARSE_DATETIME": re.compile(r"%[YmdHMS]"),
    "TIMEZONE": re.compile(r"America/|Etc/|UTC|GMT[+-]?\d*"),
    "ASSIGN_CONSTANT": re.compile(r"\d"),
}

_UNIT_CONV = re.compile(
    r"(?P<op>divide|multiply)\s+by\s+(?P<factor>[0-9.eE+-]+).*?from\s+(?P<frm>.+?)\s+to\s+(?P<to>.+?)\.?$",
    re.I | re.S,
)
_NO_CONV = re.compile(r"^\s*none\b", re.I)


def parse_unit_conversion(text: str | None) -> dict:
    """Parse the templated ``unit_conversion`` field into structured form."""
    if text is None:
        return {"present": False, "kind": "absent"}
    if _NO_CONV.match(text):
        return {"present": True, "kind": "none", "factor": 1.0}
    m = _UNIT_CONV.search(text.strip())
    if not m:
        return {"present": True, "kind": "unparsed", "raw": text.strip()[:120]}
    try:
        factor = float(m.group("factor"))
    except ValueError:
        factor = None
    if m.group("op").lower() == "divide" and factor:
        factor = 1.0 / factor
    return {
        "present": True,
        "kind": "scale",
        "factor": factor,
        "from_unit": m.group("frm").strip().lower(),
        "to_unit": m.group("to").strip().lower(),
    }


def extract_steps(text: str | None) -> set[str]:
    """Operation types named in a transformation string."""
    if not text:
        return set()
    return {op for op, rx in OPERATIONS.items() if rx.search(text)}


def extract_steps_detailed(text: str | None) -> dict[str, bool]:
    """Operation -> whether it carries its identifying parameters."""
    out: dict[str, bool] = {}
    for op in extract_steps(text):
        hint = _PARAM_HINTS.get(op)
        out[op] = bool(hint.search(text)) if hint else True
    return out


def _iter_patterns(entry: dict):
    for group, pats in (entry.get("harmonization_mappings") or {}).items():
        if not isinstance(pats, dict):
            continue
        for _, p in pats.items():
            if isinstance(p, dict):
                yield group, p


def dataset_steps(entry: dict) -> tuple[Counter, dict[str, bool]]:
    """Pool operations across all variable groups of one dataset entry."""
    counts: Counter = Counter()
    parameterised: dict[str, bool] = {}
    for _group, p in _iter_patterns(entry):
        detail = extract_steps_detailed(p.get("transformation"))
        for op, has_params in detail.items():
            counts[op] += 1
            parameterised[op] = parameterised.get(op, False) or has_params
    return counts, parameterised


def _set_prf(pred: set, true: set) -> dict:
    tp = len(pred & true)
    p = tp / len(pred) if pred else 0.0
    r = tp / len(true) if true else 0.0
    return {
        "tp": tp,
        "n_agent": len(pred),
        "n_gold": len(true),
        "precision": p,
        "recall": r,
        "f1": (2 * p * r / (p + r)) if (p + r) else 0.0,
        "missing": sorted(true - pred),
        "extra": sorted(pred - true),
    }


def score(agent_entry: dict | None, gold_entry: dict, notes_text: str | None = None) -> dict:
    """Compare one agent mapping entry against the reference entry.

    Documentation **recall** pools the mapping text with ``notes.md`` -- an
    agent should not be penalised for documenting a step in the other
    deliverable -- while **precision** stays attributed per artifact.
    """
    if agent_entry is None:
        return {"available": False}

    out: dict = {"available": True}

    # --- structured file lists ------------------------------------------
    for field_name in ("data_payload_files", "location_metadata_files", "sensor_metadata_files"):
        pred = set(agent_entry.get(field_name) or [])
        true = set(gold_entry.get(field_name) or [])
        if pred or true:
            out[field_name] = _set_prf(pred, true)

    # --- variable groups -------------------------------------------------
    def groups(e: dict) -> set[str]:
        g = set((e.get("harmonization_mappings") or {}).keys())
        # Vocabulary drift seen in the corpus.
        alias = {"water_potential": "soil_water_potential"}
        return {alias.get(x, x) for x in g}

    out["variable_groups"] = _set_prf(groups(agent_entry), groups(gold_entry))

    # --- destination variables ------------------------------------------
    def dests(e: dict) -> set[str]:
        return {
            p.get("destination_variable")
            for _, p in _iter_patterns(e)
            if p.get("destination_variable")
        }

    out["destination_variables"] = _set_prf(dests(agent_entry), dests(gold_entry))

    # --- unit conversions -------------------------------------------------
    def conversions(e: dict) -> set[tuple]:
        found = set()
        for _, p in _iter_patterns(e):
            parsed = parse_unit_conversion(p.get("unit_conversion"))
            if parsed.get("kind") == "scale" and parsed.get("factor"):
                found.add((p.get("destination_variable"), round(parsed["factor"], 9)))
        return found

    out["unit_conversions"] = _set_prf(conversions(agent_entry), conversions(gold_entry))

    # --- transformation steps, stratified by operation -------------------
    gold_counts, _ = dataset_steps(gold_entry)
    agent_counts, agent_params = dataset_steps(agent_entry)
    notes_steps = extract_steps(notes_text)

    by_op: dict[str, dict] = {}
    for op in sorted(set(gold_counts) | set(agent_counts) | notes_steps):
        in_gold = op in gold_counts
        in_mapping = op in agent_counts
        in_notes = op in notes_steps
        by_op[op] = {
            "in_gold": in_gold,
            "in_agent_mapping": in_mapping,
            "in_agent_notes": in_notes,
            # Pooled recall: documented anywhere counts as stated.
            "stated": in_mapping or in_notes,
            "parameterised": agent_params.get(op, False),
            "gold_occurrences": int(gold_counts.get(op, 0)),
        }

    gold_ops = set(gold_counts)
    stated_ops = {op for op, v in by_op.items() if v["stated"]}
    out["steps"] = {
        # Counts, not rates: FILTER occurs twice in the whole reference corpus,
        # so a percentage here would be meaningless.
        "n_gold_ops": len(gold_ops),
        "n_recovered": len(gold_ops & stated_ops),
        "missing_ops": sorted(gold_ops - stated_ops),
        "extra_ops_mapping": sorted(set(agent_counts) - gold_ops),
        "extra_ops_notes": sorted(notes_steps - gold_ops - set(agent_counts)),
        "by_operation": by_op,
    }
    return out
