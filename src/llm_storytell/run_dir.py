"""Run directory initialization and management.

Creates and initializes run directories in a deterministic, inspectable way.
Ensures atomic creation: failed runs do not leave partial state.
"""

import json
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


from .logging import RunLogger


class RunInitializationError(Exception):
    """Raised when run initialization fails."""

    pass


def generate_run_id() -> str:
    """Generate a default run ID based on current UTC timestamp.

    Returns:
        Run ID in format: run-YYYYMMDD-HHMMSS
    """
    now = datetime.now(timezone.utc)
    return f"run-{now.strftime('%Y%m%d-%H%M%S')}"


def _create_inputs_json(
    app_name: str,
    seed: str,
    beats: int | None,
    run_id: str,
    context_dir: Path,
    prompts_dir: Path,
    word_count: int | None = None,
) -> dict[str, Any]:
    """Create the inputs.json structure.

    Args:
        app_name: Name of the app being run.
        seed: The story seed/description.
        beats: Number of outline beats (None if app-defined).
        run_id: The unique run identifier.
        context_dir: Path to the app's context directory.
        prompts_dir: Path to the app's prompts directory.
        word_count: Optional target total word count (when --word-count was used).

    Returns:
        Dictionary representing inputs.json content.
    """
    data: dict[str, Any] = {
        "run_id": run_id,
        "app": app_name,
        "seed": seed,
        "beats": beats,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "context_dir": str(context_dir),
        "prompts_dir": str(prompts_dir),
    }
    if word_count is not None:
        data["word_count"] = word_count
    return data


def _create_initial_state(app_name: str, seed: str) -> dict[str, Any]:
    """Create the initial state.json structure.

    Args:
        app_name: Name of the app being run.
        seed: The story seed/description.

    Returns:
        Dictionary representing initial state.json content.
    """
    return {
        "app": app_name,
        "seed": seed,
        "selected_context": {
            "location": None,
            "characters": [],
            "world_files": [],
        },
        "outline": [],
        "sections": [],
        "summaries": [],
        "continuity_ledger": {},
        "token_usage": [],
    }


def initialize_run(
    app_name: str,
    seed: str,
    context_dir: Path,
    prompts_dir: Path,
    beats: int | None = None,
    run_id: str | None = None,
    base_dir: Path | None = None,
    word_count: int | None = None,
) -> Path:
    """Initialize a new run directory with all required files.

    Creates the run directory atomically: if any step fails, no partial
    state is left behind.

    Args:
        app_name: Name of the app being run.
        seed: The story seed/description.
        context_dir: Path to the app's context directory.
        prompts_dir: Path to the app's prompts directory.
        beats: Number of outline beats (None for app-defined default).
        run_id: Optional run ID override. If None, generates one.
        base_dir: Base directory for runs. If None, uses current working directory.
        word_count: Optional target total word count (when --word-count was used).

    Returns:
        Path to the created run directory.

    Raises:
        RunInitializationError: If initialization fails or run already exists.
    """
    if base_dir is None:
        base_dir = Path.cwd()

    base_dir = base_dir.resolve()
    runs_dir = base_dir / "runs"

    # Generate run ID if not provided
    actual_run_id = run_id if run_id else generate_run_id()
    final_run_dir = runs_dir / actual_run_id

    # Check if run already exists (must be created exactly once)
    if final_run_dir.exists():
        raise RunInitializationError(f"Run directory already exists: {final_run_dir}")

    # Ensure runs directory exists
    _retry_fs(lambda: runs_dir.mkdir(parents=True, exist_ok=True))

    # Create in temp directory first for atomicity
    temp_dir = None
    try:
        # Create temp directory in the same filesystem for atomic rename
        temp_dir = Path(
            tempfile.mkdtemp(dir=runs_dir, prefix=f"_build_{actual_run_id}_")
        )

        # Create artifacts subdirectory
        artifacts_dir = temp_dir / "artifacts"
        _retry_fs(lambda: artifacts_dir.mkdir())

        # Write inputs.json
        inputs_data = _create_inputs_json(
            app_name=app_name,
            seed=seed,
            beats=beats,
            run_id=actual_run_id,
            context_dir=context_dir,
            prompts_dir=prompts_dir,
            word_count=word_count,
        )
        inputs_path = temp_dir / "inputs.json"

        def _write_inputs() -> None:
            with inputs_path.open("w", encoding="utf-8") as f:
                json.dump(inputs_data, f, indent=2)

        _retry_fs(_write_inputs)

        # Write initial state.json
        state_data = _create_initial_state(app_name=app_name, seed=seed)
        state_path = temp_dir / "state.json"
        with state_path.open("w", encoding="utf-8") as f:
            json.dump(state_data, f, indent=2)

        # Create run.log (empty initially, logger will write to it)
        log_path = temp_dir / "run.log"
        _retry_fs(lambda: log_path.touch())

        # Initialize logger and write initial entries
        logger = RunLogger(log_path)
        logger.log_run_init(
            app_name=app_name,
            seed=seed,
            context_dir=context_dir,
            prompts_dir=prompts_dir,
        )

        # Atomic rename to final location
        _retry_fs(lambda: temp_dir.rename(final_run_dir))
        temp_dir = None  # Prevent cleanup since rename succeeded

        return final_run_dir

    except Exception as e:
        # Clean up temp directory on any failure
        if temp_dir is not None and temp_dir.exists():
            _retry_fs(lambda: shutil.rmtree(temp_dir, ignore_errors=True))

        if isinstance(e, RunInitializationError):
            raise

        raise RunInitializationError(f"Failed to initialize run: {e}") from e


def get_run_logger(run_dir: Path) -> RunLogger:
    """Get a logger for an existing run directory.

    Args:
        run_dir: Path to the run directory.

    Returns:
        RunLogger instance for the run.

    Raises:
        RunInitializationError: If run directory or log file doesn't exist.
    """
    if not run_dir.is_dir():
        raise RunInitializationError(f"Run directory does not exist: {run_dir}")

    log_path = run_dir / "run.log"
    if not log_path.exists():
        raise RunInitializationError(f"Log file does not exist: {log_path}")

    return RunLogger(log_path)


def _retry_fs(op, *, attempts: int = 8, delay: float = 0.05):
    """Retry a filesystem operation to mitigate transient Windows file locks.

    Retries PermissionError with exponential backoff.
    """
    last: PermissionError | None = None
    for i in range(attempts):
        try:
            return op()
        except PermissionError as e:
            last = e
            time.sleep(delay * (2**i))
    # If we exhausted retries, re-raise the last PermissionError
    raise (
        last if last is not None else PermissionError("Operation failed after retries")
    )
