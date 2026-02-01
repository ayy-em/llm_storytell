"""Tests for app config TTS/audio loading and state persistence."""

import json
from pathlib import Path

from llm_storytell.config.app_config import AppConfig, load_app_config
from llm_storytell.run_dir import initialize_run


def _defaults_yaml() -> str:
    return (
        "beats: 5\n"
        "section_length: '400-600'\n"
        "max_characters: 3\n"
        "max_locations: 1\n"
        "include_world: true\n"
        "llm_provider: openai\n"
        "model: gpt-4.1-mini\n"
    )


class TestTTSConfigFull:
    """Full TTS/audio config: all optional keys set in app_config.yaml."""

    def test_full_tts_config_from_yaml(self, tmp_path: Path) -> None:
        """When app_config.yaml has all TTS keys, AppConfig and resolved_tts_config match."""
        apps_dir = tmp_path / "apps"
        apps_dir.mkdir()
        (apps_dir / "default_config.yaml").write_text(_defaults_yaml())
        app_dir = apps_dir / "my-app"
        app_dir.mkdir()
        (app_dir / "app_config.yaml").write_text(
            "tts-provider: custom\n"
            "tts-model: custom-model-tts\n"
            "tts-voice: Nova\n"
            "tts-arguments:\n"
            "  speed: 1.1\n"
            "  pitch: 0\n"
            "bg-music: assets/my-bg.wav\n"
        )

        result = load_app_config("my-app", base_dir=tmp_path)

        assert result.tts_provider == "custom"
        assert result.tts_model == "custom-model-tts"
        assert result.tts_voice == "Nova"
        assert result.tts_arguments == {"speed": 1.1, "pitch": 0}
        assert result.bg_music == "assets/my-bg.wav"

        resolved = result.resolved_tts_config()
        assert resolved["tts_provider"] == "custom"
        assert resolved["tts_model"] == "custom-model-tts"
        assert resolved["tts_voice"] == "Nova"
        assert resolved["tts_arguments"] == {"speed": 1.1, "pitch": 0}
        assert resolved["bg_music"] == "assets/my-bg.wav"


class TestTTSConfigPartial:
    """Partial TTS config: some keys set, rest use defaults."""

    def test_partial_tts_config_uses_defaults(self, tmp_path: Path) -> None:
        """When only some TTS keys are set, rest come from defaults."""
        apps_dir = tmp_path / "apps"
        apps_dir.mkdir()
        (apps_dir / "default_config.yaml").write_text(_defaults_yaml())
        app_dir = apps_dir / "my-app"
        app_dir.mkdir()
        (app_dir / "app_config.yaml").write_text(
            "tts-voice: Alloy\nbg-music: music/ambient.wav\n"
        )

        result = load_app_config("my-app", base_dir=tmp_path)

        assert result.tts_provider == "openai"
        assert result.tts_model == "gpt-4o-mini-tts"
        assert result.tts_voice == "Alloy"
        assert result.tts_arguments is None
        assert result.bg_music == "music/ambient.wav"

        resolved = result.resolved_tts_config()
        assert resolved["tts_provider"] == "openai"
        assert resolved["tts_model"] == "gpt-4o-mini-tts"
        assert resolved["tts_voice"] == "Alloy"
        assert resolved["tts_arguments"] == {}
        assert resolved["bg_music"] == "music/ambient.wav"


class TestTTSConfigEmpty:
    """Empty TTS config: no TTS keys in app or defaults; all use built-in defaults."""

    def test_empty_tts_config_uses_builtin_defaults(self, tmp_path: Path) -> None:
        """When no TTS keys in YAML, all TTS fields use built-in defaults; run does not fail."""
        apps_dir = tmp_path / "apps"
        apps_dir.mkdir()
        (apps_dir / "default_config.yaml").write_text(_defaults_yaml())
        app_dir = apps_dir / "minimal-app"
        app_dir.mkdir()
        (app_dir / "app_config.yaml").write_text("# Optional overrides\n")

        result = load_app_config("minimal-app", base_dir=tmp_path)

        assert result.tts_provider == "openai"
        assert result.tts_model == "gpt-4o-mini-tts"
        assert result.tts_voice == "Onyx"
        assert result.tts_arguments is None
        assert result.bg_music is None

        resolved = result.resolved_tts_config()
        assert resolved["tts_provider"] == "openai"
        assert resolved["tts_model"] == "gpt-4o-mini-tts"
        assert resolved["tts_voice"] == "Onyx"
        assert resolved["tts_arguments"] == {}
        assert resolved["bg_music"] is None

    def test_no_app_config_tts_defaults_only(self, tmp_path: Path) -> None:
        """When app has no app_config.yaml, TTS defaults come from default_config or built-in."""
        apps_dir = tmp_path / "apps"
        apps_dir.mkdir()
        (apps_dir / "default_config.yaml").write_text(_defaults_yaml())
        app_dir = apps_dir / "no-overrides"
        app_dir.mkdir()
        # No app_config.yaml

        result = load_app_config("no-overrides", base_dir=tmp_path)

        assert result.tts_provider == "openai"
        assert result.tts_model == "gpt-4o-mini-tts"
        assert result.tts_voice == "Onyx"
        assert result.resolved_tts_config()["tts_arguments"] == {}


class TestTTSConfigStatePersistence:
    """Resolved TTS config is persisted to state.json when provided to initialize_run."""

    def test_resolved_tts_config_persisted_to_state(self, tmp_path: Path) -> None:
        """When resolved_tts_config is passed to initialize_run, state.json contains tts_config."""
        apps_dir = tmp_path / "apps"
        apps_dir.mkdir()
        (apps_dir / "default_config.yaml").write_text(_defaults_yaml())
        app_dir = apps_dir / "my-app"
        app_dir.mkdir()
        (app_dir / "app_config.yaml").write_text("tts-voice: Shimmer\n")
        context_dir = tmp_path / "context"
        context_dir.mkdir()
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()

        config = load_app_config("my-app", base_dir=tmp_path)
        resolved = config.resolved_tts_config()

        run_dir = initialize_run(
            app_name="my-app",
            seed="test seed",
            context_dir=context_dir,
            prompts_dir=prompts_dir,
            beats=5,
            base_dir=tmp_path,
            run_id="run-test-tts",
            resolved_tts_config=resolved,
        )

        state_path = run_dir / "state.json"
        assert state_path.exists()
        with state_path.open(encoding="utf-8") as f:
            state = json.load(f)

        assert "tts_config" in state
        assert state["tts_config"]["tts_provider"] == "openai"
        assert state["tts_config"]["tts_model"] == "gpt-4o-mini-tts"
        assert state["tts_config"]["tts_voice"] == "Shimmer"
        assert state["tts_config"]["tts_arguments"] == {}
        assert state["tts_config"]["bg_music"] is None

    def test_initialize_run_without_resolved_tts_config_no_tts_in_state(
        self, tmp_path: Path
    ) -> None:
        """When resolved_tts_config is not passed, state.json does not contain tts_config."""
        context_dir = tmp_path / "context"
        context_dir.mkdir()
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()

        run_dir = initialize_run(
            app_name="any-app",
            seed="test seed",
            context_dir=context_dir,
            prompts_dir=prompts_dir,
            beats=5,
            base_dir=tmp_path,
            run_id="run-no-tts",
        )

        state_path = run_dir / "state.json"
        with state_path.open(encoding="utf-8") as f:
            state = json.load(f)

        assert "tts_config" not in state


class TestAppConfigResolvedTTS:
    """AppConfig.resolved_tts_config() behavior."""

    def test_resolved_tts_config_serializable(self) -> None:
        """resolved_tts_config() is JSON-serializable."""
        config = AppConfig(
            beats=5,
            section_length="400-600",
            max_characters=3,
            max_locations=1,
            include_world=True,
            llm_provider="openai",
            model="gpt-4.1-mini",
            tts_provider="openai",
            tts_model="gpt-4o-mini-tts",
            tts_voice="Onyx",
            tts_arguments={"extra": 1},
            bg_music="path/to/music.wav",
        )
        resolved = config.resolved_tts_config()
        # Must not raise
        json_str = json.dumps(resolved)
        back = json.loads(json_str)
        assert back == resolved

    def test_resolved_tts_config_none_arguments_becomes_empty_dict(self) -> None:
        """When tts_arguments is None, resolved_tts_config() exposes {}."""
        config = AppConfig(
            beats=5,
            section_length="400-600",
            max_characters=3,
            max_locations=1,
            include_world=True,
            llm_provider="openai",
            model="gpt-4.1-mini",
        )
        resolved = config.resolved_tts_config()
        assert resolved["tts_arguments"] == {}
