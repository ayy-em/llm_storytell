"""Tests for CLI TTS flags and resolution (default, override precedence, pipeline skip)."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from llm_storytell.cli import (
    _update_state_selected_context,
    create_parser,
    main,
)


@pytest.fixture
def temp_app_minimal(tmp_path: Path) -> Path:
    """Minimal app layout so resolve_app and load_app_config succeed."""
    context_dir = tmp_path / "apps" / "test-app" / "context"
    context_dir.mkdir(parents=True)
    (context_dir / "lore_bible.md").write_text("# Lore\n\nTest lore.")
    (context_dir / "characters").mkdir()
    (context_dir / "characters" / "one.md").write_text("# One\n\nCharacter.")
    return tmp_path


def test_tts_parser_accepts_flags() -> None:
    """Parser accepts --tts, --no-tts, --tts-provider, --tts-voice."""
    parser = create_parser()
    args = parser.parse_args(
        [
            "run",
            "--app",
            "a",
            "--seed",
            "s",
            "--no-tts",
            "--tts-provider",
            "custom",
            "--tts-voice",
            "Nova",
        ]
    )
    assert getattr(args, "no_tts", None) is True
    assert getattr(args, "tts_provider", None) == "custom"
    assert getattr(args, "tts_voice", None) == "Nova"


def test_tts_default_enabled(
    temp_app_minimal: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Default (no --no-tts) passes tts_enabled=True and non-None resolved_tts_config."""
    monkeypatch.chdir(temp_app_minimal)
    captured: dict = {}

    def capture_run_pipeline(**kwargs: object) -> int:
        captured.clear()
        captured.update(kwargs)
        return 0

    with patch("llm_storytell.cli._run_pipeline", side_effect=capture_run_pipeline):
        exit_code = main(
            [
                "run",
                "--app",
                "test-app",
                "--seed",
                "A story.",
                "--beats",
                "1",
                "--run-id",
                "tts-default-run",
            ]
        )

    assert exit_code == 0
    assert captured.get("tts_enabled") is True
    assert captured.get("resolved_tts_config") is not None
    rtc = captured["resolved_tts_config"]
    assert rtc.get("tts_provider") == "openai"
    assert rtc.get("tts_voice") == "Onyx"


def test_no_tts_disables(
    temp_app_minimal: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--no-tts passes tts_enabled=False and resolved_tts_config=None."""
    monkeypatch.chdir(temp_app_minimal)
    captured: dict = {}

    def capture_run_pipeline(**kwargs: object) -> int:
        captured.clear()
        captured.update(kwargs)
        return 0

    with patch("llm_storytell.cli._run_pipeline", side_effect=capture_run_pipeline):
        exit_code = main(
            [
                "run",
                "--app",
                "test-app",
                "--seed",
                "A story.",
                "--beats",
                "1",
                "--no-tts",
                "--run-id",
                "no-tts-run",
            ]
        )

    assert exit_code == 0
    assert captured.get("tts_enabled") is False
    assert captured.get("resolved_tts_config") is None


def test_tts_provider_voice_override(
    temp_app_minimal: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--tts-provider and --tts-voice override app config (CLI wins)."""
    monkeypatch.chdir(temp_app_minimal)
    captured: dict = {}

    def capture_run_pipeline(**kwargs: object) -> int:
        captured.clear()
        captured.update(kwargs)
        return 0

    with patch("llm_storytell.cli._run_pipeline", side_effect=capture_run_pipeline):
        exit_code = main(
            [
                "run",
                "--app",
                "test-app",
                "--seed",
                "A story.",
                "--beats",
                "1",
                "--tts-provider",
                "custom-provider",
                "--tts-voice",
                "CustomVoice",
                "--run-id",
                "override-run",
            ]
        )

    assert exit_code == 0
    assert captured.get("tts_enabled") is True
    rtc = captured.get("resolved_tts_config")
    assert rtc is not None
    assert rtc.get("tts_provider") == "custom-provider"
    assert rtc.get("tts_voice") == "CustomVoice"


def test_tts_and_no_tts_no_tts_wins(
    temp_app_minimal: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When both --tts and --no-tts are given, --no-tts wins (pipeline ends after critic)."""
    monkeypatch.chdir(temp_app_minimal)
    captured: dict = {}

    def capture_run_pipeline(**kwargs: object) -> int:
        captured.clear()
        captured.update(kwargs)
        return 0

    with patch("llm_storytell.cli._run_pipeline", side_effect=capture_run_pipeline):
        exit_code = main(
            [
                "run",
                "--app",
                "test-app",
                "--seed",
                "A story.",
                "--beats",
                "1",
                "--tts",
                "--no-tts",
                "--run-id",
                "conflict-run",
            ]
        )

    assert exit_code == 0
    assert captured.get("tts_enabled") is False
    assert captured.get("resolved_tts_config") is None


def test_update_state_selected_context_atomic_write(tmp_path: Path) -> None:
    """_update_state_selected_context uses atomic write (temp file + rename); no partial state.json."""
    run_dir = tmp_path / "runs" / "run-001"
    run_dir.mkdir(parents=True)
    state_path = run_dir / "state.json"
    initial_state = {
        "app": "test-app",
        "seed": "A seed.",
        "selected_context": {"location": None, "characters": [], "world_files": []},
        "outline": [],
        "token_usage": [],
    }
    state_path.write_text(json.dumps(initial_state, indent=2), encoding="utf-8")

    selected_context = {
        "location": "city.md",
        "characters": ["hero.md", "villain.md"],
        "world_files": ["world.md"],
    }
    _update_state_selected_context(run_dir, selected_context)

    with state_path.open(encoding="utf-8") as f:
        state = json.load(f)
    assert state["selected_context"] == selected_context
    # No temp file left behind
    tmp_files = list(run_dir.glob("*.tmp"))
    assert len(tmp_files) == 0
