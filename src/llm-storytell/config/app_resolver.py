"""App discovery and validation.

Resolves app names to their corresponding context and prompt directories.
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
        context_dir: Path to the app's context directory (context/<app>/).
        prompts_dir: Path to the app's prompts directory (prompts/apps/<app>/).
    """

    app_name: str
    context_dir: Path
    prompts_dir: Path


def resolve_app(app_name: str, base_dir: Path | None = None) -> AppPaths:
    """Resolve an app name to its context and prompt directories.

    Args:
        app_name: The name of the app to resolve.
        base_dir: The base directory of the project. If None, uses current working
            directory.

    Returns:
        AppPaths containing the resolved paths.

    Raises:
        AppNotFoundError: If the app name is empty, or if either the context
            or prompts directory does not exist.
    """
    if not app_name or not app_name.strip():
        raise AppNotFoundError("App name cannot be empty.")

    app_name = app_name.strip()

    if base_dir is None:
        base_dir = Path.cwd()

    base_dir = base_dir.resolve()

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
            f"App '{app_name}' not found. Missing directories: {missing_str}\n"
            f"Ensure both directories exist under: {base_dir}"
        )

    return AppPaths(
        app_name=app_name,
        context_dir=context_dir,
        prompts_dir=prompts_dir,
    )
