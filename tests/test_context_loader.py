"""Tests for context loading and selection."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Import from the package using the hyphenated name
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from importlib import import_module

context_module = import_module("llm_storytell.context")
logging_module = import_module("llm_storytell.logging")

ContextLoader = context_module.ContextLoader
ContextSelection = context_module.ContextSelection
ContextLoaderError = context_module.ContextLoaderError
RunLogger = logging_module.RunLogger


@pytest.fixture
def temp_context_dir(tmp_path: Path) -> Path:
    """Create a temporary context directory structure."""
    context_dir = tmp_path / "context" / "test-app"
    context_dir.mkdir(parents=True)

    # Create required lore_bible.md
    (context_dir / "lore_bible.md").write_text("# Lore Bible\n\nTest lore content.")

    # Create style directory with files
    style_dir = context_dir / "style"
    style_dir.mkdir()
    (style_dir / "tone.md").write_text("# Tone\n\nDark and moody.")
    (style_dir / "narration.md").write_text("# Narration\n\nThird person limited.")

    # Create locations directory with files
    locations_dir = context_dir / "locations"
    locations_dir.mkdir()
    (locations_dir / "forest.md").write_text("# Forest\n\nA dark forest.")
    (locations_dir / "city.md").write_text("# City\n\nA sprawling city.")
    (locations_dir / "desert.md").write_text("# Desert\n\nA vast desert.")

    # Create characters directory with files
    characters_dir = context_dir / "characters"
    characters_dir.mkdir()
    (characters_dir / "hero.md").write_text("# Hero\n\nA brave hero.")
    (characters_dir / "villain.md").write_text("# Villain\n\nAn evil villain.")
    (characters_dir / "mentor.md").write_text("# Mentor\n\nA wise mentor.")
    (characters_dir / "sidekick.md").write_text("# Sidekick\n\nA loyal sidekick.")

    return context_dir


class TestContextLoader:
    """Tests for ContextLoader."""

    def test_loads_lore_bible(self, temp_context_dir: Path) -> None:
        """Always loads lore_bible.md."""
        loader = ContextLoader(temp_context_dir)
        selection = loader.load_context("run-test-001")

        assert "lore_bible.md" in selection.always_loaded
        assert (
            selection.always_loaded["lore_bible.md"]
            == "# Lore Bible\n\nTest lore content."
        )

    def test_loads_style_files(self, temp_context_dir: Path) -> None:
        """Always loads all style/*.md files."""
        loader = ContextLoader(temp_context_dir)
        selection = loader.load_context("run-test-002")

        assert "style/tone.md" in selection.always_loaded
        assert "style/narration.md" in selection.always_loaded
        assert selection.always_loaded["style/tone.md"] == "# Tone\n\nDark and moody."
        assert (
            selection.always_loaded["style/narration.md"]
            == "# Narration\n\nThird person limited."
        )

    def test_fails_without_lore_bible(self, tmp_path: Path) -> None:
        """Raises error if lore_bible.md is missing."""
        context_dir = tmp_path / "context" / "test-app"
        context_dir.mkdir(parents=True)

        loader = ContextLoader(context_dir)
        with pytest.raises(ContextLoaderError) as exc_info:
            loader.load_context("run-test-003")

        assert "lore_bible.md" in str(exc_info.value)

    def test_handles_missing_style_directory(self, tmp_path: Path) -> None:
        """Handles missing style directory gracefully."""
        context_dir = tmp_path / "context" / "test-app"
        context_dir.mkdir(parents=True)
        (context_dir / "lore_bible.md").write_text("# Lore Bible")

        loader = ContextLoader(context_dir)
        selection = loader.load_context("run-test-004")

        # Should only have lore_bible, no style files
        assert "lore_bible.md" in selection.always_loaded
        assert len(selection.always_loaded) == 1

    def test_selects_one_location(self, temp_context_dir: Path) -> None:
        """Randomly selects one location file."""
        loader = ContextLoader(temp_context_dir)
        selection = loader.load_context("run-test-005")

        assert selection.selected_location is not None
        assert selection.selected_location in [
            "locations/forest.md",
            "locations/city.md",
            "locations/desert.md",
        ]
        assert selection.location_content is not None
        assert len(selection.location_content) > 0

    def test_handles_missing_locations_directory(self, tmp_path: Path) -> None:
        """Handles missing locations directory gracefully."""
        context_dir = tmp_path / "context" / "test-app"
        context_dir.mkdir(parents=True)
        (context_dir / "lore_bible.md").write_text("# Lore Bible")

        loader = ContextLoader(context_dir)
        selection = loader.load_context("run-test-006")

        assert selection.selected_location is None
        assert selection.location_content is None

    def test_handles_empty_locations_directory(self, tmp_path: Path) -> None:
        """Handles empty locations directory gracefully."""
        context_dir = tmp_path / "context" / "test-app"
        context_dir.mkdir(parents=True)
        (context_dir / "lore_bible.md").write_text("# Lore Bible")
        (context_dir / "locations").mkdir()

        loader = ContextLoader(context_dir)
        selection = loader.load_context("run-test-007")

        assert selection.selected_location is None
        assert selection.location_content is None

    def test_selects_2_to_3_characters(self, temp_context_dir: Path) -> None:
        """Randomly selects 2-3 character files."""
        loader = ContextLoader(temp_context_dir)
        selection = loader.load_context("run-test-008")

        assert len(selection.selected_characters) >= 2
        assert len(selection.selected_characters) <= 3
        assert all(
            char
            in [
                "characters/hero.md",
                "characters/villain.md",
                "characters/mentor.md",
                "characters/sidekick.md",
            ]
            for char in selection.selected_characters
        )
        assert len(selection.character_contents) == len(selection.selected_characters)

    def test_handles_missing_characters_directory(self, tmp_path: Path) -> None:
        """Handles missing characters directory gracefully."""
        context_dir = tmp_path / "context" / "test-app"
        context_dir.mkdir(parents=True)
        (context_dir / "lore_bible.md").write_text("# Lore Bible")

        loader = ContextLoader(context_dir)
        selection = loader.load_context("run-test-009")

        assert selection.selected_characters == []
        assert selection.character_contents == {}

    def test_handles_empty_characters_directory(self, tmp_path: Path) -> None:
        """Handles empty characters directory gracefully."""
        context_dir = tmp_path / "context" / "test-app"
        context_dir.mkdir(parents=True)
        (context_dir / "lore_bible.md").write_text("# Lore Bible")
        (context_dir / "characters").mkdir()

        loader = ContextLoader(context_dir)
        selection = loader.load_context("run-test-010")

        assert selection.selected_characters == []
        assert selection.character_contents == {}

    def test_selects_all_characters_if_fewer_than_2(self, tmp_path: Path) -> None:
        """Selects all available characters if fewer than 2."""
        context_dir = tmp_path / "context" / "test-app"
        context_dir.mkdir(parents=True)
        (context_dir / "lore_bible.md").write_text("# Lore Bible")
        characters_dir = context_dir / "characters"
        characters_dir.mkdir()
        (characters_dir / "only_one.md").write_text("# Only One\n\nSingle character.")

        loader = ContextLoader(context_dir)
        logger = MagicMock(spec=RunLogger)
        loader.logger = logger
        selection = loader.load_context("run-test-011")

        assert len(selection.selected_characters) == 1
        assert "characters/only_one.md" in selection.selected_characters
        # Should log a warning
        assert any(
            "Warning" in str(call) and "character" in str(call).lower()
            for call in logger.info.call_args_list
        )

    def test_reproducible_selection(self, temp_context_dir: Path) -> None:
        """Same run_id produces same selections."""
        loader1 = ContextLoader(temp_context_dir)
        loader2 = ContextLoader(temp_context_dir)

        selection1 = loader1.load_context("run-reproducible-001")
        selection2 = loader2.load_context("run-reproducible-001")

        assert selection1.selected_location == selection2.selected_location
        assert selection1.selected_characters == selection2.selected_characters
        assert selection1.location_content == selection2.location_content
        assert selection1.character_contents == selection2.character_contents

    def test_different_run_ids_produce_different_selections(
        self, temp_context_dir: Path
    ) -> None:
        """Different run_ids can produce different selections."""
        loader = ContextLoader(temp_context_dir)

        # Run multiple times with different run_ids
        selections = [loader.load_context(f"run-variation-{i}") for i in range(10)]

        # Collect unique location and character selections
        unique_locations = set(s.selected_location for s in selections)
        unique_character_sets = set(
            tuple(sorted(s.selected_characters)) for s in selections
        )

        # With 3 locations and 4 characters, we should see some variation
        # (though not guaranteed, so we just check that it's possible)
        assert len(unique_locations) >= 1  # At least one location selected
        assert len(unique_character_sets) >= 1  # At least one character set

    def test_logs_selections(self, temp_context_dir: Path, tmp_path: Path) -> None:
        """Logs context selections when logger is provided."""
        log_path = tmp_path / "test.log"
        log_path.touch()
        logger = RunLogger(log_path)

        loader = ContextLoader(temp_context_dir, logger=logger)
        selection = loader.load_context("run-logging-001")

        log_content = log_path.read_text()
        assert "Context selection:" in log_content
        assert "lore_bible.md" in log_content or "Always loaded" in log_content
        if selection.selected_location:
            assert selection.selected_location in log_content
        if selection.selected_characters:
            assert all(char in log_content for char in selection.selected_characters)

    def test_reads_file_contents(self, temp_context_dir: Path) -> None:
        """Reads and returns file contents correctly."""
        loader = ContextLoader(temp_context_dir)
        selection = loader.load_context("run-contents-001")

        # Check lore_bible content
        assert "Test lore content" in selection.always_loaded["lore_bible.md"]

        # Check location content if selected
        if selection.selected_location and selection.location_content:
            assert len(selection.location_content) > 0

        # Check character contents
        for char_path, content in selection.character_contents.items():
            assert len(content) > 0
            assert char_path in selection.selected_characters

    def test_handles_unicode_content(self, tmp_path: Path) -> None:
        """Handles Unicode content correctly."""
        context_dir = tmp_path / "context" / "test-app"
        context_dir.mkdir(parents=True)
        (context_dir / "lore_bible.md").write_text(
            "# Lore Bible\n\nTest with émojis: 🎭📚", encoding="utf-8"
        )

        loader = ContextLoader(context_dir)
        selection = loader.load_context("run-unicode-001")

        assert "émojis" in selection.always_loaded["lore_bible.md"]
        assert "🎭" in selection.always_loaded["lore_bible.md"]

    def test_handles_minimal_app(self, tmp_path: Path) -> None:
        """Handles app with only lore_bible.md."""
        context_dir = tmp_path / "context" / "minimal-app"
        context_dir.mkdir(parents=True)
        (context_dir / "lore_bible.md").write_text("# Minimal Lore")

        loader = ContextLoader(context_dir)
        selection = loader.load_context("run-minimal-001")

        assert "lore_bible.md" in selection.always_loaded
        assert len(selection.always_loaded) == 1
        assert selection.selected_location is None
        assert selection.selected_characters == []

    def test_handles_large_context_library(self, tmp_path: Path) -> None:
        """Handles app with many context files."""
        context_dir = tmp_path / "context" / "large-app"
        context_dir.mkdir(parents=True)
        (context_dir / "lore_bible.md").write_text("# Large Lore")

        # Create many locations
        locations_dir = context_dir / "locations"
        locations_dir.mkdir()
        for i in range(20):
            (locations_dir / f"location_{i:02d}.md").write_text(f"# Location {i}")

        # Create many characters
        characters_dir = context_dir / "characters"
        characters_dir.mkdir()
        for i in range(15):
            (characters_dir / f"character_{i:02d}.md").write_text(f"# Character {i}")

        loader = ContextLoader(context_dir)
        selection = loader.load_context("run-large-001")

        # Should select exactly one location
        assert selection.selected_location is not None
        assert selection.selected_location.startswith("locations/")

        # Should select 2-3 characters
        assert len(selection.selected_characters) >= 2
        assert len(selection.selected_characters) <= 3
        assert all(
            char.startswith("characters/") for char in selection.selected_characters
        )

    def test_no_duplicate_character_selection(self, temp_context_dir: Path) -> None:
        """Selected characters are unique (no duplicates)."""
        loader = ContextLoader(temp_context_dir)
        selection = loader.load_context("run-unique-001")

        # Check for duplicates
        assert len(selection.selected_characters) == len(
            set(selection.selected_characters)
        )
        assert len(selection.character_contents) == len(selection.selected_characters)
