"""Context file loading and deterministic selection for pipeline runs."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..logging import RunLogger

# Maximum number of character files to include (deterministic subset, alphabetical).
MAX_CHARACTERS = 3

# Separator header when folding world/*.md into lore_bible (traceable in output/logs).
WORLD_FOLD_SEPARATOR = "\n\n---\n## World context (from world/*.md)\n\n"


class ContextLoaderError(Exception):
    """Raised when context loading fails."""

    pass


@dataclass
class ContextSelection:
    """Represents selected context files for a run.

    Attributes:
        always_loaded: Dictionary mapping relative file paths to file contents.
            Includes lore_bible.md (with world content folded if present) and
            all style/*.md files.
        selected_location: Relative path to selected location file, or None.
        selected_characters: List of relative paths to selected character files
            (deterministic subset, up to MAX_CHARACTERS).
        location_content: Content of selected location file, or None.
        character_contents: Dictionary mapping relative paths to file contents.
        world_files: List of relative paths to world/*.md files folded into
            lore_bible (empty if no world directory or no .md files).
    """

    always_loaded: dict[str, str]
    selected_location: str | None
    selected_characters: list[str]
    location_content: str | None
    character_contents: dict[str, str]
    world_files: list[str]


class ContextLoader:
    """Loads and selects context files for a pipeline run.

    Handles:
    - Always-loaded files (lore_bible.md, optionally world/*.md folded in, style/*.md)
    - Deterministic selection: 1 location (first alphabetically), up to
      MAX_CHARACTERS characters (first alphabetically)
    - Required: lore_bible.md must exist; at least one character file must exist.
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
        """Normalize a path to use forward slashes (POSIX-style)."""
        return str(path).replace("\\", "/")

    def load_context(self, run_id: str) -> ContextSelection:
        """Load and select context files for a run.

        Required:
        - lore_bible.md must exist.
        - At least one character file in characters/*.md must exist.

        Optional (deterministic):
        - locations/: include exactly one file (first alphabetically).
        - world/: load all *.md in alphabetical order, fold into lore_bible
          with a clear separator; record world_files in selection.

        Args:
            run_id: Run identifier (used for logging only; selection is deterministic).

        Returns:
            ContextSelection with loaded files and selections.

        Raises:
            ContextLoaderError: If lore_bible.md is missing or characters
                directory is missing/empty.
        """
        # Load lore_bible and world (folded), then style
        always_loaded = self._load_lore_and_style()
        world_files = always_loaded.pop("_world_files", [])

        # Deterministic: one location (first alphabetically)
        selected_location, location_content = self._select_location()

        # Deterministic: up to MAX_CHARACTERS characters (first alphabetically);
        # at least one required (validated inside _select_characters)
        selected_characters, character_contents = self._select_characters()

        if self.logger:
            self.logger.log_context_selection(
                always_loaded=list(always_loaded.keys()),
                selected_location=selected_location,
                selected_characters=selected_characters,
                world_files=world_files,
            )

        return ContextSelection(
            always_loaded=always_loaded,
            selected_location=selected_location,
            selected_characters=selected_characters,
            location_content=location_content,
            character_contents=character_contents,
            world_files=world_files,
        )

    def _load_lore_and_style(self) -> dict[str, str]:
        """Load lore_bible (required), fold world/*.md if present, then style/*.md.

        Returns:
            Dict with 'lore_bible.md' (with world content appended if any),
            '_world_files' (list of world file paths, for logging/state),
            and style file entries. _world_files is removed before building
            ContextSelection.always_loaded.
        """
        result: dict[str, str] = {}
        lore_bible_path = self.context_dir / "lore_bible.md"
        if not lore_bible_path.exists():
            raise ContextLoaderError(
                f"Required file not found: {lore_bible_path.relative_to(self.context_dir)}"
            )
        lore_content = self._read_file(lore_bible_path)

        # World: load all world/*.md in alphabetical order, append with separator
        world_dir = self.context_dir / "world"
        world_parts: list[str] = []
        world_files: list[str] = []
        if world_dir.exists() and world_dir.is_dir():
            for world_file in sorted(world_dir.glob("*.md")):
                rel_path = world_file.relative_to(self.context_dir)
                normalized = self._normalize_path(rel_path)
                world_files.append(normalized)
                world_parts.append(self._read_file(world_file))
        if world_parts:
            lore_content = (
                lore_content.rstrip() + WORLD_FOLD_SEPARATOR + "\n\n".join(world_parts)
            )
        result["lore_bible.md"] = lore_content
        result["_world_files"] = world_files  # consumed by caller

        # Style
        style_dir = self.context_dir / "style"
        if style_dir.exists() and style_dir.is_dir():
            for style_file in sorted(style_dir.glob("*.md")):
                rel_path = style_file.relative_to(self.context_dir)
                result[self._normalize_path(rel_path)] = self._read_file(style_file)

        return result

    def _select_location(self) -> tuple[str | None, str | None]:
        """Select exactly one location file deterministically (first alphabetically).

        Returns:
            Tuple of (relative_path, content) or (None, None) if no locations.
        """
        locations_dir = self.context_dir / "locations"
        if not locations_dir.exists() or not locations_dir.is_dir():
            return (None, None)
        location_files = sorted(locations_dir.glob("*.md"))
        if not location_files:
            return (None, None)
        selected = location_files[0]
        rel_path = selected.relative_to(self.context_dir)
        normalized = self._normalize_path(rel_path)
        return (normalized, self._read_file(selected))

    def _select_characters(self) -> tuple[list[str], dict[str, str]]:
        """Select up to MAX_CHARACTERS character files deterministically (first alphabetically).

        At least one character file is required; raises if characters dir
        is missing or empty.

        Returns:
            Tuple of (list of relative paths, dict path -> content).
        """
        characters_dir = self.context_dir / "characters"
        if not characters_dir.exists() or not characters_dir.is_dir():
            raise ContextLoaderError(
                "Required context directory not found or empty: context/<app>/characters/ "
                "(at least one .md file is required)"
            )
        character_files = sorted(characters_dir.glob("*.md"))
        if not character_files:
            raise ContextLoaderError(
                "No character files found in context/<app>/characters/ "
                "(at least one .md file is required)"
            )
        selected = character_files[:MAX_CHARACTERS]
        selected_paths: list[str] = []
        contents: dict[str, str] = {}
        for char_file in selected:
            rel_path = char_file.relative_to(self.context_dir)
            normalized = self._normalize_path(rel_path)
            selected_paths.append(normalized)
            contents[normalized] = self._read_file(char_file)
        return (selected_paths, contents)

    def _read_file(self, file_path: Path) -> str:
        """Read a file as UTF-8 text."""
        try:
            return file_path.read_text(encoding="utf-8")
        except OSError as e:
            raise ContextLoaderError(f"Failed to read {file_path}: {e}") from e


def build_prompt_context_vars(
    context_dir: Path, state: dict[str, Any]
) -> dict[str, str]:
    """Build prompt variables from state (lore_bible, style, location, characters).

    Uses the same contract as ContextLoader: lore_bible plus world files
    (from state) merged with separator, style, optional location, required
    character context. Used by outline, section, and critic steps.

    Args:
        context_dir: Path to the app's context directory.
        state: State dict with selected_context (location, characters, world_files).

    Returns:
        Dict with keys: lore_bible, style_rules, location_context, character_context.
    """
    context_dir = context_dir.resolve()
    selected = state.get("selected_context", {})
    context_vars: dict[str, str] = {}

    # Lore bible (required)
    lore_path = context_dir / "lore_bible.md"
    if not lore_path.exists():
        raise ContextLoaderError(
            f"Required file not found: {lore_path.relative_to(context_dir)}"
        )
    lore_content = lore_path.read_text(encoding="utf-8")

    # World: fold in alphabetical order with separator (same as loader)
    world_files = selected.get("world_files", [])
    if world_files:
        world_dir = context_dir / "world"
        parts: list[str] = []
        for name in sorted(world_files):
            p = world_dir / name
            if p.exists():
                parts.append(p.read_text(encoding="utf-8"))
        if parts:
            lore_content = (
                lore_content.rstrip() + WORLD_FOLD_SEPARATOR + "\n\n".join(parts)
            )
    context_vars["lore_bible"] = lore_content

    # Style
    style_dir = context_dir / "style"
    style_parts: list[str] = []
    if style_dir.exists():
        for f in sorted(style_dir.glob("*.md")):
            style_parts.append(f"## {f.stem}\n\n{f.read_text(encoding='utf-8')}")
    context_vars["style_rules"] = "\n\n".join(style_parts) if style_parts else ""

    # Location (optional)
    location_name = selected.get("location")
    context_vars["location_context"] = ""
    if location_name:
        loc_path = context_dir / "locations" / location_name
        if loc_path.exists():
            context_vars["location_context"] = loc_path.read_text(encoding="utf-8")

    # Characters (required; state already validated at run start)
    character_names = selected.get("characters", [])
    char_parts: list[str] = []
    for name in character_names:
        char_path = context_dir / "characters" / name
        if char_path.exists():
            char_parts.append(f"## {name}\n\n{char_path.read_text(encoding='utf-8')}")
    context_vars["character_context"] = "\n\n".join(char_parts) if char_parts else ""

    return context_vars
