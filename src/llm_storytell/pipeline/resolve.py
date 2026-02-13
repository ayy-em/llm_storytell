"""Pipeline run settings resolution: CLI-like args + app config -> RunSettings."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from llm_storytell.config import AppConfig, AppPaths
from llm_storytell.tts_providers.elevenlabs_tts import (
    DEFAULT_VOICE_ID,
    DEFAULT_MODEL_ID,
)

# Per-provider default tts_model and tts_voice when CLI does not set them.
# Used so e.g. --tts-provider elevenlabs works without --tts-voice/--tts-model.
TTS_PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "openai": {"tts_model": "gpt-4o-mini-tts", "tts_voice": "onyx"},
    "elevenlabs": {"tts_model": DEFAULT_MODEL_ID, "tts_voice": DEFAULT_VOICE_ID},
}


def _section_length_midpoint(section_length_str: str) -> int:
    """Parse section_length string (e.g. '400-600') to midpoint; fallback 500."""
    s = section_length_str.strip()
    if "-" in s:
        parts = s.split("-", 1)
        try:
            lo, hi = int(parts[0].strip()), int(parts[1].strip())
            if lo > 0 and hi >= lo:
                return (lo + hi) // 2
        except ValueError:
            pass
    try:
        return int(s)
    except ValueError:
        pass
    return 500


@dataclass(frozen=True)
class RunSettings:
    """Resolved run settings for the pipeline runner.

    All data the runner needs: app paths, app config, seed, beats,
    section_length, run_id, config_path, model, word_count, TTS flags.
    """

    app_paths: AppPaths
    app_config: AppConfig
    seed: str
    beats: int
    section_length: str
    run_id: str | None
    config_path: Path
    model: str
    word_count: int | None
    tts_enabled: bool
    resolved_tts_config: dict[str, Any] | None


def resolve_run_settings(
    app_paths: AppPaths,
    app_config: AppConfig,
    seed: str,
    *,
    beats_arg: int | None = None,
    sections_arg: int | None = None,
    word_count: int | None = None,
    section_length_arg: int | None = None,
    model_arg: str | None = None,
    tts_enabled: bool = True,
    tts_provider: str | None = None,
    tts_provider_cli: str | None = None,
    tts_voice: str | None = None,
    tts_model: str | None = None,
    run_id: str | None = None,
    config_path: Path | None = None,
) -> RunSettings:
    """Build RunSettings from CLI-like args and app config.

    Caller must validate word_count range and beats/word_count consistency
    before calling. This only derives beats, section_length, model,
    and resolved_tts_config.

    Args:
        app_paths: Resolved app paths.
        app_config: Merged app config (defaults + app overrides).
        seed: Story seed string.
        beats_arg: --beats value (optional).
        sections_arg: --sections value (optional; used when beats_arg is None).
        word_count: --word-count value (optional).
        section_length_arg: --section-length N value (optional).
        model_arg: --model value (optional).
        tts_enabled: Whether TTS is enabled (not --no-tts).
        tts_provider: Resolved provider (CLI or app).
        tts_provider_cli: Raw --tts-provider value (None if not passed). When set, missing voice/model use provider defaults; when None, use app config.
        tts_voice: --tts-voice (optional).
        tts_model: --tts-model (optional).
        run_id: --run-id override (optional).
        config_path: --config-path (default config/).

    Returns:
        RunSettings with derived beats, section_length, model, resolved_tts_config.
    """
    config_path = config_path or Path("config/")

    if word_count is not None:
        if beats_arg is not None:
            section_length_per = word_count / beats_arg
            beats = beats_arg
        else:
            baseline = (
                section_length_arg
                if section_length_arg is not None
                else _section_length_midpoint(app_config.section_length)
            )
            beats = max(1, min(20, round(word_count / baseline)))
            section_length_per = word_count / beats
        lo = int(section_length_per * 0.8)
        hi = int(section_length_per * 1.2)
        section_length = f"{lo}-{hi}"
    else:
        beats = beats_arg
        if beats is None and sections_arg is not None:
            beats = sections_arg
        if beats is None:
            beats = app_config.beats
        if section_length_arg is not None:
            lo = int(section_length_arg * 0.8)
            hi = int(section_length_arg * 1.2)
            section_length = f"{lo}-{hi}"
        else:
            section_length = app_config.section_length

    model = model_arg if model_arg is not None else app_config.model

    resolved_tts_config: dict[str, Any] | None = None
    if tts_enabled:
        resolved_tts_config = dict(app_config.resolved_tts_config())
        provider = tts_provider or app_config.tts_provider
        resolved_tts_config["tts_provider"] = provider
        defaults = TTS_PROVIDER_DEFAULTS.get(provider, TTS_PROVIDER_DEFAULTS["openai"])
        # User passed --tts-provider → use provider defaults for any missing model/voice.
        # User did not pass provider → use app config for model/voice (app is expected to set provider when it sets model/voice).
        use_provider_defaults = tts_provider_cli is not None
        resolved_tts_config["tts_model"] = (
            tts_model
            if tts_model is not None
            else (defaults["tts_model"] if use_provider_defaults else app_config.tts_model)
        )
        resolved_tts_config["tts_voice"] = (
            tts_voice
            if tts_voice is not None
            else (
                defaults["tts_voice"]
                if use_provider_defaults
                else app_config.tts_voice
            )
        )

    return RunSettings(
        app_paths=app_paths,
        app_config=app_config,
        seed=seed,
        beats=beats,
        section_length=section_length,
        run_id=run_id,
        config_path=config_path,
        model=model,
        word_count=word_count,
        tts_enabled=tts_enabled,
        resolved_tts_config=resolved_tts_config,
    )
