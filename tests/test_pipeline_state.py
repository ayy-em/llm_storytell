"""Tests for pipeline state IO: load_state, load_inputs, update_state_atomic."""

import json
from pathlib import Path

import pytest

from llm_storytell.pipeline.state import (
    StateIOError,
    load_inputs,
    load_state,
    update_state_atomic,
    update_state_selected_context,
)


def test_load_state_success(tmp_path: Path) -> None:
    """load_state returns state dict when state.json exists and is valid."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    state_data = {"app": "test", "seed": "x", "outline": []}
    (run_dir / "state.json").write_text(
        json.dumps(state_data, indent=2), encoding="utf-8"
    )
    result = load_state(run_dir)
    assert result == state_data


def test_load_state_missing_file(tmp_path: Path) -> None:
    """load_state raises StateIOError when state.json does not exist."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    with pytest.raises(StateIOError, match="State file not found"):
        load_state(run_dir)


def test_load_state_invalid_json(tmp_path: Path) -> None:
    """load_state raises StateIOError when state.json is invalid JSON."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "state.json").write_text("not json {", encoding="utf-8")
    with pytest.raises(StateIOError, match="Invalid JSON"):
        load_state(run_dir)


def test_load_inputs_success(tmp_path: Path) -> None:
    """load_inputs returns inputs dict when inputs.json exists and is valid."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    inputs_data = {"app": "test", "seed": "x", "beats": 3}
    (run_dir / "inputs.json").write_text(
        json.dumps(inputs_data, indent=2), encoding="utf-8"
    )
    result = load_inputs(run_dir)
    assert result == inputs_data


def test_load_inputs_missing_file(tmp_path: Path) -> None:
    """load_inputs raises StateIOError when inputs.json does not exist."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    with pytest.raises(StateIOError, match="inputs.json not found"):
        load_inputs(run_dir)


def test_load_inputs_invalid_json(tmp_path: Path) -> None:
    """load_inputs raises StateIOError when inputs.json is invalid JSON."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "inputs.json").write_text("not json [", encoding="utf-8")
    with pytest.raises(StateIOError, match="Invalid JSON"):
        load_inputs(run_dir)


def test_update_state_atomic_success(tmp_path: Path) -> None:
    """update_state_atomic applies updater and writes state atomically."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    initial = {"key": "old", "list": [1]}
    state_path = run_dir / "state.json"
    state_path.write_text(json.dumps(initial, indent=2), encoding="utf-8")

    def updater(s: dict) -> None:
        s["key"] = "new"
        s["list"].append(2)

    update_state_atomic(run_dir, updater)

    with state_path.open(encoding="utf-8") as f:
        result = json.load(f)
    assert result["key"] == "new"
    assert result["list"] == [1, 2]
    # No temp file left behind
    assert len(list(run_dir.glob("*.tmp"))) == 0


def test_update_state_atomic_missing_state_raises(tmp_path: Path) -> None:
    """update_state_atomic raises StateIOError when state.json does not exist."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    def updater(s: dict) -> None:
        s["x"] = 1

    with pytest.raises(StateIOError, match="Error reading state for update"):
        update_state_atomic(run_dir, updater)


def test_update_state_selected_context_uses_atomic(tmp_path: Path) -> None:
    """update_state_selected_context updates selected_context via atomic write."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    initial = {
        "app": "test",
        "selected_context": {"location": None, "characters": [], "world_files": []},
    }
    (run_dir / "state.json").write_text(json.dumps(initial, indent=2), encoding="utf-8")
    selected = {"location": "city.md", "characters": ["a.md"], "world_files": []}
    update_state_selected_context(run_dir, selected)
    state = load_state(run_dir)
    assert state["selected_context"] == selected
