"""Integrity checks for the targeted grouped cross-validation plan."""
from __future__ import annotations

from pathlib import Path

import yaml

from src.folds.expert_harmonizer import DATASET_INDICES


def test_every_included_dataset_has_exactly_one_target_fold():
    config = yaml.safe_load(Path("config/cv_folds.yaml").read_text())
    folds = config["folds"]
    targets = [fold["target_dataset"] for fold in folds]

    assert config["cv_strategy"] == "targeted_grouped_loo"
    assert len(folds) == len(DATASET_INDICES) == 19
    assert sorted(targets) == sorted(DATASET_INDICES)
    assert len(set(targets)) == len(targets)


def test_cluster_folds_hold_out_cluster_but_target_one_dataset():
    config = yaml.safe_load(Path("config/cv_folds.yaml").read_text())
    clusters = config["clusters"]
    for fold in config["folds"]:
        assert fold["target_dataset"] in fold["reference_holdout_datasets"]
        cluster = fold.get("held_out_cluster")
        if cluster in {"cluster_1", "cluster_2"}:
            assert fold["reference_holdout_datasets"] == clusters[cluster]["datasets"]
