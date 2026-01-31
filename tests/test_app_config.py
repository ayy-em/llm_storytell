"""Tests for app config loading and merging."""

import pytest

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "llm_storytell"))

from config.app_config import (
    AppConfig,
    AppConfigError,
    load_app_config,
)


class TestLoadAppConfig:
    """Tests for load_app_config."""

    def test_loads_defaults_only_when_no_app_config(self, tmp_path: Path) -> None:
        """When only apps/default_config.yaml exists, returns default values."""
        apps_dir = tmp_path / "apps"
        apps_dir.mkdir()
        default_path = apps_dir / "default_config.yaml"
        default_path.write_text(
            "beats: 7\n"
            "section_length: '300-500'\n"
            "max_characters: 2\n"
            "max_locations: 1\n"
            "include_world: false\n"
            "llm_provider: openai\n"
            "model: gpt-4.1-mini\n"
        )

        result = load_app_config("any-app", base_dir=tmp_path)

        assert isinstance(result, AppConfig)
        assert result.beats == 7
        assert result.section_length == "300-500"
        assert result.max_characters == 2
        assert result.max_locations == 1
        assert result.include_world is False
        assert result.llm_provider == "openai"
        assert result.model == "gpt-4.1-mini"

    def test_merges_app_override_with_defaults(self, tmp_path: Path) -> None:
        """App app_config.yaml overrides defaults for specified keys."""
        apps_dir = tmp_path / "apps"
        apps_dir.mkdir()
        (apps_dir / "default_config.yaml").write_text(
            "beats: 5\n"
            "section_length: '400-600'\n"
            "max_characters: 3\n"
            "max_locations: 1\n"
            "include_world: true\n"
            "llm_provider: openai\n"
            "model: gpt-4.1-mini\n"
        )
        app_dir = apps_dir / "my-app"
        app_dir.mkdir()
        (app_dir / "app_config.yaml").write_text("beats: 10\nmodel: gpt-4.1\n")

        result = load_app_config("my-app", base_dir=tmp_path)

        assert result.beats == 10
        assert result.model == "gpt-4.1"
        assert result.section_length == "400-600"
        assert result.max_characters == 3

    def test_missing_default_config_uses_builtin_defaults(self, tmp_path: Path) -> None:
        """When apps/default_config.yaml does not exist, uses built-in defaults (legacy/e2e)."""
        result = load_app_config("any-app", base_dir=tmp_path)

        assert result.beats == 5
        assert result.section_length == "400-600"
        assert result.max_characters == 3
        assert result.model == "gpt-4.1-mini"

    def test_invalid_default_yaml_raises(self, tmp_path: Path) -> None:
        """When default config is invalid YAML, raises AppConfigError."""
        apps_dir = tmp_path / "apps"
        apps_dir.mkdir()
        (apps_dir / "default_config.yaml").write_text("invalid: [unclosed")

        with pytest.raises(AppConfigError) as exc_info:
            load_app_config("any-app", base_dir=tmp_path)

        assert (
            "invalid" in str(exc_info.value).lower()
            or "yaml" in str(exc_info.value).lower()
        )

    def test_uses_app_root_when_provided(self, tmp_path: Path) -> None:
        """When app_root is provided, app_config.yaml is read from app_root."""
        apps_dir = tmp_path / "apps"
        apps_dir.mkdir()
        (apps_dir / "default_config.yaml").write_text(
            "beats: 5\n"
            "section_length: '400-600'\n"
            "max_characters: 3\n"
            "max_locations: 1\n"
            "include_world: true\n"
            "llm_provider: openai\n"
            "model: gpt-4.1-mini\n"
        )
        app_root = apps_dir / "custom-app"
        app_root.mkdir()
        (app_root / "app_config.yaml").write_text("beats: 12\n")

        result = load_app_config(
            "custom-app",
            base_dir=tmp_path,
            app_root=app_root,
        )

        assert result.beats == 12

    def test_empty_default_config_raises(self, tmp_path: Path) -> None:
        """When default config file is empty or not a dict, raises AppConfigError."""
        apps_dir = tmp_path / "apps"
        apps_dir.mkdir()
        (apps_dir / "default_config.yaml").write_text("")

        with pytest.raises(AppConfigError) as exc_info:
            load_app_config("any-app", base_dir=tmp_path)

        assert (
            "empty" in str(exc_info.value).lower()
            or "invalid" in str(exc_info.value).lower()
        )


class TestAppConfig:
    """Tests for AppConfig dataclass."""

    def test_app_config_is_frozen(self) -> None:
        """AppConfig is immutable."""
        config = AppConfig(
            beats=5,
            section_length="400-600",
            max_characters=3,
            max_locations=1,
            include_world=True,
            llm_provider="openai",
            model="gpt-4.1-mini",
        )
        with pytest.raises(AttributeError):
            config.beats = 10  # type: ignore[misc]
