"""Tests for app resolution functionality."""

import pytest

from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "llm_storytell"))

from config.app_resolver import AppNotFoundError, AppPaths, resolve_app


class TestResolveApp:
    """Tests for the resolve_app function."""

    def test_valid_app_returns_correct_paths(self, tmp_path: Path) -> None:
        """Test that a valid app returns correct AppPaths."""
        # Setup: create both required directories
        app_name = "test-app"
        context_dir = tmp_path / "context" / app_name
        prompts_dir = tmp_path / "prompts" / "apps" / app_name
        context_dir.mkdir(parents=True)
        prompts_dir.mkdir(parents=True)

        # Execute
        result = resolve_app(app_name, tmp_path)

        # Verify (legacy layout: app_root is None)
        assert isinstance(result, AppPaths)
        assert result.app_name == app_name
        assert result.context_dir == context_dir
        assert result.prompts_dir == prompts_dir
        assert result.app_root is None

    def test_invalid_app_name_raises_error(self, tmp_path: Path) -> None:
        """Test that a non-existent app raises AppNotFoundError."""
        # Execute & Verify
        with pytest.raises(AppNotFoundError) as exc_info:
            resolve_app("nonexistent-app", tmp_path)

        # Check error message is actionable (mentions missing paths or apps/ option)
        error_msg = str(exc_info.value)
        assert "nonexistent-app" in error_msg
        assert "context/nonexistent-app/" in error_msg
        assert "prompts/apps/nonexistent-app/" in error_msg

    def test_missing_context_dir_raises_error(self, tmp_path: Path) -> None:
        """Test that missing context directory raises AppNotFoundError."""
        # Setup: create only prompts directory
        app_name = "partial-app"
        prompts_dir = tmp_path / "prompts" / "apps" / app_name
        prompts_dir.mkdir(parents=True)

        # Execute & Verify
        with pytest.raises(AppNotFoundError) as exc_info:
            resolve_app(app_name, tmp_path)

        error_msg = str(exc_info.value)
        assert f"context/{app_name}/" in error_msg

    def test_missing_prompts_dir_raises_error(self, tmp_path: Path) -> None:
        """Test that missing prompts directory raises AppNotFoundError."""
        # Setup: create only context directory
        app_name = "partial-app"
        context_dir = tmp_path / "context" / app_name
        context_dir.mkdir(parents=True)

        # Execute & Verify
        with pytest.raises(AppNotFoundError) as exc_info:
            resolve_app(app_name, tmp_path)

        error_msg = str(exc_info.value)
        assert f"prompts/apps/{app_name}/" in error_msg

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
        # Setup
        app_name = "test-app"
        context_dir = tmp_path / "context" / app_name
        prompts_dir = tmp_path / "prompts" / "apps" / app_name
        context_dir.mkdir(parents=True)
        prompts_dir.mkdir(parents=True)

        # Execute with whitespace
        result = resolve_app("  test-app  ", tmp_path)

        # Verify whitespace was stripped
        assert result.app_name == app_name

    def test_app_paths_is_frozen(self, tmp_path: Path) -> None:
        """Test that AppPaths is immutable."""
        # Setup
        app_name = "test-app"
        context_dir = tmp_path / "context" / app_name
        prompts_dir = tmp_path / "prompts" / "apps" / app_name
        context_dir.mkdir(parents=True)
        prompts_dir.mkdir(parents=True)

        result = resolve_app(app_name, tmp_path)

        # Verify immutability
        with pytest.raises(AttributeError):
            result.app_name = "other-app"  # type: ignore[misc]

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

    def test_apps_preferred_over_legacy(self, tmp_path: Path) -> None:
        """When both apps/<app>/ and legacy layout exist, apps/ is used."""
        app_name = "my-app"
        apps_context = tmp_path / "apps" / app_name / "context"
        apps_context.mkdir(parents=True)
        (apps_context / "lore_bible.md").write_text("# Lore (apps)")
        legacy_context = tmp_path / "context" / app_name
        legacy_context.mkdir(parents=True)
        (tmp_path / "prompts" / "app-defaults").mkdir(parents=True)

        result = resolve_app(app_name, tmp_path)

        assert result.context_dir == apps_context
        assert result.app_root is not None


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
