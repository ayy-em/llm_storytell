"""Tests for context loading and selection."""

from pathlib import Path

import pytest

# Import from the package using the hyphenated name
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from importlib import import_module

context_module = import_module("llm_storytell.context")
loader_module = import_module("llm_storytell.context.loader")
logging_module = import_module("llm_storytell.logging")
config_app_config = import_module("llm_storytell.config.app_config")

ContextLoader = context_module.ContextLoader
ContextLoaderError = context_module.ContextLoaderError
ContextSelection = context_module.ContextSelection
RunLogger = logging_module.RunLogger
build_prompt_context_vars = context_module.build_prompt_context_vars
AppConfig = config_app_config.AppConfig
CONTEXT_CHAR_WARNING_THRESHOLD_DEFAULT = (
    loader_module.CONTEXT_CHAR_WARNING_THRESHOLD_DEFAULT
)
CONTEXT_CHAR_WARNING_THRESHOLD_BY_MODEL = (
    loader_module.CONTEXT_CHAR_WARNING_THRESHOLD_BY_MODEL
)


def _make_app_config(
    *,
    max_characters: int = 3,
    max_locations: int = 1,
    include_world: bool = True,
) -> AppConfig:
    """Build AppConfig with default values for non-context fields."""
    return AppConfig(
        beats=5,
        section_length="400-600",
        max_characters=max_characters,
        max_locations=max_locations,
        include_world=include_world,
        llm_provider="openai",
        model="gpt-4.1-mini",
    )


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
        (context_dir / "characters").mkdir()
        (context_dir / "characters" / "one.md").write_text("# One")

        loader = ContextLoader(context_dir)
        selection = loader.load_context("run-test-004")

        # Should have lore_bible, no style files
        assert "lore_bible.md" in selection.always_loaded
        assert len([k for k in selection.always_loaded if k != "lore_bible.md"]) == 0

    def test_selects_one_location_random(self, temp_context_dir: Path) -> None:
        """Selects exactly one location file at random from locations/."""
        valid_locations = {
            "locations/city.md",
            "locations/desert.md",
            "locations/forest.md",
        }
        loader = ContextLoader(temp_context_dir)
        selection = loader.load_context("run-test-005")

        assert selection.selected_location in valid_locations
        assert selection.location_content is not None
        assert len(selection.location_content) > 0

    def test_handles_missing_locations_directory(self, tmp_path: Path) -> None:
        """Handles missing locations directory gracefully (optional)."""
        context_dir = tmp_path / "context" / "test-app"
        context_dir.mkdir(parents=True)
        (context_dir / "lore_bible.md").write_text("# Lore Bible")
        (context_dir / "characters").mkdir()
        (context_dir / "characters" / "one.md").write_text("# One")

        loader = ContextLoader(context_dir)
        selection = loader.load_context("run-test-006")

        assert selection.selected_location is None
        assert selection.location_content is None
        assert selection.world_files == []

    def test_handles_empty_locations_directory(self, tmp_path: Path) -> None:
        """Handles empty locations directory gracefully (optional)."""
        context_dir = tmp_path / "context" / "test-app"
        context_dir.mkdir(parents=True)
        (context_dir / "lore_bible.md").write_text("# Lore Bible")
        (context_dir / "locations").mkdir()
        (context_dir / "characters").mkdir()
        (context_dir / "characters" / "one.md").write_text("# One")

        loader = ContextLoader(context_dir)
        selection = loader.load_context("run-test-007")

        assert selection.selected_location is None
        assert selection.location_content is None

    def test_selects_characters_random_bounded(self, temp_context_dir: Path) -> None:
        """Selects up to 3 character files at random from characters/."""
        valid_chars = {
            "characters/hero.md",
            "characters/mentor.md",
            "characters/sidekick.md",
            "characters/villain.md",
        }
        loader = ContextLoader(temp_context_dir)
        selection = loader.load_context("run-test-008")

        assert len(selection.selected_characters) == 3
        assert set(selection.selected_characters) <= valid_chars
        assert len(selection.character_contents) == 3

    def test_fails_without_characters_directory(self, tmp_path: Path) -> None:
        """Run fails with explicit message if characters directory is missing."""
        context_dir = tmp_path / "context" / "test-app"
        context_dir.mkdir(parents=True)
        (context_dir / "lore_bible.md").write_text("# Lore Bible")

        loader = ContextLoader(context_dir)
        with pytest.raises(ContextLoaderError) as exc_info:
            loader.load_context("run-test-009")

        assert "characters" in str(exc_info.value).lower()

    def test_fails_with_empty_characters_directory(self, tmp_path: Path) -> None:
        """Run fails with explicit message if characters directory has no .md files."""
        context_dir = tmp_path / "context" / "test-app"
        context_dir.mkdir(parents=True)
        (context_dir / "lore_bible.md").write_text("# Lore Bible")
        (context_dir / "characters").mkdir()

        loader = ContextLoader(context_dir)
        with pytest.raises(ContextLoaderError) as exc_info:
            loader.load_context("run-test-010")

        assert "character" in str(exc_info.value).lower()

    def test_selects_one_character_when_only_one_exists(self, tmp_path: Path) -> None:
        """Selects the single character when only one exists (at least 1 required)."""
        context_dir = tmp_path / "context" / "test-app"
        context_dir.mkdir(parents=True)
        (context_dir / "lore_bible.md").write_text("# Lore Bible")
        characters_dir = context_dir / "characters"
        characters_dir.mkdir()
        (characters_dir / "only_one.md").write_text("# Only One\n\nSingle character.")

        loader = ContextLoader(context_dir)
        selection = loader.load_context("run-test-011")

        assert selection.selected_characters == ["characters/only_one.md"]
        assert len(selection.character_contents) == 1

    def test_reproducible_selection_same_run_id(self, temp_context_dir: Path) -> None:
        """Same run_id yields the same location and character selection."""
        loader = ContextLoader(temp_context_dir)

        selection1 = loader.load_context("run-reproducible-001")
        selection2 = loader.load_context("run-reproducible-001")

        assert selection1.selected_location == selection2.selected_location
        assert selection1.selected_characters == selection2.selected_characters
        assert selection1.world_files == selection2.world_files

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
        assert hasattr(selection, "world_files")

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
        (context_dir / "characters").mkdir()
        (context_dir / "characters" / "one.md").write_text("# One")

        loader = ContextLoader(context_dir)
        selection = loader.load_context("run-unicode-001")

        assert "émojis" in selection.always_loaded["lore_bible.md"]
        assert "🎭" in selection.always_loaded["lore_bible.md"]

    def test_minimal_app_requires_at_least_one_character(self, tmp_path: Path) -> None:
        """Run fails if only lore_bible exists (at least one character required)."""
        context_dir = tmp_path / "context" / "minimal-app"
        context_dir.mkdir(parents=True)
        (context_dir / "lore_bible.md").write_text("# Minimal Lore")

        loader = ContextLoader(context_dir)
        with pytest.raises(ContextLoaderError):
            loader.load_context("run-minimal-001")

    def test_minimal_app_with_one_character_succeeds(self, tmp_path: Path) -> None:
        """App with lore_bible + one character succeeds."""
        context_dir = tmp_path / "context" / "minimal-app"
        context_dir.mkdir(parents=True)
        (context_dir / "lore_bible.md").write_text("# Minimal Lore")
        (context_dir / "characters").mkdir()
        (context_dir / "characters" / "protagonist.md").write_text("# Protagonist")

        loader = ContextLoader(context_dir)
        selection = loader.load_context("run-minimal-002")

        assert "lore_bible.md" in selection.always_loaded
        assert selection.selected_characters == ["characters/protagonist.md"]
        assert selection.selected_location is None
        assert selection.world_files == []

    def test_handles_large_context_library_random_bounded(self, tmp_path: Path) -> None:
        """Selects one location and 3 characters at random from large sets."""
        context_dir = tmp_path / "context" / "large-app"
        context_dir.mkdir(parents=True)
        (context_dir / "lore_bible.md").write_text("# Large Lore")

        locations_dir = context_dir / "locations"
        locations_dir.mkdir()
        valid_locations = {f"locations/location_{i:02d}.md" for i in range(20)}
        for i in range(20):
            (locations_dir / f"location_{i:02d}.md").write_text(f"# Location {i}")

        characters_dir = context_dir / "characters"
        characters_dir.mkdir()
        valid_characters = {f"characters/character_{i:02d}.md" for i in range(15)}
        for i in range(15):
            (characters_dir / f"character_{i:02d}.md").write_text(f"# Character {i}")

        loader = ContextLoader(context_dir)
        selection = loader.load_context("run-large-001")

        assert selection.selected_location in valid_locations
        assert len(selection.selected_characters) == 3
        assert set(selection.selected_characters) <= valid_characters

    def test_no_duplicate_character_selection(self, temp_context_dir: Path) -> None:
        """Selected characters are unique (no duplicates)."""
        loader = ContextLoader(temp_context_dir)
        selection = loader.load_context("run-unique-001")

        assert len(selection.selected_characters) == len(
            set(selection.selected_characters)
        )
        assert len(selection.character_contents) == len(selection.selected_characters)

    def test_world_folded_into_lore_bible_alphabetical(self, tmp_path: Path) -> None:
        """If world/ exists with .md files, they are loaded in alphabetical order and folded into lore_bible."""
        context_dir = tmp_path / "context" / "test-app"
        context_dir.mkdir(parents=True)
        (context_dir / "lore_bible.md").write_text("# Lore\n\nCore lore.")
        (context_dir / "characters").mkdir()
        (context_dir / "characters" / "one.md").write_text("# One")
        world_dir = context_dir / "world"
        world_dir.mkdir()
        (world_dir / "beta.md").write_text("# Beta world")
        (world_dir / "alpha.md").write_text("# Alpha world")

        loader = ContextLoader(context_dir)
        selection = loader.load_context("run-world-001")

        assert selection.world_files == ["world/alpha.md", "world/beta.md"]
        lore = selection.always_loaded["lore_bible.md"]
        assert "Core lore." in lore
        assert "World context" in lore or "world/*.md" in lore
        assert "Alpha world" in lore
        assert "Beta world" in lore
        # Alphabetical order: alpha before beta
        assert lore.index("Alpha world") < lore.index("Beta world")

    def test_world_optional_missing_dir_succeeds(self, tmp_path: Path) -> None:
        """Optional world directory missing => run still succeeds."""
        context_dir = tmp_path / "context" / "test-app"
        context_dir.mkdir(parents=True)
        (context_dir / "lore_bible.md").write_text("# Lore")
        (context_dir / "characters").mkdir()
        (context_dir / "characters" / "one.md").write_text("# One")

        loader = ContextLoader(context_dir)
        selection = loader.load_context("run-noworld-001")

        assert selection.world_files == []
        assert "lore_bible.md" in selection.always_loaded

    def test_build_prompt_context_vars_from_state(self, temp_context_dir: Path) -> None:
        """build_prompt_context_vars builds same vars from state (location, characters, world_files)."""
        loader = ContextLoader(temp_context_dir)
        selection = loader.load_context("run-buildvars-001")

        state = {
            "selected_context": {
                "location": Path(selection.selected_location).name
                if selection.selected_location
                else None,
                "characters": [Path(p).name for p in selection.selected_characters],
                "world_files": [Path(p).name for p in selection.world_files],
            }
        }
        vars_out = build_prompt_context_vars(temp_context_dir, state)

        assert "lore_bible" in vars_out
        assert "style_rules" in vars_out
        assert "location_context" in vars_out
        assert "character_context" in vars_out
        if selection.selected_location:
            assert len(vars_out["location_context"]) > 0
        assert len(vars_out["character_context"]) > 0


class TestContextLoaderAppConfigLimits:
    """Tests for context selection limits from app config (T005)."""

    def test_app_config_max_characters_limits_selection(
        self, temp_context_dir: Path
    ) -> None:
        """When app_config has max_characters=2, only 2 character files are selected (at random)."""
        valid_chars = {
            "characters/hero.md",
            "characters/mentor.md",
            "characters/sidekick.md",
            "characters/villain.md",
        }
        app_config = _make_app_config(max_characters=2)
        loader = ContextLoader(temp_context_dir, app_config=app_config)
        selection = loader.load_context("run-limits-001")

        assert len(selection.selected_characters) == 2
        assert set(selection.selected_characters) <= valid_chars
        assert len(selection.character_contents) == 2

    def test_app_config_max_characters_zero_selects_all(
        self, temp_context_dir: Path
    ) -> None:
        """When app_config has max_characters=0, all character files are selected."""
        app_config = _make_app_config(max_characters=0)
        loader = ContextLoader(temp_context_dir, app_config=app_config)
        selection = loader.load_context("run-all-chars-001")

        assert len(selection.selected_characters) == 4
        assert selection.selected_characters == [
            "characters/hero.md",
            "characters/mentor.md",
            "characters/sidekick.md",
            "characters/villain.md",
        ]
        assert len(selection.character_contents) == 4

    def test_app_config_max_locations_zero_omits_location(
        self, temp_context_dir: Path
    ) -> None:
        """When app_config has max_locations=0, no location is selected."""
        app_config = _make_app_config(max_locations=0)
        loader = ContextLoader(temp_context_dir, app_config=app_config)
        selection = loader.load_context("run-noloc-001")

        assert selection.selected_location is None
        assert selection.location_content is None
        assert len(selection.selected_characters) >= 1

    def test_app_config_include_world_false_omits_world(self, tmp_path: Path) -> None:
        """When app_config has include_world=False, world files are not loaded."""
        context_dir = tmp_path / "context" / "test-app"
        context_dir.mkdir(parents=True)
        (context_dir / "lore_bible.md").write_text("# Lore\n\nCore lore.")
        (context_dir / "characters").mkdir()
        (context_dir / "characters" / "one.md").write_text("# One")
        world_dir = context_dir / "world"
        world_dir.mkdir()
        (world_dir / "alpha.md").write_text("# Alpha world")

        app_config = _make_app_config(include_world=False)
        loader = ContextLoader(context_dir, app_config=app_config)
        selection = loader.load_context("run-noworld-002")

        assert selection.world_files == []
        lore = selection.always_loaded["lore_bible.md"]
        assert "Core lore." in lore
        assert "Alpha world" not in lore
        assert "World context" not in lore and "world/*.md" not in lore

    def test_no_app_config_uses_default_limits(self, temp_context_dir: Path) -> None:
        """When app_config is None, default limits apply (3 characters, 1 location, world included)."""
        valid_locations = {
            "locations/city.md",
            "locations/desert.md",
            "locations/forest.md",
        }
        valid_chars = {
            "characters/hero.md",
            "characters/mentor.md",
            "characters/sidekick.md",
            "characters/villain.md",
        }
        loader = ContextLoader(temp_context_dir)
        selection = loader.load_context("run-default-001")

        assert len(selection.selected_characters) == 3
        assert set(selection.selected_characters) <= valid_chars
        assert selection.selected_location in valid_locations
        assert "lore_bible.md" in selection.always_loaded


class TestContextSizeWarning:
    """Tests for v1.0.1 soft warning when combined context approaches threshold."""

    def test_no_warning_when_below_threshold(
        self, temp_context_dir: Path, tmp_path: Path
    ) -> None:
        """When combined context is below default threshold, no WARNING is logged."""
        log_path = tmp_path / "test.log"
        log_path.touch()
        logger = RunLogger(log_path)
        loader = ContextLoader(temp_context_dir, logger=logger)
        selection = loader.load_context("run-below-001")

        content = log_path.read_text()
        assert (
            "[WARNING]" not in content or "Combined context approaches" not in content
        )
        assert "lore_bible.md" in selection.always_loaded

    def test_warning_when_at_or_above_default_threshold(self, tmp_path: Path) -> None:
        """When combined context is >= default threshold and logger present, WARNING is logged."""
        context_dir = tmp_path / "context" / "large-app"
        context_dir.mkdir(parents=True)
        # Create context that exceeds 15_000 chars (default threshold)
        big_lore = "x" * (CONTEXT_CHAR_WARNING_THRESHOLD_DEFAULT - 100)
        (context_dir / "lore_bible.md").write_text(big_lore)
        (context_dir / "characters").mkdir()
        (context_dir / "characters" / "one.md").write_text("a" * 200)

        log_path = tmp_path / "test.log"
        log_path.touch()
        logger = RunLogger(log_path)
        loader = ContextLoader(context_dir, logger=logger)
        selection = loader.load_context("run-above-001")

        content = log_path.read_text()
        assert "[WARNING]" in content
        assert "Combined context approaches or exceeds threshold" in content
        assert str(CONTEXT_CHAR_WARNING_THRESHOLD_DEFAULT) in content
        assert "lore_bible.md" in selection.always_loaded

    def test_no_crash_when_above_threshold_and_no_logger(self, tmp_path: Path) -> None:
        """When logger is None and context is above threshold, load_context still succeeds."""
        context_dir = tmp_path / "context" / "large-app"
        context_dir.mkdir(parents=True)
        big_lore = "x" * (CONTEXT_CHAR_WARNING_THRESHOLD_DEFAULT + 1000)
        (context_dir / "lore_bible.md").write_text(big_lore)
        (context_dir / "characters").mkdir()
        (context_dir / "characters" / "one.md").write_text("# One")

        loader = ContextLoader(context_dir, logger=None)
        selection = loader.load_context("run-nologger-001")

        assert "lore_bible.md" in selection.always_loaded
        assert selection.selected_characters == ["characters/one.md"]

    def test_model_specific_threshold_used_when_model_in_dict(
        self, tmp_path: Path
    ) -> None:
        """When model is in CONTEXT_CHAR_WARNING_THRESHOLD_BY_MODEL, that threshold is used."""
        context_dir = tmp_path / "context" / "app"
        context_dir.mkdir(parents=True)
        # Total ~60 chars: above 50 (model threshold) but below 15000 (default)
        (context_dir / "lore_bible.md").write_text("x" * 30)
        (context_dir / "characters").mkdir()
        (context_dir / "characters" / "one.md").write_text("y" * 30)

        log_path = tmp_path / "test.log"
        log_path.touch()
        logger = RunLogger(log_path)

        original = dict(CONTEXT_CHAR_WARNING_THRESHOLD_BY_MODEL)
        try:
            CONTEXT_CHAR_WARNING_THRESHOLD_BY_MODEL["test-model"] = 50
            loader = ContextLoader(context_dir, logger=logger)
            loader.load_context("run-model-001", model="test-model")

            content = log_path.read_text()
            assert "[WARNING]" in content
            assert "Combined context approaches or exceeds threshold" in content
            assert "50" in content
        finally:
            CONTEXT_CHAR_WARNING_THRESHOLD_BY_MODEL.clear()
            CONTEXT_CHAR_WARNING_THRESHOLD_BY_MODEL.update(original)

    def test_default_threshold_used_when_model_not_in_dict(
        self, tmp_path: Path
    ) -> None:
        """When model is not in dict, default threshold is used (no warning for small context)."""
        context_dir = tmp_path / "context" / "app"
        context_dir.mkdir(parents=True)
        (context_dir / "lore_bible.md").write_text("x" * 100)
        (context_dir / "characters").mkdir()
        (context_dir / "characters" / "one.md").write_text("y" * 50)

        log_path = tmp_path / "test.log"
        log_path.touch()
        logger = RunLogger(log_path)
        loader = ContextLoader(context_dir, logger=logger)
        selection = loader.load_context("run-other-model-001", model="other-model")

        content = log_path.read_text()
        assert "Combined context approaches or exceeds threshold" not in content
        assert "lore_bible.md" in selection.always_loaded
