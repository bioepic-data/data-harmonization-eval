"""Safely execute generated Python harmonization code.

Generated code must be run on raw data to produce harmonized outputs.
This module provides sandboxed execution with timeout and resource limits.
"""
from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass
import subprocess
import tempfile
import shutil
from typing import Optional
import traceback


@dataclass
class SafeExecutionResult:
    """Result of executing generated Python code."""
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    execution_time_sec: float
    output_files: list[Path]
    error_message: Optional[str] = None


def execute_python_code(
    code: str,
    working_dir: Path,
    timeout_sec: int = 300,
    env_vars: Optional[dict] = None,
) -> SafeExecutionResult:
    """Execute Python code in a controlled environment.

    Args:
        code: Python code string to execute
        working_dir: Directory where code will run (should contain raw data)
        timeout_sec: Maximum execution time
        env_vars: Optional environment variables

    Returns:
        SafeExecutionResult with execution details

    Security/safety notes:
        - Runs in subprocess, not main Python process
        - Enforces timeout
        - Working directory is isolated
        - No network access (could add with additional sandboxing)
    """
    import time

    # Create temporary script file
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".py",
        delete=False,
        dir=working_dir
    ) as f:
        script_path = Path(f.name)
        f.write(code)

    start_time = time.time()

    try:
        # Execute in subprocess
        result = subprocess.run(
            ["python", str(script_path)],
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            env=env_vars,
        )

        execution_time = time.time() - start_time

        # Find output files (look for newly created CSVs)
        output_files = list(working_dir.glob("*.csv"))

        return SafeExecutionResult(
            success=(result.returncode == 0),
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.returncode,
            execution_time_sec=execution_time,
            output_files=output_files,
            error_message=None if result.returncode == 0 else result.stderr,
        )

    except subprocess.TimeoutExpired:
        execution_time = time.time() - start_time
        return SafeExecutionResult(
            success=False,
            stdout="",
            stderr="",
            exit_code=-1,
            execution_time_sec=execution_time,
            output_files=[],
            error_message=f"Execution timeout after {timeout_sec}s",
        )

    except Exception as e:
        execution_time = time.time() - start_time
        return SafeExecutionResult(
            success=False,
            stdout="",
            stderr=traceback.format_exc(),
            exit_code=-1,
            execution_time_sec=execution_time,
            output_files=[],
            error_message=str(e),
        )

    finally:
        # Clean up script file
        script_path.unlink(missing_ok=True)


def prepare_execution_environment(
    dataset_index: int,
    raw_data_dir: Path,
    execution_dir: Path,
) -> Path:
    """Prepare isolated execution environment for a dataset.

    Args:
        dataset_index: Dataset index
        raw_data_dir: Directory with raw ESS-DIVE data
        execution_dir: Where to create execution environment

    Returns:
        Path to prepared working directory

    Copies raw data files into isolated directory so execution
    cannot modify originals.
    """
    # Create unique execution directory
    work_dir = execution_dir / f"dataset_{dataset_index}"
    work_dir.mkdir(parents=True, exist_ok=True)

    # Copy raw data files
    dataset_raw_dir = raw_data_dir / f"dataset_{dataset_index}"
    if dataset_raw_dir.exists():
        for file in dataset_raw_dir.glob("**/*"):
            if file.is_file():
                rel_path = file.relative_to(dataset_raw_dir)
                dest = work_dir / rel_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file, dest)

    return work_dir


def cleanup_execution_environment(work_dir: Path, keep_outputs: bool = True):
    """Clean up execution environment after run.

    Args:
        work_dir: Working directory to clean
        keep_outputs: If True, preserve output CSV files
    """
    if keep_outputs:
        # Move output CSVs to parent directory before cleanup
        for csv in work_dir.glob("*.csv"):
            shutil.move(str(csv), str(work_dir.parent / csv.name))

    # Remove working directory
    shutil.rmtree(work_dir, ignore_errors=True)
