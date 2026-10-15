"""Score every eval fold against the lakehouse reference.

Usage::

    python -m src.metrics.run_all                 # all eval/* branches
    python -m src.metrics.run_all --target 23     # one fold
    python -m src.metrics.run_all --out results/scored

Writes one JSON per fold plus a combined ``summary.json``.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import traceback
from pathlib import Path

import pandas as pd

from src.metrics import behavior, diagnose, equivalence, location, mapping_score, schema_score
from src.metrics.artifacts import GitSource, list_eval_branches, load_mapping, resolve
from src.metrics.reference import (
    REFERENCE_COVERAGE,
    gold_entry,
    load_gold,
    load_gold_locations,
    target_to_identifier,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO_ROOT / "results" / "scored"


def score_fold(repo: Path, branch: str, spark=None) -> dict:
    ref = branch if branch.startswith("origin/") else f"origin/{branch}"
    source = GitSource(repo, ref)
    art = resolve(source, branch)
    target = art.target

    record: dict = {
        "branch": branch,
        "fold_id": art.fold_id,
        "target": target,
        "run_id": art.run_id,
        "dataset_identifier": target_to_identifier().get(target),
        "artifact_warnings": art.warnings,
    }

    structure = behavior.fold_structure().get(target, {})
    record["fold"] = structure

    gold = load_gold(target, spark=spark)
    gold_loc = load_gold_locations(target, spark=spark)
    gentry = gold_entry(target) or {}

    if art.harmonized_csv:
        agent = pd.read_csv(io.BytesIO(source.read_bytes(art.harmonized_csv)), low_memory=False)
        record["equivalence"] = equivalence.score(agent, gold)
        record["schema"] = schema_score.score(agent)
        record["findings"] = diagnose.diagnose(
            record["equivalence"],
            equivalence.canonicalise(agent),
            equivalence.canonicalise(gold),
        )
    else:
        record["equivalence"] = None
        record["schema"] = None
        record["findings"] = [
            {"code": "NO_HARMONIZED_OUTPUT", "severity": "critical",
             "message": "no harmonized CSV found in output/", "evidence": {}}
        ]

    # Location table.
    agent_loc = None
    if art.location_csv:
        agent_loc = pd.read_csv(io.BytesIO(source.read_bytes(art.location_csv)), low_memory=False)
    crosswalk = (record.get("equivalence") or {}).get("crosswalk")
    record["location"] = location.score(agent_loc, gold_loc, crosswalk=crosswalk)
    record["findings"].extend(diagnose.diagnose_location(record["location"]))
    record["findings"].sort(
        key=lambda f: -diagnose.SEVERITY_ORDER.get(f.get("severity", ""), 0)
    )

    # Mapping semantics, with notes pooled for recall.
    notes = source.read_text(art.notes_md) if art.notes_md else None
    agent_entry = None
    if art.mapping_json:
        try:
            entries = load_mapping(source, art.mapping_json)
            agent_entry = entries[0] if entries else None
        except (json.JSONDecodeError, TypeError) as exc:
            record.setdefault("errors", []).append(f"mapping JSON unreadable: {exc}")
    record["mapping"] = mapping_score.score(agent_entry, gentry, notes_text=notes)

    # Behaviour and covariates.
    if art.access_trace:
        record["access"] = behavior.parse_access_trace(
            source.read_text(art.access_trace), target, structure.get("holdout", [])
        )
    if art.execution_json:
        record["telemetry"] = behavior.parse_execution(source.read_text(art.execution_json))
    if art.invigilator_report:
        record["integrity"] = behavior.parse_invigilator(source.read_text(art.invigilator_report))

    record["difficulty"] = behavior.difficulty(
        gentry, len(gold), int(gold["site_id"].nunique())
    )
    record["reference_coverage"] = REFERENCE_COVERAGE
    return record


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", default=str(REPO_ROOT))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--target", type=int, action="append",
                    help="score only these target indices (repeatable)")
    args = ap.parse_args(argv)

    repo = Path(args.repo)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    branches = [b.replace("origin/", "") for b in list_eval_branches(repo)]
    records, failures = [], []
    spark = None
    for branch in branches:
        try:
            from src.metrics.artifacts import parse_branch

            _fold, target, _run, _att = parse_branch(branch)
        except ValueError:
            continue
        if args.target and target not in args.target:
            continue
        print(f"scoring {branch} ...", flush=True)
        try:
            if spark is None:
                from src.metrics.reference import get_session

                spark = get_session()
            rec = score_fold(repo, branch, spark=spark)
            records.append(rec)
            (out_dir / f"fold-{rec['fold_id']:02d}-target-{target}.json").write_text(
                json.dumps(rec, indent=2, default=str)
            )
        except Exception as exc:  # noqa: BLE001 - one bad fold must not sink the batch
            traceback.print_exc()
            failures.append({"branch": branch, "error": repr(exc)})

    summary = {"n_scored": len(records), "n_failed": len(failures), "failures": failures,
               "folds": records}
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nscored {len(records)} folds, {len(failures)} failures -> {out_dir}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
