"""App config loading and merging with pipeline defaults."""

from __future__ import annotations

import yaml
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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
        tts_provider: TTS provider identifier (optional).
        tts_model: TTS model identifier (optional).
        tts_voice: TTS voice name (optional).
        tts_arguments: Optional dict passed verbatim to TTS provider.
        bg_music: Optional path to background music asset.
    """

    beats: int
    section_length: str
    max_characters: int
    max_locations: int
    include_world: bool
    llm_provider: str
    model: str
    tts_provider: str = "openai"
    tts_model: str = "gpt-4o-mini-tts"
    tts_voice: str = "Onyx"
    tts_arguments: dict[str, Any] | None = None
    bg_music: str | None = None

    def resolved_tts_config(self) -> dict[str, Any]:
        """Return resolved TTS/audio config as a JSON-serializable dict for state.json."""
        return {
            "tts_provider": self.tts_provider,
            "tts_model": self.tts_model,
            "tts_voice": self.tts_voice,
            "tts_arguments": self.tts_arguments
            if self.tts_arguments is not None
            else {},
            "bg_music": self.bg_music,
        }


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
    "tts-provider": "openai",
    "tts-model": "gpt-4o-mini-tts",
    "tts-voice": "Onyx",
    "tts-arguments": None,
    "bg-music": None,
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

    # Resolve TTS/audio keys (YAML uses hyphens; support both hyphen and snake_case)
    def _get(key: str, default: Any) -> Any:
        return merged.get(key) if merged.get(key) is not None else default

    tts_provider = str(
        _get("tts-provider", _get("tts_provider", _BUILTIN_DEFAULTS["tts-provider"]))
    )
    tts_model = str(
        _get("tts-model", _get("tts_model", _BUILTIN_DEFAULTS["tts-model"]))
    )
    tts_voice = str(
        _get("tts-voice", _get("tts_voice", _BUILTIN_DEFAULTS["tts-voice"]))
    )
    raw_tts_args = _get("tts-arguments", _get("tts_arguments", None))
    tts_arguments: dict[str, Any] | None = (
        dict(raw_tts_args) if isinstance(raw_tts_args, dict) else None
    )
    raw_bg = _get("bg-music", _get("bg_music", None))
    bg_music = str(raw_bg) if raw_bg is not None else None

    # Build AppConfig with safe defaults for missing keys
    return AppConfig(
        beats=int(merged.get("beats", 5)),
        section_length=str(merged.get("section_length", "400-600")),
        max_characters=int(merged.get("max_characters", 3)),
        max_locations=int(merged.get("max_locations", 1)),
        include_world=bool(merged.get("include_world", True)),
        llm_provider=str(merged.get("llm_provider", "openai")),
        model=str(merged.get("model", "gpt-4.1-mini")),
        tts_provider=tts_provider,
        tts_model=tts_model,
        tts_voice=tts_voice,
        tts_arguments=tts_arguments,
        bg_music=bg_music,
    )
