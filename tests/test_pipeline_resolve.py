"""Tests for pipeline resolve_run_settings and RunSettings."""

from pathlib import Path

from llm_storytell.config import AppConfig, AppPaths
from llm_storytell.pipeline.resolve import RunSettings, resolve_run_settings


def _minimal_app_paths(tmp_path: Path) -> AppPaths:
    context_dir = tmp_path / "apps" / "test-app" / "context"
    context_dir.mkdir(parents=True)
    prompts_dir = tmp_path / "prompts" / "app-defaults"
    prompts_dir.mkdir(parents=True)
    return AppPaths(
        app_name="test-app",
        context_dir=context_dir,
        prompts_dir=prompts_dir,
        app_root=tmp_path / "apps" / "test-app",
    )


def _minimal_app_config(
    beats: int = 5,
    section_length: str = "400-600",
    model: str = "gpt-4.1-mini",
    tts_provider: str = "openai",
    tts_voice: str = "Onyx",
) -> AppConfig:
    return AppConfig(
        beats=beats,
        section_length=section_length,
        max_characters=3,
        max_locations=1,
        include_world=True,
        llm_provider="openai",
        model=model,
        tts_provider=tts_provider,
        tts_model="gpt-4o-mini-tts",
        tts_voice=tts_voice,
        tts_arguments=None,
        bg_music=None,
    )


class TestResolveRunSettings:
    """Tests for resolve_run_settings."""

    def test_beats_from_arg(self, tmp_path: Path) -> None:
        """beats_arg is used when provided."""
        app_paths = _minimal_app_paths(tmp_path)
        app_config = _minimal_app_config(beats=5)
        settings = resolve_run_settings(
            app_paths,
            app_config,
            "A seed.",
            beats_arg=3,
            config_path=tmp_path / "config",
        )
        assert settings.beats == 3
        assert (
            settings.section_length == "400-600"
        )  # from app_config (no section_length_arg)

    def test_beats_from_app_config_when_none(self, tmp_path: Path) -> None:
        """When beats_arg and sections_arg are None, app_config.beats is used."""
        app_paths = _minimal_app_paths(tmp_path)
        app_config = _minimal_app_config(beats=7)
        settings = resolve_run_settings(
            app_paths,
            app_config,
            "A seed.",
            config_path=tmp_path / "config",
        )
        assert settings.beats == 7

    def test_sections_arg_used_when_beats_arg_none(self, tmp_path: Path) -> None:
        """sections_arg is used when beats_arg is None."""
        app_paths = _minimal_app_paths(tmp_path)
        app_config = _minimal_app_config(beats=5)
        settings = resolve_run_settings(
            app_paths,
            app_config,
            "A seed.",
            sections_arg=2,
            config_path=tmp_path / "config",
        )
        assert settings.beats == 2

    def test_word_count_derives_beats_and_section_length(self, tmp_path: Path) -> None:
        """When word_count is set and beats_arg None, beats and section_length are derived."""
        app_paths = _minimal_app_paths(tmp_path)
        app_config = _minimal_app_config(beats=5, section_length="400-600")
        settings = resolve_run_settings(
            app_paths,
            app_config,
            "A seed.",
            word_count=2000,
            config_path=tmp_path / "config",
        )
        # baseline midpoint 500 -> beats = round(2000/500) = 4, section_length_per = 500
        assert settings.beats == 4
        assert settings.section_length == "400-600"

    def test_word_count_with_beats_validates_ratio(self, tmp_path: Path) -> None:
        """When both word_count and beats_arg set, section_length is derived from ratio."""
        app_paths = _minimal_app_paths(tmp_path)
        app_config = _minimal_app_config(beats=5)
        settings = resolve_run_settings(
            app_paths,
            app_config,
            "A seed.",
            beats_arg=4,
            word_count=2000,
            config_path=tmp_path / "config",
        )
        assert settings.beats == 4
        # 2000/4 = 500 per section -> 0.8*500=400, 1.2*500=600
        assert settings.section_length == "400-600"

    def test_model_from_arg(self, tmp_path: Path) -> None:
        """model_arg overrides app_config.model."""
        app_paths = _minimal_app_paths(tmp_path)
        app_config = _minimal_app_config(model="gpt-4.1-mini")
        settings = resolve_run_settings(
            app_paths,
            app_config,
            "A seed.",
            beats_arg=1,
            model_arg="gpt-4o",
            config_path=tmp_path / "config",
        )
        assert settings.model == "gpt-4o"

    def test_model_from_app_config_when_arg_none(self, tmp_path: Path) -> None:
        """When model_arg is None, app_config.model is used."""
        app_paths = _minimal_app_paths(tmp_path)
        app_config = _minimal_app_config(model="gpt-4o")
        settings = resolve_run_settings(
            app_paths,
            app_config,
            "A seed.",
            beats_arg=1,
            config_path=tmp_path / "config",
        )
        assert settings.model == "gpt-4o"

    def test_tts_disabled_resolved_tts_config_none(self, tmp_path: Path) -> None:
        """When tts_enabled is False, resolved_tts_config is None."""
        app_paths = _minimal_app_paths(tmp_path)
        app_config = _minimal_app_config()
        settings = resolve_run_settings(
            app_paths,
            app_config,
            "A seed.",
            beats_arg=1,
            tts_enabled=False,
            config_path=tmp_path / "config",
        )
        assert settings.tts_enabled is False
        assert settings.resolved_tts_config is None

    def test_tts_enabled_resolved_tts_config_has_provider_voice(
        self, tmp_path: Path
    ) -> None:
        """When tts_enabled is True, resolved_tts_config has tts_provider and tts_voice."""
        app_paths = _minimal_app_paths(tmp_path)
        app_config = _minimal_app_config(tts_provider="openai", tts_voice="Onyx")
        settings = resolve_run_settings(
            app_paths,
            app_config,
            "A seed.",
            beats_arg=1,
            tts_enabled=True,
            tts_provider="custom",
            tts_voice="Nova",
            config_path=tmp_path / "config",
        )
        assert settings.tts_enabled is True
        assert settings.resolved_tts_config is not None
        assert settings.resolved_tts_config.get("tts_provider") == "custom"
        assert settings.resolved_tts_config.get("tts_voice") == "Nova"

    def test_run_settings_has_all_expected_attrs(self, tmp_path: Path) -> None:
        """RunSettings has app_paths, app_config, seed, beats, section_length, run_id, config_path, model, word_count, tts_enabled, resolved_tts_config."""
        app_paths = _minimal_app_paths(tmp_path)
        app_config = _minimal_app_config()
        settings = resolve_run_settings(
            app_paths,
            app_config,
            "A seed.",
            beats_arg=1,
            run_id="run-001",
            config_path=tmp_path / "config",
        )
        assert isinstance(settings, RunSettings)
        assert settings.app_paths is app_paths
        assert settings.app_config is app_config
        assert settings.seed == "A seed."
        assert settings.beats == 1
        assert settings.run_id == "run-001"
        assert settings.config_path == tmp_path / "config"
        assert settings.word_count is None
