"""Pipeline state IO: atomic read/update of state.json in run directories."""

import json
import tempfile
from pathlib import Path
from typing import Any, Callable


class StateIOError(Exception):
    """Raised when state.json or inputs.json cannot be read or written."""

    pass


def load_state(run_dir: Path) -> dict[str, Any]:
    """Load state.json from run directory.

    Args:
        run_dir: Path to the run directory.

    Returns:
        State dictionary.

    Raises:
        StateIOError: If state.json is missing, invalid JSON, or unreadable.
    """
    state_path = run_dir / "state.json"
    if not state_path.exists():
        raise StateIOError(f"State file not found: {state_path}")
    try:
        with state_path.open(encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise StateIOError(f"Invalid JSON in state.json: {e}") from e
    except OSError as e:
        raise StateIOError(f"Error reading state.json: {e}") from e


def load_inputs(run_dir: Path) -> dict[str, Any]:
    """Load inputs.json from run directory.

    Args:
        run_dir: Path to the run directory.

    Returns:
        Inputs dictionary.

    Raises:
        StateIOError: If inputs.json is missing, invalid JSON, or unreadable.
    """
    inputs_path = run_dir / "inputs.json"
    if not inputs_path.exists():
        raise StateIOError(f"inputs.json not found: {inputs_path}")
    try:
        with inputs_path.open(encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise StateIOError(f"Invalid JSON in inputs.json: {e}") from e
    except OSError as e:
        raise StateIOError(f"Error reading inputs.json: {e}") from e


def update_state_atomic(
    run_dir: Path, updater: Callable[[dict[str, Any]], None]
) -> None:
    """Update state.json by applying updater to current state, then atomic write.

    Uses temp file + rename so partial state.json is never left on failure.

    Args:
        run_dir: Path to the run directory.
        updater: Callable that mutates the state dict in place (no return).

    Raises:
        StateIOError: On read failure, write failure, or rename failure.
    """
    state_path = run_dir / "state.json"
    try:
        with state_path.open(encoding="utf-8") as f:
            state = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise StateIOError(f"Error reading state for update: {e}") from e

    updater(state)

    temp_file = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=run_dir,
            delete=False,
            suffix=".tmp",
        ) as f:
            temp_file = Path(f.name)
            json.dump(state, f, indent=2, ensure_ascii=False)
        temp_file.replace(state_path)
        temp_file = None
    except OSError as e:
        if temp_file is not None and temp_file.exists():
            temp_file.unlink(missing_ok=True)
        raise StateIOError(f"Error writing updated state: {e}") from e


def update_state_selected_context(
    run_dir: Path, selected_context: dict[str, Any]
) -> None:
    """Update state.json with selected context files.

    Uses atomic write (temp file + rename) so partial state.json is never left.

    Args:
        run_dir: Path to the run directory.
        selected_context: Dictionary with 'location', 'characters', and
            'world_files' keys (basenames for reproducibility).

    Raises:
        StateIOError: On read/write or rename failure.
    """

    def updater(s: dict[str, Any]) -> None:
        s["selected_context"] = selected_context

    update_state_atomic(run_dir, updater)
