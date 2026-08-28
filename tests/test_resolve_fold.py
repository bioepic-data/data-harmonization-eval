"""Tests for workflow-dispatch fold resolution."""
from __future__ import annotations

import pytest
import yaml

from src.folds.resolve_fold import resolve_fold


@pytest.fixture
def config():
    return yaml.safe_load(open("config/cv_folds.yaml"))


def test_configured_target_ablates_cluster_and_stages_target(config):
    resolved = resolve_fold("1", "", config)
    assert resolved.holdout == "1,2,3,6,16,27"
    assert resolved.target == "1"
    assert resolved.stage_indices == "1"
    assert resolved.env_name == "fold-01-target-1"


def test_cluster_input_preserves_legacy_multi_target_mode(config):
    resolved = resolve_fold("cluster_2", "", config)
    assert resolved.holdout == "15,26"
    assert resolved.target == "15,26"
    assert resolved.stage_indices == "15,26"
    assert resolved.env_name == "cluster_2"


def test_fold_id_zero_still_selects_fold_name():
    config = {
        "clusters": {},
        "folds": [{"fold_id": 0, "target_dataset": 1, "reference_holdout_datasets": [1]}],
    }
    assert resolve_fold("1", "", config).env_name == "fold-00-target-1"


def test_unsafe_dispatch_input_is_rejected(config):
    with pytest.raises(ValueError, match="must contain only"):
        resolve_fold("1\nenv_path=attacker", "", config)
