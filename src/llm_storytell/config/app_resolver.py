"""App discovery and validation.

Resolves app names to their corresponding context and prompt directories.
Only apps/<app_name>/ is used: context from apps/<app_name>/context/,
prompts from apps/<app_name>/prompts/ if present, else prompts/app-defaults/.
"""

from dataclasses import dataclass
from pathlib import Path


class AppNotFoundError(Exception):
    """Raised when an app cannot be resolved to valid paths."""

    pass


@dataclass(frozen=True)
class AppPaths:
    """Resolved paths for an app.

    Attributes:
        app_name: The name of the app.
        context_dir: Path to the app's context directory.
        prompts_dir: Path to the app's prompts directory.
        app_root: Path to apps/<app_name>/.
    """

    app_name: str
    context_dir: Path
    prompts_dir: Path
    app_root: Path | None = None


def resolve_app(app_name: str, base_dir: Path | None = None) -> AppPaths:
    """Resolve an app name to its context and prompt directories.

    Resolution uses only apps/<app_name>/:
    - apps/<app_name>/context/lore_bible.md must exist.
    - Prompts from apps/<app_name>/prompts/ if present, else prompts/app-defaults/.

    Args:
        app_name: The name of the app to resolve.
        base_dir: The base directory of the project. If None, uses current working
            directory.

    Returns:
        AppPaths containing the resolved paths and app_root.

    Raises:
        AppNotFoundError: If apps/<app_name>/context/lore_bible.md does not exist.
    """
    if not app_name or not app_name.strip():
        raise AppNotFoundError("App name cannot be empty.")

    app_name = app_name.strip()

    if base_dir is None:
        base_dir = Path.cwd()

    base_dir = base_dir.resolve()

    apps_context = base_dir / "apps" / app_name / "context"
    lore_bible = apps_context / "lore_bible.md"
    if not lore_bible.exists():
        raise AppNotFoundError(
            f"App '{app_name}' not found. Create apps/{app_name}/context/lore_bible.md "
            f"(and at least one character file in apps/{app_name}/context/characters/) "
            f"under: {base_dir}"
        )

    app_root = base_dir / "apps" / app_name
    prompts_in_app = app_root / "prompts"
    if prompts_in_app.is_dir():
        prompts_dir = prompts_in_app
    else:
        prompts_dir = base_dir / "prompts" / "app-defaults"

    return AppPaths(
        app_name=app_name,
        context_dir=apps_context,
        prompts_dir=prompts_dir,
        app_root=app_root,
    )
