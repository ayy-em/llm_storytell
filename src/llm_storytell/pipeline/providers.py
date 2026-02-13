"""Pipeline provider creation: LLM and TTS from config.

Creates provider instances from config path and resolved settings.
Raises on error; no sys.exit. Caller (CLI or runner) prints and exits.
"""

import json
from pathlib import Path
from typing import Any

from llm_storytell.llm import LLMProvider, OpenAIProvider
from llm_storytell.tts_providers import TTSProvider
from llm_storytell.tts_providers.elevenlabs_tts import (
    DEFAULT_VOICE_ID,
    ElevenLabsTTSProvider,
    _elevenlabs_model_from_config,
)
from llm_storytell.tts_providers.openai_tts import OpenAITTSProvider


class ProviderError(Exception):
    """Raised when a provider cannot be created (missing key, unsupported, etc.)."""

    pass


def _load_creds_api_key(config_path: Path) -> str | None:
    """Load OpenAI API key from config_path/creds.json. Returns None if missing/invalid."""
    creds_path = config_path / "creds.json"
    if not creds_path.exists():
        return None
    try:
        with creds_path.open(encoding="utf-8") as f:
            creds = json.load(f)
        return (
            creds.get("openai_api_key")
            or creds.get("OPENAI_KEY")
            or creds.get("OPEN_AI")
            or creds.get("OPENAI_API_KEY")
        )
    except (OSError, json.JSONDecodeError, KeyError):
        return None


def _load_elevenlabs_api_key(config_path: Path) -> str | None:
    """Load ElevenLabs API key from config_path/creds.json. Returns None if missing/invalid."""
    creds_path = config_path / "creds.json"
    if not creds_path.exists():
        return None
    try:
        with creds_path.open(encoding="utf-8") as f:
            creds = json.load(f)
        return creds.get("ELEVENLABS_API_KEY") or creds.get("elevenlabs_api_key")
    except (OSError, json.JSONDecodeError, KeyError):
        return None


def create_llm_provider(
    config_path: Path, default_model: str = "gpt-4.1-mini"
) -> LLMProvider:
    """Create LLM provider from configuration.

    Args:
        config_path: Path to config directory (creds.json).
        default_model: Model to use for all LLM calls.

    Returns:
        LLM provider instance (e.g. OpenAIProvider).

    Raises:
        ProviderError: If openai is not installed, API key is missing, or creation fails.
    """
    try:
        from openai import OpenAI
    except ImportError as e:
        raise ProviderError(
            "openai package not installed. Install with: pip install openai"
        ) from e

    api_key = _load_creds_api_key(config_path)
    if not api_key:
        raise ProviderError(
            "No OpenAI API key found. "
            "Create config/creds.json with one of these fields: "
            "'openai_api_key', 'OPENAI_KEY', 'OPEN_AI', or 'OPENAI_API_KEY'."
        )

    try:
        client = OpenAI(api_key=api_key)

        def openai_client_wrapper(
            prompt: str, model: str, **kwargs: Any
        ) -> dict[str, Any]:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                **kwargs,
            )
            return {
                "choices": [
                    {"message": {"content": response.choices[0].message.content}}
                ],
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
            }

        return OpenAIProvider(
            client=openai_client_wrapper,
            default_model=default_model,
            temperature=0.7,
        )
    except Exception as e:
        raise ProviderError(f"Error creating LLM provider: {e}") from e


def create_tts_provider(
    config_path: Path, resolved_tts_config: dict[str, Any]
) -> TTSProvider:
    """Create TTS provider from config and resolved TTS config.

    Args:
        config_path: Path to config directory (creds.json).
        resolved_tts_config: Dict with tts_provider, tts_model, tts_voice, tts_arguments.

    Returns:
        TTS provider instance (e.g. OpenAITTSProvider, ElevenLabsTTSProvider).

    Raises:
        ProviderError: If provider unsupported, SDK not installed, key missing, or creation fails.
    """
    cfg = resolved_tts_config or {}

    # Support both snake_case (from AppConfig/resolved_tts_config) and hyphenated keys (from raw YAML)
    def _get_cfg(key: str, hyphen_key: str, default: Any) -> Any:
        return cfg.get(key) or cfg.get(hyphen_key) or default

    provider_id = _get_cfg("tts_provider", "tts-provider", "openai")
    if provider_id == "elevenlabs":
        return _create_elevenlabs_tts_provider(config_path, _get_cfg)
    if provider_id != "openai":
        raise ProviderError(
            f"Unsupported TTS provider '{provider_id}'. Supported: 'openai', 'elevenlabs'."
        )

    api_key = _load_creds_api_key(config_path)
    if not api_key:
        raise ProviderError(
            "No OpenAI API key found for TTS. "
            "Create config/creds.json with one of: "
            "'openai_api_key', 'OPENAI_KEY', 'OPEN_AI', or 'OPENAI_API_KEY'."
        )

    try:
        from openai import OpenAI
    except ImportError as e:
        raise ProviderError(
            "openai package not installed. Install with: pip install openai"
        ) from e

    try:
        # Always use official OpenAI API for TTS; audio/speech is not supported by most proxies (OpenRouter, etc.)
        client = OpenAI(api_key=api_key, base_url="https://api.openai.com/v1")
        tts_model = _get_cfg("tts_model", "tts-model", "gpt-4o-mini-tts")
        tts_voice_raw = _get_cfg("tts_voice", "tts-voice", "onyx")
        # OpenAI TTS API requires lowercase voice (e.g. "onyx"); normalize so config can use "Onyx"
        tts_voice = str(tts_voice_raw).lower() if tts_voice_raw else "onyx"
        tts_arguments = _get_cfg("tts_arguments", "tts-arguments", {}) or {}

        def openai_tts_client(
            text: str, model: str, voice: str, **kwargs: Any
        ) -> bytes:
            response = client.audio.speech.create(
                model=model,
                voice=voice,
                input=text,
                **{**tts_arguments, **kwargs},
            )
            return response.content

        return OpenAITTSProvider(
            client=openai_tts_client,
            default_model=tts_model,
            default_voice=tts_voice,
            **tts_arguments,
        )
    except Exception as e:
        raise ProviderError(f"Error creating TTS provider: {e}") from e


def _create_elevenlabs_tts_provider(
    config_path: Path,
    get_cfg: Any,
) -> ElevenLabsTTSProvider:
    """Create ElevenLabs TTS provider. Uses ELEVENLABS_API_KEY from config/creds.json."""
    try:
        from elevenlabs.client import ElevenLabs
    except ImportError as e:
        raise ProviderError(
            "elevenlabs package not installed. Install with: pip install elevenlabs"
        ) from e

    api_key = _load_elevenlabs_api_key(config_path)
    if not api_key:
        raise ProviderError(
            "No ElevenLabs API key found. Add ELEVENLABS_API_KEY to config/creds.json."
        )

    try:
        client = ElevenLabs(api_key=api_key)
        # Ignore OpenAI model names from app config (e.g. tts-1, gpt-4o-mini-tts)
        configured_model = get_cfg("tts_model", "tts-model", None)
        tts_model = _elevenlabs_model_from_config(configured_model)
        tts_voice = get_cfg("tts_voice", "tts-voice", DEFAULT_VOICE_ID)
        tts_voice = str(tts_voice).strip() if tts_voice else DEFAULT_VOICE_ID
        raw_args = get_cfg("tts_arguments", "tts-arguments", {}) or {}
        tts_arguments = dict(raw_args)
        output_format = tts_arguments.pop("output_format", "mp3_44100_128")
        return ElevenLabsTTSProvider(
            client=client,
            default_model=tts_model,
            default_voice=tts_voice,
            output_format=output_format,
            **tts_arguments,
        )
    except Exception as e:
        raise ProviderError(f"Error creating ElevenLabs TTS provider: {e}") from e
