"""Skill 2 executability: does generated code run and reproduce claimed output?"""
from __future__ import annotations
from pathlib import Path

from src.execution.sandbox import execute_python_code, SafeExecutionResult


def score_code_executability(
    code: str,
    working_dir: Path,
    timeout_sec: int = 300,
) -> dict:
    """Score whether code executes without errors.

    Returns:
        Dict with executability metrics
    """
    result = execute_python_code(code, working_dir, timeout_sec)

    return {
        "executes_successfully": result.success,
        "execution_time_sec": result.execution_time_sec,
        "exit_code": result.exit_code,
        "error_message": result.error_message,
        "output_files_created": len(result.output_files),
    }
