"""Run a complete ablation fold evaluation: build env → agent → audit → score.

This orchestrates the full pipeline for one leave-one-cluster-out fold:
1. Build isolated environment (.runs/<fold-id>/)
2. Run agent evaluation (manual or automated)
3. Audit tool-call trace for out-of-bounds access
4. Score agent output against gold standard
5. Save results to results/folds/<fold-id>/

Usage:
    # Full pipeline (requires manual agent step)
    python experiments/run_ablation_fold.py --holdout 1,2,3,6,16,27

    # Just build env
    python experiments/run_ablation_fold.py --holdout 1,2,3,6,16,27 --build-only

    # Score existing run
    python experiments/run_ablation_fold.py --fold-id fold-01 --score-only
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Optional

import typer

from src.folds.build_env import build_env, default_name
from src.folds.expert_harmonizer import resolve_holdout, DEFAULT_MAPPING
from src.folds.invigilator import audit, DEFAULT_RAW_DATA
# Uncomment when the reference experiment metrics are adapted for ablation.
# from experiments.metrics.skill2_output_equiv import score_output_equivalence
# from experiments.metrics.composite import compute_composite_scores

app = typer.Typer(add_completion=False, help="Run ablation fold evaluation.")

RESULTS_DIR = Path("results/folds")


def build_fold_env(holdout: set[int], name: Optional[str] = None) -> Path:
    """Build the isolated evaluation environment."""
    typer.echo(f"Building environment for holdout {sorted(holdout)}...")
    env = build_env(
        holdout=holdout,
        name=name,
        # Add metadata_dir if you have cached ESS-DIVE metadata
        # metadata_dir=Path("data/external/ess-dive_meta"),
    )
    typer.echo(f"✅ Environment ready: {env}")
    typer.echo(f"   - MANIFEST: {env / 'MANIFEST.json'}")
    typer.echo(f"   - Instructions: {env / 'AGENT_INSTRUCTIONS.md'}")
    return env


def run_agent_evaluation(env: Path) -> Path:
    """Run or prompt for agent evaluation.

    Currently this is a manual step - returns the expected trace path.

    TODO: Automate this step by:
    - Creating a new git branch from here
    - Invoking the agentic workflow via SDK/API
    - Or providing instructions for manual agent invocation
    """
    typer.echo("\n" + "="*70)
    typer.echo("AGENT EVALUATION STEP (CURRENTLY MANUAL)")
    typer.echo("="*70)
    typer.echo(f"\nTo run the agent evaluation:")
    typer.echo(f"  1. cd {env}")
    typer.echo(f"  2. Read {env / 'AGENT_INSTRUCTIONS.md'}")
    typer.echo(f"  3. Invoke your agentic workflow (curator + harmonizer)")
    typer.echo(f"  4. Agent trace should be saved as: {env / 'agent-trace.jsonl'}")
    typer.echo(f"\nPress Enter when agent evaluation is complete...")
    typer.echo("="*70 + "\n")

    input()  # Wait for user confirmation

    # Expected trace location
    trace = env / "agent-trace.jsonl"
    if not trace.exists():
        typer.echo(f"⚠️  Trace not found at {trace}")
        trace_input = typer.prompt("Enter path to agent trace JSONL")
        trace = Path(trace_input)
        if not trace.exists():
            raise typer.Exit(code=1)

    return trace


def audit_agent_run(env: Path, trace: Path) -> dict:
    """Run invigilator audit on agent trace."""
    typer.echo(f"\nAuditing agent trace for out-of-bounds access...")

    manifest = env / "MANIFEST.json"
    holdout_ids = []
    if manifest.exists():
        holdout_ids = json.loads(manifest.read_text()).get("holdout_identifiers", [])

    report = audit(
        trace_path=trace,
        env_dir=env,
        raw_data_dir=DEFAULT_RAW_DATA,
        holdout_identifiers=holdout_ids,
    )

    if report.clean:
        typer.echo("✅ CLEAN - No out-of-bounds access detected")
    else:
        typer.echo(f"⚠️  {len(report.violations)} VIOLATIONS detected:")
        for v in report.violations[:5]:  # Show first 5
            typer.echo(f"   [{v.tool}] {v.reason}: {v.path}")
        if len(report.violations) > 5:
            typer.echo(f"   ... and {len(report.violations) - 5} more")

    return {
        "clean": report.clean,
        "violations": [
            {"tool": v.tool, "path": v.path, "reason": v.reason, "context": v.context}
            for v in report.violations
        ],
        "n_tool_calls": report.n_tool_calls,
        "n_reads": report.n_reads,
        "reads_in_bounds": report.reads_in_bounds,
    }


def score_agent_output(env: Path, trace: Path) -> dict:
    """Score agent output against gold standard.

    TODO: Implement scoring once experiments.metrics is adapted for ablation workflow.
    This should:
    - Load agent-generated harmonized output
    - Load corresponding gold standard
    - Compute output equivalence metrics
    - Compute semantic mapping accuracy
    - Return composite scores
    """
    typer.echo(f"\n⚠️  Scoring not yet implemented")
    typer.echo("TODO: Adapt experiments.metrics for ablation workflow")

    # Placeholder
    return {
        "output_equivalence": None,
        "semantic_accuracy": None,
        "executability": None,
        "composite_score": None,
    }


def save_results(env: Path, audit_report: dict, scores: dict):
    """Save all results to results/folds/<fold-id>/."""
    fold_id = env.name
    result_dir = RESULTS_DIR / fold_id
    result_dir.mkdir(parents=True, exist_ok=True)

    # Copy manifest
    shutil.copy(env / "MANIFEST.json", result_dir / "manifest.json")

    # Save audit report
    (result_dir / "audit_report.json").write_text(json.dumps(audit_report, indent=2))

    # Save scores
    (result_dir / "scores.json").write_text(json.dumps(scores, indent=2))

    typer.echo(f"\n✅ Results saved to {result_dir}")
    typer.echo(f"   - {result_dir / 'manifest.json'}")
    typer.echo(f"   - {result_dir / 'audit_report.json'}")
    typer.echo(f"   - {result_dir / 'scores.json'}")


@app.command()
def main(
    holdout: Optional[str] = typer.Option(None, "--holdout", help="Comma-separated indices to hold out (e.g., '1,2,3,6,16,27')."),
    fold_id: Optional[str] = typer.Option(None, "--fold-id", help="Existing fold ID to score (skip env build)."),
    build_only: bool = typer.Option(False, "--build-only", help="Only build env, don't run agent or score."),
    score_only: bool = typer.Option(False, "--score-only", help="Only score existing run (requires --fold-id)."),
) -> None:
    """Run a complete ablation fold evaluation or individual steps."""

    if score_only:
        if not fold_id:
            typer.echo("❌ --score-only requires --fold-id")
            raise typer.Exit(code=1)
        env = Path(".runs") / fold_id
        if not env.exists():
            typer.echo(f"❌ Fold environment not found: {env}")
            raise typer.Exit(code=1)

        trace = env / "agent-trace.jsonl"
        if not trace.exists():
            trace_input = typer.prompt("Enter path to agent trace JSONL")
            trace = Path(trace_input)

        audit_report = audit_agent_run(env, trace)
        scores = score_agent_output(env, trace)
        save_results(env, audit_report, scores)
        return

    if not holdout:
        typer.echo("❌ --holdout required when building new environment")
        raise typer.Exit(code=1)

    # Build environment
    holdout_idx = resolve_holdout(holdout.split(","), DEFAULT_MAPPING)
    name = fold_id or default_name(holdout_idx)
    env = build_fold_env(holdout_idx, name)

    if build_only:
        return

    # Run agent (manual for now)
    trace = run_agent_evaluation(env)

    # Audit and score
    audit_report = audit_agent_run(env, trace)
    scores = score_agent_output(env, trace)

    # Save results
    save_results(env, audit_report, scores)


if __name__ == "__main__":
    app()
