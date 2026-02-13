"""ElevenLabs-backed TTS provider implementation."""

from __future__ import annotations

from typing import Any

from llm_storytell.tts_providers import TTSProvider, TTSProviderError, TTSResult

# Default voice_id per user request
DEFAULT_VOICE_ID = "6FiCmD8eY5VyjOdG5Zjk"
DEFAULT_MODEL_ID = "eleven_multilingual_v2"
DEFAULT_OUTPUT_FORMAT = "mp3_44100_128"

# OpenAI TTS model names; do not send these to ElevenLabs API
_OPENAI_TTS_MODEL_PREFIXES = ("tts-", "gpt-4o-mini", "gpt-4o-")


def _is_openai_tts_model(model_id: str) -> bool:
    """True if model_id looks like an OpenAI TTS model (invalid for ElevenLabs)."""
    s = (model_id or "").strip().lower()
    return any(s.startswith(p) for p in _OPENAI_TTS_MODEL_PREFIXES)


def _elevenlabs_model_from_config(configured: str | None) -> str:
    """Use configured value only if it looks like an ElevenLabs model; else default."""
    s = (configured or "").strip()
    if not s or _is_openai_tts_model(s):
        return DEFAULT_MODEL_ID
    return s


def _audio_to_bytes(audio: Any) -> bytes:
    """Convert ElevenLabs convert() return value to bytes.

    The SDK may return a stream or bytes; we consume it to get a single bytes object.
    """
    if isinstance(audio, bytes):
        return audio
    if hasattr(audio, "read"):
        data = audio.read()
        return data if isinstance(data, bytes) else b""
    if hasattr(audio, "__iter__") and not isinstance(audio, (bytes, str)):
        return b"".join(chunk for chunk in audio if isinstance(chunk, bytes))
    raise TTSProviderError(
        "ElevenLabs TTS returned an unexpected type; cannot get audio bytes"
    )


class ElevenLabsTTSProvider(TTSProvider):
    """ElevenLabs-backed :class:`TTSProvider` implementation.

    Uses the ElevenLabs text-to-speech API. API key is read from
    config/creds.json under ``ELEVENLABS_API_KEY``.
    """

    def __init__(
        self,
        client: Any,
        *,
        default_model: str = DEFAULT_MODEL_ID,
        default_voice: str = DEFAULT_VOICE_ID,
        output_format: str = DEFAULT_OUTPUT_FORMAT,
        **default_params: Any,
    ) -> None:
        """Create a new ElevenLabs TTS provider.

        Args:
            client: ElevenLabs client instance (from elevenlabs.client.ElevenLabs).
            default_model: Default model_id when not provided to synthesize.
            default_voice: Default voice_id when not provided to synthesize.
            output_format: Output format (e.g. mp3_44100_128).
            **default_params: Extra parameters merged with per-call overrides.
        """
        super().__init__(provider_name="elevenlabs")
        self._client = client
        self._default_model = default_model
        self._default_voice = default_voice
        self._output_format = output_format
        self._default_params = default_params

    def synthesize(
        self,
        text: str,
        *,
        model: str | None = None,
        voice: str | None = None,
        **kwargs: Any,
    ) -> TTSResult:
        """Synthesize text to audio using the ElevenLabs API."""
        raw_model = model or self._default_model
        # Pipeline may pass OpenAI tts_model when user switched provider; ignore it
        effective_model = (
            self._default_model if _is_openai_tts_model(raw_model) else raw_model
        )
        effective_voice = voice or self._default_voice
        params: dict[str, Any] = {**self._default_params, **kwargs}
        output_format = params.pop("output_format", self._output_format)

        try:
            audio_response = self._client.text_to_speech.convert(
                text=text,
                voice_id=effective_voice,
                model_id=effective_model,
                output_format=output_format,
                **params,
            )
        except Exception as exc:
            raise TTSProviderError(f"ElevenLabs TTS call failed: {exc!s}") from exc

        try:
            audio_bytes = _audio_to_bytes(audio_response)
        except TTSProviderError:
            raise
        except Exception as exc:
            raise TTSProviderError(
                f"Failed to read ElevenLabs audio response: {exc!s}"
            ) from exc

        if not audio_bytes:
            raise TTSProviderError("ElevenLabs TTS returned no audio data")

        # ElevenLabs does not report token usage; pipeline uses input_characters
        return TTSResult(
            audio=audio_bytes,
            provider=self.provider_name,
            model=effective_model,
            voice=effective_voice,
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            raw_response=None,
        )
