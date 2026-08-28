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
    assert sorted(targets) == sorted(DATASET_INDICES)


def test_cluster_folds_hold_out_cluster_but_target_one_dataset():
    config = yaml.safe_load(Path("config/cv_folds.yaml").read_text())
    clusters = config["clusters"]
    for fold in config["folds"]:
        target = fold["target_dataset"]
        cluster = fold["held_out_cluster"]
        assert target in clusters[cluster]["datasets"]

        if cluster == "cluster_3":
            assert fold["reference_holdout_datasets"] == [target]
        else:
            assert fold["reference_holdout_datasets"] == clusters[cluster]["datasets"]
