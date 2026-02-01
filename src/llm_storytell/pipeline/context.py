"""Pipeline context loading and persisting selected_context to state."""

from pathlib import Path
from typing import Any

from ..config import AppConfig
from ..context import ContextLoader, ContextSelection
from ..logging import RunLogger

from .state import update_state_selected_context


def load_and_persist_context(
    run_dir: Path,
    context_dir: Path,
    app_config: AppConfig,
    model: str,
    logger: RunLogger,
    run_id: str | None = None,
) -> ContextSelection:
    """Load context for the run and persist selected_context to state.json.

    Uses ContextLoader to load and select context, then writes
    selected_context (location, characters, world_files basenames) to
    state.json via update_state_selected_context.

    Args:
        run_dir: Path to the run directory (for state.json).
        context_dir: Path to the app's context directory.
        app_config: Merged app config (for max_characters, etc.).
        model: Model identifier (for context-size warning threshold).
        logger: Run logger for context selection logging.
        run_id: Run ID for loader logging (default: run_dir.name).

    Returns:
        ContextSelection from the loader.

    Raises:
        ContextLoaderError: If context loading fails (from ContextLoader).
        OSError: If state write fails.
    """
    run_id = run_id or run_dir.name
    loader = ContextLoader(
        context_dir,
        logger=logger,
        app_config=app_config,
    )
    selection = loader.load_context(run_id, model=model)

    selected_context: dict[str, Any] = {
        "location": Path(selection.selected_location).name
        if selection.selected_location
        else None,
        "characters": [Path(p).name for p in selection.selected_characters],
        "world_files": [Path(p).name for p in selection.world_files],
    }
    update_state_selected_context(run_dir, selected_context)
    return selection
