"""App config loading and merging with pipeline defaults."""

import yaml
from dataclasses import dataclass
from pathlib import Path


class AppConfigError(Exception):
    """Raised when app config cannot be loaded or is invalid."""

    pass


@dataclass(frozen=True)
class AppConfig:
    """Merged app config (defaults + optional app overrides).

    Attributes:
        beats: Default number of outline beats (1-20).
        section_length: Default section length hint (e.g. "400-600").
        max_characters: Max character files to select.
        max_locations: Max location files to select (1 = one location).
        include_world: Whether to include world/*.md in lore.
        llm_provider: LLM provider identifier.
        model: Default model identifier.
    """

    beats: int
    section_length: str
    max_characters: int
    max_locations: int
    include_world: bool
    llm_provider: str
    model: str


def _load_yaml(path: Path) -> dict:
    """Load a YAML file; return empty dict if file missing, raise on invalid YAML."""
    if not path.exists():
        return {}
    try:
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except yaml.YAMLError as e:
        raise AppConfigError(f"Invalid YAML in {path}: {e}") from e


def _default_config_path(base_dir: Path) -> Path:
    """Path to apps/default_config.yaml."""
    return base_dir.resolve() / "apps" / "default_config.yaml"


# Built-in defaults when apps/default_config.yaml is missing (e.g. legacy layout, e2e temp).
_BUILTIN_DEFAULTS: dict = {
    "beats": 5,
    "section_length": "400-600",
    "max_characters": 3,
    "max_locations": 1,
    "include_world": True,
    "llm_provider": "openai",
    "model": "gpt-4.1-mini",
}


def load_app_config(
    app_name: str,
    base_dir: Path | None = None,
    app_root: Path | None = None,
) -> AppConfig:
    """Load merged app config: defaults from apps/default_config.yaml plus app overrides.

    Args:
        app_name: Name of the app (for resolving app_config path when app_root not given).
        base_dir: Project base directory. If None, uses Path.cwd().
        app_root: If set, path to apps/<app_name>/; used to find app_config.yaml.
            If None, inferred as base_dir / "apps" / app_name when that dir exists.

    Returns:
        AppConfig with merged values (app overrides take precedence over defaults).

    Raises:
        AppConfigError: If default config file exists but is invalid, or app config YAML invalid.
    """
    if base_dir is None:
        base_dir = Path.cwd()
    base_dir = base_dir.resolve()

    defaults_path = _default_config_path(base_dir)
    if defaults_path.exists():
        defaults = _load_yaml(defaults_path)
        if not defaults:
            raise AppConfigError(
                f"Default app config empty or invalid: {defaults_path}"
            )
    else:
        # Legacy layout or e2e temp: no apps/; use built-in defaults
        defaults = dict(_BUILTIN_DEFAULTS)

    # App overrides: app_root or apps/<app_name>/
    app_config_path: Path | None = None
    if app_root is not None and app_root.is_dir():
        app_config_path = app_root / "app_config.yaml"
    else:
        candidate = base_dir / "apps" / app_name / "app_config.yaml"
        if candidate.exists():
            app_config_path = candidate

    overrides = _load_yaml(app_config_path) if app_config_path else {}

    # Shallow merge: overrides replace defaults for top-level keys only
    merged = dict(defaults)
    for key, value in overrides.items():
        if value is not None:
            merged[key] = value

    # Build AppConfig with safe defaults for missing keys
    return AppConfig(
        beats=int(merged.get("beats", 5)),
        section_length=str(merged.get("section_length", "400-600")),
        max_characters=int(merged.get("max_characters", 3)),
        max_locations=int(merged.get("max_locations", 1)),
        include_world=bool(merged.get("include_world", True)),
        llm_provider=str(merged.get("llm_provider", "openai")),
        model=str(merged.get("model", "gpt-4.1-mini")),
    )
