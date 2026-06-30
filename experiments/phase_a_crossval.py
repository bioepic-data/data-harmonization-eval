"""Phase A: grouped leave-one-out cross-validation over the 19 gold datasets.

For each held-out dataset, the exemplar pool = all OTHER datasets in the
SAME training group (or all others, for plain LOO). Runs all three modes,
N stochastic repeats each, scores every run, writes tidy results.
"""
from __future__ import annotations
from pathlib import Path
import yaml
import pandas as pd
import json
from datetime import datetime

from src.harness.run_pipeline import run_end_to_end
from src.harness.run_skill1 import run_skill1_isolated
from src.harness.run_skill2 import run_skill2_oracle
from src.harness.oracle import load_all_oracle_bundles
from src.metrics.skill1_metrics import score_skill1
from src.metrics.skill2_output_equiv import score_output_equivalence
from src.metrics.composite import compute_composite_scores


def load_config() -> dict:
    """Load experiment configuration."""
    config_path = Path(__file__).parent.parent / "config" / "experiment.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def load_folds(config: dict) -> list[dict]:
    """Load grouped CV fold definitions from config/cv_folds.yaml.

    Each fold: {fold_id, held_out_datasets, exemplar_pool}.
    Grouped so whole source-clusters are held out where appropriate.
    """
    folds_path = Path(__file__).parent.parent / "config" / "cv_folds.yaml"
    with open(folds_path) as f:
        folds_config = yaml.safe_load(f)

    return folds_config["folds"]


def load_expert_labels(dataset_index: int) -> dict:
    """Load expert ground truth labels for a dataset.

    PLACEHOLDER: Actual path to expert labels directory.
    """
    # PLACEHOLDER: Load from data/gold/expert_labels/
    raise NotImplementedError("Expert labels not yet available")


def run_fold(
    fold: dict,
    config: dict,
    output_dir: Path,
) -> list[dict]:
    """Run all evaluations for one CV fold.

    Args:
        fold: Fold definition (held_out_datasets, exemplar_pool)
        config: Experiment configuration
        output_dir: Where to save outputs

    Returns:
        List of scored result dicts (one per dataset × mode × run)
    """
    results = []

    for dataset_idx in fold["held_out_datasets"]:
        # Load expert labels for this dataset
        try:
            expert_labels = load_expert_labels(dataset_idx)
        except NotImplementedError:
            print(f"Skipping dataset {dataset_idx}: expert labels not available")
            continue

        # Run all modes × stochastic repeats
        for mode in config["modes"]:
            for run_i in range(config["experiment"]["n_stochastic_runs"]):

                run_id = f"fold{fold['fold_id']}_ds{dataset_idx}_{mode}_run{run_i}"
                run_dir = output_dir / run_id

                print(f"Running: {run_id}")

                # Execute based on mode
                if mode == "skill1_isolated":
                    result = run_skill1_isolated(
                        identifier=expert_labels["package_id"],
                        exemplar_pool=fold["exemplar_pool"],
                        config=config,
                        output_dir=run_dir,
                        run_index=run_i,
                    )

                    # Score Skill 1
                    if result["success"]:
                        metrics = score_skill1(
                            result["bundle"],
                            expert_labels
                        )
                        result["metrics"] = metrics

                elif mode == "skill2_oracle":
                    # Load oracle bundle (gold Skill 1 output)
                    oracle_bundle = create_oracle_bundle_from_labels(expert_labels)

                    result = run_skill2_oracle(
                        gold_bundle=oracle_bundle,
                        exemplar_pool=fold["exemplar_pool"],
                        config=config,
                        output_dir=run_dir,
                        run_index=run_i,
                    )

                    # Score Skill 2 (oracle mode)
                    if result["success"]:
                        metrics = score_output_equivalence(
                            agent_csv_path=result["code_path"].replace(".py", "_output.csv"),
                            expert_csv_path=expert_labels["gold_harmonized_csv"],
                            config=config,
                        )
                        result["metrics"] = metrics

                elif mode == "end_to_end":
                    result = run_end_to_end(
                        identifier=expert_labels["package_id"],
                        exemplar_pool=fold["exemplar_pool"],
                        config=config,
                        output_dir=run_dir,
                        run_index=run_i,
                    )

                    # Score both skills + composite
                    if result["success"]:
                        # PLACEHOLDER: Score both skills and combine
                        pass

                # Add metadata
                result["fold_id"] = fold["fold_id"]
                result["dataset_index"] = dataset_idx
                result["mode"] = mode
                result["run_index"] = run_i
                result["timestamp"] = datetime.utcnow().isoformat()

                results.append(result)

    return results


def main():
    """Orchestrate Phase A cross-validation."""
    config = load_config()
    folds = load_folds(config)

    # Create output directory
    out_dir = Path(config["paths"]["results"]) / "raw_runs" / "phase_a"
    out_dir.mkdir(parents=True, exist_ok=True)

    all_results = []

    # Run each fold
    for fold in folds:
        print(f"\n=== Fold {fold['fold_id']} ===")
        fold_results = run_fold(fold, config, out_dir)
        all_results.extend(fold_results)

    # Write tidy results to CSV
    results_df = pd.DataFrame(all_results)
    results_path = Path(config["paths"]["results"]) / "scored" / "phase_a_results.csv"
    results_path.parent.mkdir(parents=True, exist_ok=True)
    results_df.to_csv(results_path, index=False)

    print(f"\nPhase A complete. Results: {results_path}")
    print(f"Total runs: {len(all_results)}")

    # Summary statistics
    summary = {
        "total_runs": len(all_results),
        "n_folds": len(folds),
        "n_datasets": len(set(r["dataset_index"] for r in all_results)),
        "modes": list(set(r["mode"] for r in all_results)),
        "success_rate": sum(1 for r in all_results if r["success"]) / len(all_results),
    }

    summary_path = results_path.parent / "phase_a_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))


def create_oracle_bundle_from_labels(expert_labels: dict):
    """Create oracle curator bundle from expert labels.

    PLACEHOLDER: Convert expert labels to CuratorBundle.
    """
    from src.harness.oracle import create_oracle_bundle
    raise NotImplementedError("Oracle bundle creation not implemented")


if __name__ == "__main__":
    main()
