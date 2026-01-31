"""App discovery and validation.

Resolves app names to their corresponding context and prompt directories.
Prefers apps/<app_name>/ (only lore_bible.md required); falls back to
context/<app_name>/ + prompts/apps/<app_name>/ for backward compatibility.
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
        app_root: When resolved from apps/<app_name>/; path to that directory.
            None when resolved from legacy context/ + prompts/apps/.
    """

    app_name: str
    context_dir: Path
    prompts_dir: Path
    app_root: Path | None = None


def resolve_app(app_name: str, base_dir: Path | None = None) -> AppPaths:
    """Resolve an app name to its context and prompt directories.

    Resolution order:
    1. apps/<app_name>/context/lore_bible.md exists -> use apps/<app_name>/context
       and prompts from apps/<app_name>/prompts/ if present, else prompts/app-defaults/.
    2. Else context/<app_name>/ and prompts/apps/<app_name>/ both exist -> legacy paths.
    3. Else raise AppNotFoundError.

    Args:
        app_name: The name of the app to resolve.
        base_dir: The base directory of the project. If None, uses current working
            directory.

    Returns:
        AppPaths containing the resolved paths and app_root when from apps/.

    Raises:
        AppNotFoundError: If the app cannot be found in either layout.
    """
    if not app_name or not app_name.strip():
        raise AppNotFoundError("App name cannot be empty.")

    app_name = app_name.strip()

    if base_dir is None:
        base_dir = Path.cwd()

    base_dir = base_dir.resolve()

    # Prefer apps/<app_name>/: valid if only context/lore_bible.md exists
    apps_context = base_dir / "apps" / app_name / "context"
    lore_bible = apps_context / "lore_bible.md"
    if lore_bible.exists():
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

    # Legacy: context/<app_name>/ and prompts/apps/<app_name>/
    context_dir = base_dir / "context" / app_name
    prompts_dir = base_dir / "prompts" / "apps" / app_name

    missing_paths: list[str] = []

    if not context_dir.is_dir():
        missing_paths.append(f"context/{app_name}/")

    if not prompts_dir.is_dir():
        missing_paths.append(f"prompts/apps/{app_name}/")

    if missing_paths:
        missing_str = ", ".join(missing_paths)
        raise AppNotFoundError(
            f"App '{app_name}' not found. Missing: {missing_str}\n"
            f"Either create apps/{app_name}/context/lore_bible.md "
            f"or ensure both directories exist under: {base_dir}"
        )

    return AppPaths(
        app_name=app_name,
        context_dir=context_dir,
        prompts_dir=prompts_dir,
        app_root=None,
    )
