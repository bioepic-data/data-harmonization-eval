"""Validate the LinkML target schema and its example instances.

Each file under ``examples/valid/`` MUST validate against
``src/schemas/target_schema.yaml``; each file under ``examples/invalid/`` MUST
fail validation. The target class for a file is taken from the part of its
filename before the first ``-`` (e.g. ``HarmonizedRecord-foo.yaml`` ->
``HarmonizedRecord``), matching the convention used by ``linkml-run-examples``.

These tests require the ``linkml`` package (see the ``linkml`` optional
dependency group in ``pyproject.toml``); they are skipped if it is not
installed so the rest of the suite can run without it.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

pytest.importorskip("linkml.validator", reason="linkml is not installed")

from linkml.validator import validate  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA = REPO_ROOT / "src" / "schemas" / "target_schema.yaml"
VALID_DIR = REPO_ROOT / "examples" / "valid"
INVALID_DIR = REPO_ROOT / "examples" / "invalid"


def _target_class(path: Path) -> str:
    """Infer the schema class a given example file should be validated against."""
    return path.stem.split("-", 1)[0]


def _instances(directory: Path) -> list[Path]:
    return sorted(directory.glob("*.yaml"))


def _validate(path: Path):
    instance = yaml.safe_load(path.read_text())
    return validate(instance, str(SCHEMA), _target_class(path))


@pytest.mark.parametrize("path", _instances(VALID_DIR), ids=lambda p: p.name)
def test_valid_examples_pass(path: Path) -> None:
    report = _validate(path)
    messages = [r.message for r in report.results]
    assert not report.results, f"{path.name} should validate but got: {messages}"


@pytest.mark.parametrize("path", _instances(INVALID_DIR), ids=lambda p: p.name)
def test_invalid_examples_fail(path: Path) -> None:
    report = _validate(path)
    assert report.results, f"{path.name} should fail validation but passed"


def test_example_directories_are_populated() -> None:
    assert _instances(VALID_DIR), "no valid examples found"
    assert _instances(INVALID_DIR), "no invalid examples found"
