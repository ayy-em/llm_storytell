"""Context file loading and randomized selection for pipeline runs."""

import random
from dataclasses import dataclass
from pathlib import Path

from ..logging import RunLogger


class ContextLoaderError(Exception):
    """Raised when context loading fails."""

    pass


@dataclass
class ContextSelection:
    """Represents selected context files for a run.

    Attributes:
        always_loaded: Dictionary mapping relative file paths to file contents.
            Includes lore_bible.md and all style/*.md files.
        selected_location: Relative path to selected location file, or None.
        selected_characters: List of relative paths to selected character files.
        location_content: Content of selected location file, or None.
        character_contents: Dictionary mapping relative paths to file contents.
    """

    always_loaded: dict[str, str]
    selected_location: str | None
    selected_characters: list[str]
    location_content: str | None
    character_contents: dict[str, str]


class ContextLoader:
    """Loads and selects context files for a pipeline run.

    Handles:
    - Always-loaded files (lore_bible.md, style/*.md)
    - Randomized selection (1 location, 2-3 characters)
    - Reproducible selection based on run_id seed
    """

    def __init__(self, context_dir: Path, logger: RunLogger | None = None) -> None:
        """Initialize the context loader.

        Args:
            context_dir: Path to the app's context directory.
            logger: Optional logger for recording selections.
        """
        self.context_dir = context_dir.resolve()
        self.logger = logger

    def _normalize_path(self, path: Path) -> str:
        """Normalize a path to use forward slashes (POSIX-style).

        Args:
            path: Path to normalize.

        Returns:
            String representation with forward slashes.
        """
        return str(path).replace("\\", "/")

    def load_context(self, run_id: str) -> ContextSelection:
        """Load and select context files for a run.

        Always loads:
        - lore_bible.md (required)
        - All *.md files from style/ directory

        Randomly selects:
        - 1 file from locations/ directory
        - 2-3 files from characters/ directory (or all available if fewer)

        Args:
            run_id: Run identifier used as random seed for reproducibility.

        Returns:
            ContextSelection with loaded files and selections.

        Raises:
            ContextLoaderError: If lore_bible.md is missing or other critical errors.
        """
        # Set deterministic random seed based on run_id
        seed = hash(run_id) % (2**32)
        random.seed(seed)

        # Load always-required files
        always_loaded = self._load_always_required()

        # Randomly select location
        selected_location, location_content = self._select_location()

        # Randomly select characters
        selected_characters, character_contents = self._select_characters()

        # Log selections
        if self.logger:
            self.logger.log_context_selection(
                always_loaded=list(always_loaded.keys()),
                selected_location=selected_location,
                selected_characters=selected_characters,
            )

        return ContextSelection(
            always_loaded=always_loaded,
            selected_location=selected_location,
            selected_characters=selected_characters,
            location_content=location_content,
            character_contents=character_contents,
        )

    def _load_always_required(self) -> dict[str, str]:
        """Load always-required context files.

        Returns:
            Dictionary mapping relative file paths to file contents.

        Raises:
            ContextLoaderError: If lore_bible.md is missing.
        """
        always_loaded: dict[str, str] = {}

        # Load lore_bible.md (required)
        lore_bible_path = self.context_dir / "lore_bible.md"
        if not lore_bible_path.exists():
            raise ContextLoaderError(
                f"Required file not found: {lore_bible_path.relative_to(self.context_dir)}"
            )
        always_loaded["lore_bible.md"] = self._read_file(lore_bible_path)

        # Load all style files
        style_dir = self.context_dir / "style"
        if style_dir.exists() and style_dir.is_dir():
            for style_file in sorted(style_dir.glob("*.md")):
                rel_path = style_file.relative_to(self.context_dir)
                always_loaded[self._normalize_path(rel_path)] = self._read_file(
                    style_file
                )

        return always_loaded

    def _select_location(self) -> tuple[str | None, str | None]:
        """Randomly select one location file.

        Returns:
            Tuple of (relative_path, content) or (None, None) if no locations available.
        """
        locations_dir = self.context_dir / "locations"
        if not locations_dir.exists() or not locations_dir.is_dir():
            return (None, None)

        location_files = sorted(locations_dir.glob("*.md"))
        if not location_files:
            return (None, None)

        selected = random.choice(location_files)
        rel_path = selected.relative_to(self.context_dir)
        normalized_path = self._normalize_path(rel_path)
        content = self._read_file(selected)
        return (normalized_path, content)

    def _select_characters(self) -> tuple[list[str], dict[str, str]]:
        """Randomly select 2-3 character files (or all available if fewer).

        Returns:
            Tuple of (list of relative paths, dict mapping paths to contents).
        """
        characters_dir = self.context_dir / "characters"
        if not characters_dir.exists() or not characters_dir.is_dir():
            return ([], {})

        character_files = sorted(characters_dir.glob("*.md"))
        if not character_files:
            return ([], {})

        # Select 2-3 characters, or all if fewer available
        num_to_select = min(random.randint(2, 3), len(character_files))
        selected = random.sample(character_files, num_to_select)

        # Warn if fewer than 2 selected (but don't fail)
        if len(selected) < 2 and self.logger:
            self.logger.info(
                f"Warning: Only {len(selected)} character file(s) available "
                f"(expected 2-3). Selected all available."
            )

        selected_paths: list[str] = []
        contents: dict[str, str] = {}
        for char_file in selected:
            rel_path = char_file.relative_to(self.context_dir)
            normalized_path = self._normalize_path(rel_path)
            selected_paths.append(normalized_path)
            contents[normalized_path] = self._read_file(char_file)

        return (selected_paths, contents)

    def _read_file(self, file_path: Path) -> str:
        """Read a file as UTF-8 text.

        Args:
            file_path: Path to the file to read.

        Returns:
            File contents as string.

        Raises:
            ContextLoaderError: If file cannot be read.
        """
        try:
            return file_path.read_text(encoding="utf-8")
        except OSError as e:
            raise ContextLoaderError(f"Failed to read {file_path}: {e}") from e
