"""Pipeline state IO: atomic read/update of state.json in run directories."""

import json
import tempfile
from pathlib import Path
from typing import Any


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
        OSError: On read/write or rename failure.
        json.JSONDecodeError: If state.json is invalid JSON.
    """
    state_path = run_dir / "state.json"
    with state_path.open("r", encoding="utf-8") as f:
        state = json.load(f)

    state["selected_context"] = selected_context

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
            json.dump(state, f, indent=2)
        temp_file.replace(state_path)
        temp_file = None
    except OSError:
        if temp_file is not None and temp_file.exists():
            temp_file.unlink(missing_ok=True)
        raise
