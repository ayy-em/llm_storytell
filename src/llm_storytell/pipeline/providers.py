"""Pipeline provider creation: LLM and TTS from config.

Creates provider instances from config path and resolved settings.
Raises on error; no sys.exit. Caller (CLI or runner) prints and exits.
"""

import json
from pathlib import Path
from typing import Any

from llm_storytell.llm import LLMProvider, OpenAIProvider
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
) -> OpenAITTSProvider:
    """Create TTS provider from config and resolved TTS config.

    Args:
        config_path: Path to config directory (creds.json).
        resolved_tts_config: Dict with tts_provider, tts_model, tts_voice, tts_arguments.

    Returns:
        TTS provider instance (e.g. OpenAITTSProvider).

    Raises:
        ProviderError: If provider unsupported, openai not installed, key missing, or creation fails.
    """
    cfg = resolved_tts_config or {}
    provider_id = cfg.get("tts_provider") or "openai"
    if provider_id != "openai":
        raise ProviderError(
            f"Unsupported TTS provider '{provider_id}'. Only 'openai' is supported."
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
        client = OpenAI(api_key=api_key)
        tts_model = cfg.get("tts_model") or "gpt-4o-mini-tts"
        tts_voice = cfg.get("tts_voice") or "Onyx"
        tts_arguments = cfg.get("tts_arguments") or {}

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
