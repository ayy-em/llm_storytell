"""Tests for app resolution functionality."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "llm_storytell"))

from config.app_resolver import AppNotFoundError, resolve_app


class TestResolveApp:
    """Tests for the resolve_app function."""

    def test_resolves_from_apps_when_only_lore_bible_exists(
        self, tmp_path: Path
    ) -> None:
        """App under apps/<app>/ is valid with only context/lore_bible.md; prompts use app-defaults."""
        app_name = "my-app"
        apps_context = tmp_path / "apps" / app_name / "context"
        apps_context.mkdir(parents=True)
        (apps_context / "lore_bible.md").write_text("# Lore")
        app_defaults = tmp_path / "prompts" / "app-defaults"
        app_defaults.mkdir(parents=True)

        result = resolve_app(app_name, tmp_path)

        assert result.app_name == app_name
        assert result.context_dir == apps_context
        assert result.prompts_dir == app_defaults
        assert result.app_root == tmp_path / "apps" / app_name

    def test_resolves_from_apps_with_prompts_dir(self, tmp_path: Path) -> None:
        """App under apps/<app>/ with prompts/ uses that prompts directory."""
        app_name = "my-app"
        apps_context = tmp_path / "apps" / app_name / "context"
        apps_context.mkdir(parents=True)
        (apps_context / "lore_bible.md").write_text("# Lore")
        apps_prompts = tmp_path / "apps" / app_name / "prompts"
        apps_prompts.mkdir(parents=True)

        result = resolve_app(app_name, tmp_path)

        assert result.app_name == app_name
        assert result.context_dir == apps_context
        assert result.prompts_dir == apps_prompts
        assert result.app_root == tmp_path / "apps" / app_name

    def test_nonexistent_app_raises_with_apps_message(self, tmp_path: Path) -> None:
        """Non-existent app raises AppNotFoundError with message mentioning apps/ only."""
        with pytest.raises(AppNotFoundError) as exc_info:
            resolve_app("nonexistent-app", tmp_path)

        error_msg = str(exc_info.value)
        assert "nonexistent-app" in error_msg
        assert "apps/" in error_msg
        assert "context/nonexistent-app/" not in error_msg
        assert "prompts/apps/" not in error_msg

    def test_app_missing_lore_bible_raises(self, tmp_path: Path) -> None:
        """App dir without context/lore_bible.md raises AppNotFoundError."""
        app_name = "no-lore"
        (tmp_path / "apps" / app_name / "context").mkdir(parents=True)
        # no lore_bible.md

        with pytest.raises(AppNotFoundError) as exc_info:
            resolve_app(app_name, tmp_path)

        error_msg = str(exc_info.value)
        assert app_name in error_msg
        assert "lore_bible.md" in error_msg

    def test_empty_app_name_raises_error(self, tmp_path: Path) -> None:
        """Test that empty app name raises AppNotFoundError."""
        with pytest.raises(AppNotFoundError) as exc_info:
            resolve_app("", tmp_path)

        assert "empty" in str(exc_info.value).lower()

    def test_whitespace_app_name_raises_error(self, tmp_path: Path) -> None:
        """Test that whitespace-only app name raises AppNotFoundError."""
        with pytest.raises(AppNotFoundError) as exc_info:
            resolve_app("   ", tmp_path)

        assert "empty" in str(exc_info.value).lower()

    def test_app_name_is_stripped(self, tmp_path: Path) -> None:
        """Test that app name whitespace is stripped."""
        app_name = "my-app"
        apps_context = tmp_path / "apps" / app_name / "context"
        apps_context.mkdir(parents=True)
        (apps_context / "lore_bible.md").write_text("# Lore")
        (tmp_path / "prompts" / "app-defaults").mkdir(parents=True)

        result = resolve_app("  my-app  ", tmp_path)

        assert result.app_name == app_name

    def test_app_paths_is_frozen(self, tmp_path: Path) -> None:
        """Test that AppPaths is immutable."""
        app_name = "my-app"
        apps_context = tmp_path / "apps" / app_name / "context"
        apps_context.mkdir(parents=True)
        (apps_context / "lore_bible.md").write_text("# Lore")
        (tmp_path / "prompts" / "app-defaults").mkdir(parents=True)

        result = resolve_app(app_name, tmp_path)

        with pytest.raises(AttributeError):
            result.app_name = "other-app"  # type: ignore[misc]


class TestAppNotFoundError:
    """Tests for the AppNotFoundError exception."""

    def test_error_includes_app_name(self, tmp_path: Path) -> None:
        """Test that error message includes the app name."""
        app_name = "my-special-app"
        with pytest.raises(AppNotFoundError) as exc_info:
            resolve_app(app_name, tmp_path)

        assert app_name in str(exc_info.value)

    def test_error_includes_base_dir(self, tmp_path: Path) -> None:
        """Test that error message includes the base directory."""
        with pytest.raises(AppNotFoundError) as exc_info:
            resolve_app("some-app", tmp_path)

        assert str(tmp_path) in str(exc_info.value)
