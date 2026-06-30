"""Phase B: prospective evaluation on novel datasets.

Using all 19 gold datasets as exemplars, agent harmonizes genuinely new
ESS-DIVE datasets. In parallel and blind, domain expert harmonizes the same
datasets; their output becomes the reference standard.
"""
from __future__ import annotations
from pathlib import Path
import yaml
import pandas as pd
import json
from datetime import datetime

from src.harness.run_pipeline import run_end_to_end
from src.metrics.skill2_output_equiv import score_output_equivalence
from src.analysis.irr import compute_irr


def load_config() -> dict:
    """Load experiment configuration."""
    config_path = Path(__file__).parent.parent / "config" / "experiment.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def load_novel_dataset_list() -> list[str]:
    """Load list of novel dataset identifiers for Phase B.

    PLACEHOLDER: Load from data/prospective/dataset_list.txt
    """
    # PLACEHOLDER: Actual implementation
    raise NotImplementedError("Novel dataset list not available")


def main():
    """Orchestrate Phase B prospective evaluation."""
    config = load_config()

    # All 19 gold datasets available as exemplars
    exemplar_pool = list(range(1, 20))

    # Load novel datasets
    try:
        novel_datasets = load_novel_dataset_list()
    except NotImplementedError:
        print("Novel dataset list not available. Exiting.")
        return

    # Create output directory
    out_dir = Path(config["paths"]["results"]) / "raw_runs" / "phase_b"
    out_dir.mkdir(parents=True, exist_ok=True)

    all_results = []

    # Run agent on each novel dataset
    for identifier in novel_datasets:
        for run_i in range(config["experiment"]["n_stochastic_runs"]):
            run_id = f"{identifier.replace(':', '_')}_run{run_i}"
            run_dir = out_dir / run_id

            print(f"Running: {run_id}")

            # Run end-to-end pipeline
            result = run_end_to_end(
                identifier=identifier,
                exemplar_pool=exemplar_pool,
                config=config,
                output_dir=run_dir,
                run_index=run_i,
            )

            # Metadata
            result["identifier"] = identifier
            result["run_index"] = run_i
            result["timestamp"] = datetime.utcnow().isoformat()
            result["phase"] = "B"

            all_results.append(result)

    # Write initial results (before expert comparison)
    results_df = pd.DataFrame(all_results)
    results_path = Path(config["paths"]["results"]) / "scored" / "phase_b_agent_outputs.csv"
    results_path.parent.mkdir(parents=True, exist_ok=True)
    results_df.to_csv(results_path, index=False)

    print(f"\nPhase B agent runs complete: {results_path}")
    print("Waiting for expert harmonizations...")

    # PHASE B SCORING (after expert harmonizations available)
    # This would be run separately after expert completes blind harmonization

    print("\nTo score Phase B:")
    print("1. Expert independently harmonizes novel datasets")
    print("2. Run phase_b_scoring.py to compare agent vs expert outputs")


def score_phase_b(
    agent_results_path: Path,
    expert_harmonizations_dir: Path,
    config: dict,
):
    """Score Phase B results against expert harmonizations.

    This function is called AFTER expert has completed blind harmonization.

    Args:
        agent_results_path: Path to phase_b_agent_outputs.csv
        expert_harmonizations_dir: Directory with expert harmonized CSVs
        config: Experiment configuration
    """
    agent_results = pd.read_csv(agent_results_path)

    scored_results = []

    for idx, row in agent_results.iterrows():
        identifier = row["identifier"]

        # Find agent's output
        agent_csv = Path(row["code_path"]).replace(".py", "_output.csv")

        # Find expert's output
        expert_csv = expert_harmonizations_dir / f"{identifier}_expert.csv"

        if not expert_csv.exists():
            print(f"Warning: Expert harmonization not found for {identifier}")
            continue

        # Score output equivalence
        metrics = score_output_equivalence(agent_csv, expert_csv, config)

        scored_results.append({
            **row.to_dict(),
            **metrics,
        })

    # Write scored results
    scored_df = pd.DataFrame(scored_results)
    scored_path = agent_results_path.parent / "phase_b_scored.csv"
    scored_df.to_csv(scored_path, index=False)

    print(f"Phase B scoring complete: {scored_path}")

    # Summary statistics
    summary = {
        "n_datasets": len(set(scored_df["identifier"])),
        "n_runs": len(scored_df),
        "mean_cell_agreement": scored_df["cell_agreement_overall"].mean(),
        "pass_rate": (scored_df["passes_threshold"].sum() / len(scored_df)),
    }

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
