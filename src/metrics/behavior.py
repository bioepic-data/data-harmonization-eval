"""Run behaviour and covariates: exemplar substitution, telemetry, difficulty.

These are **not** quality metrics. Cost and turn count in particular must stay
covariates: a cheap run that silently skips a filter would otherwise look
efficient.

Exemplar substitution is the one behavioural signal that observes the ablation
mechanism rather than inferring it. Fold-01, with all six of its cluster-mates
withheld, reached for four out-of-cluster exemplars -- visible directly in
``audit/access_trace.tsv``.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CV_FOLDS = REPO_ROOT / "config" / "cv_folds.yaml"

_EXEMPLAR_RE = re.compile(r"dataset_(\d+)\.py$")
_INCLUDED = None


def _folds_config() -> dict:
    return yaml.safe_load(CV_FOLDS.read_text())


def fold_structure() -> dict[int, dict]:
    """target index -> fold id, cluster, holdout set, exemplar pool size."""
    cfg = _folds_config()
    clusters = cfg["clusters"]
    included = sorted(
        {d for c in clusters.values() for d in c["datasets"]}
        - set(clusters.get("cluster_4", {}).get("datasets", []))
    )
    out = {}
    for f in cfg["folds"]:
        holdout = list(f["reference_holdout_datasets"])
        out[f["target_dataset"]] = {
            "fold_id": f["fold_id"],
            "cluster": f["held_out_cluster"],
            "cluster_name": clusters[f["held_out_cluster"]]["name"],
            "n_withheld": len(holdout),
            "holdout": holdout,
            "exemplar_pool": len(included) - len(holdout),
        }
    return out


def parse_access_trace(text: str, target: int, holdout: list[int]) -> dict:
    """Exemplar reads, split in-cluster vs out-of-cluster."""
    lines = [l for l in text.splitlines() if l.strip()]
    if not lines:
        return {"available": False}
    rows = [l.split("\t") for l in lines[1:]]
    zones: dict[str, int] = {}
    exemplars: set[int] = set()
    enumerated = False
    for r in rows:
        if len(r) < 6:
            continue
        _tool, _sev, character, _inb, zone, path = r[0], r[1], r[2], r[3], r[4], r[5]
        zones[zone] = zones.get(zone, 0) + 1
        if zone == "exemplar_code":
            m = _EXEMPLAR_RE.search(path)
            if m:
                exemplars.add(int(m.group(1)))
            if character in {"enumerate_names", "enumerate_content"}:
                enumerated = True
    held = set(holdout)
    return {
        "available": True,
        "n_accesses": len(rows),
        "zones": zones,
        "exemplars_read": sorted(exemplars),
        "n_exemplars_read": len(exemplars),
        # Cluster-mates are withheld, so any read of one would be a leak; the
        # meaningful split is whether substitutes came from outside the cluster.
        "n_in_cluster_read": len(exemplars & held),
        "n_out_of_cluster_read": len(exemplars - held),
        "enumerated_exemplar_dir": enumerated,
    }


def parse_execution(raw: str) -> dict:
    """Telemetry from ``audit/claude-execution.json``."""
    events = json.loads(raw)
    if not isinstance(events, list) or not events:
        return {"available": False}
    result = events[-1]
    tools: dict[str, int] = {}
    for ev in events:
        msg = ev.get("message") or {}
        for block in msg.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                tools[block["name"]] = tools.get(block["name"], 0) + 1
    usage = result.get("usage") or {}
    return {
        "available": True,
        "subtype": result.get("subtype"),
        "is_error": result.get("is_error"),
        "num_turns": result.get("num_turns"),
        "duration_ms": result.get("duration_ms"),
        "total_cost_usd": result.get("total_cost_usd"),
        "permission_denials": len(result.get("permission_denials") or []),
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "cache_read_input_tokens": usage.get("cache_read_input_tokens"),
        "model": next(
            (e.get("model") for e in events if e.get("type") == "system" and e.get("model")),
            None,
        ),
        "tool_counts": tools,
        "n_tool_calls": sum(tools.values()),
    }


_CLEAN = re.compile(r"✅\s*CLEAN|✅\s*No CONTAMINATED")
_CONTAM = re.compile(r"⛔\s*CONTAMINATED")
_FINDINGS = re.compile(r"[⛔⚠]\s*(\d+)\s+(?:FINDING|VIOLATION)\(S\)")
_SEV = re.compile(r"(\d+)\s+(CONTAMINATED|LEAK_RISK|BOUNDARY|IN_BOUNDS)")
_COUNTS = re.compile(r"^tool calls:\s*(\d+)\s*\|\s*reads:\s*(\d+)\s*\((\d+) in-bounds\)", re.M)


def parse_invigilator(text: str) -> dict:
    """Process-integrity verdict.

    A gate, not a score: 20 of 21 runs in the corpus are CLEAN, so this has no
    power to discriminate between runs. Two report formats exist across batch
    generations; both are handled.
    """
    out: dict = {"available": True, "contaminated": bool(_CONTAM.search(text))}
    out["clean"] = bool(_CLEAN.search(text)) and not out["contaminated"]
    m = _FINDINGS.search(text)
    out["n_findings"] = int(m.group(1)) if m else 0
    out["severities"] = {sev: int(n) for n, sev in _SEV.findall(text)}
    c = _COUNTS.search(text)
    if c:
        out["n_tool_calls"] = int(c.group(1))
        out["n_reads"] = int(c.group(2))
        out["reads_in_bounds"] = int(c.group(3))
    return out


def difficulty(gold_entry: dict, gold_rows: int, n_gold_sites: int) -> dict:
    """Structural difficulty covariates, to separate agent skill from task ease."""
    patterns = [
        p
        for _g, pats in (gold_entry.get("harmonization_mappings") or {}).items()
        if isinstance(pats, dict)
        for p in pats.values()
        if isinstance(p, dict)
    ]
    n_conv = sum(
        1
        for p in patterns
        if p.get("unit_conversion") and not str(p["unit_conversion"]).lower().startswith("none")
    )
    source_files = {
        f
        for key in ("data_payload_files", "location_metadata_files", "sensor_metadata_files")
        for f in (gold_entry.get(key) or [])
    }
    return {
        "gold_rows": gold_rows,
        "n_gold_sites": n_gold_sites,
        "n_source_files": len(source_files),
        "n_mapping_patterns": len(patterns),
        "n_unit_conversions": n_conv,
        "n_variable_groups": len(gold_entry.get("harmonization_mappings") or {}),
    }
