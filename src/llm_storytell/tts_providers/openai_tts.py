"""OpenAI-backed TTS provider implementation."""

from __future__ import annotations

from typing import Any, Callable

from llm_storytell.tts_providers import TTSProvider, TTSProviderError, TTSResult


def _extract_usage(
    usage: dict[str, Any] | None,
) -> tuple[int | None, int | None, int | None]:
    """Extract prompt_tokens, completion_tokens, total_tokens from usage dict.

    Accepts common key names: prompt_tokens/input_tokens, completion_tokens/output_tokens,
    total_tokens. Returns (None, None, None) if usage is None or empty.
    """
    if not usage:
        return None, None, None
    prompt = usage.get("prompt_tokens") or usage.get("input_tokens")
    completion = usage.get("completion_tokens") or usage.get("output_tokens")
    total = usage.get("total_tokens")
    if total is None and isinstance(prompt, int) and isinstance(completion, int):
        total = prompt + completion
    return (
        int(prompt) if prompt is not None else None,
        int(completion) if completion is not None else None,
        int(total) if total is not None else None,
    )


class OpenAITTSProvider(TTSProvider):
    """OpenAI-backed :class:`TTSProvider` implementation.

    This provider is decoupled from the OpenAI SDK so that unit tests
    can run without network access. A callable must be supplied that
    performs the underlying TTS API call.

    The callable is expected to accept ``text``, ``model``, and ``voice``
    as keyword arguments, plus any additional parameters (e.g. from
    tts_arguments), and return either:

    - ``(audio_bytes, usage_dict | None)``, or
    - ``audio_bytes`` (usage will be None).

    The usage dict may contain ``prompt_tokens``/``input_tokens``,
    ``completion_tokens``/``output_tokens``, and ``total_tokens``
    (best-effort; extraction is tolerant of missing keys).
    """

    def __init__(
        self,
        client: Callable[..., bytes | tuple[bytes, dict[str, Any] | None]],
        *,
        default_model: str,
        default_voice: str,
        **default_params: Any,
    ) -> None:
        """Create a new OpenAI TTS provider.

        Args:
            client:
                Callable that performs the underlying TTS request
                (e.g. a wrapper around ``OpenAI().audio.speech.create``)
                and returns audio bytes, optionally with a usage dict.
            default_model:
                Default model identifier when ``model`` is not
                provided to :meth:`synthesize`.
            default_voice:
                Default voice identifier when ``voice`` is not
                provided to :meth:`synthesize`.
            **default_params:
                Default synthesis parameters (e.g. ``response_format``,
                ``speed``) merged with per-call overrides.
        """
        super().__init__(provider_name="openai")
        self._client = client
        self._default_model = default_model
        self._default_voice = default_voice
        self._default_params = default_params

    def synthesize(
        self,
        text: str,
        *,
        model: str | None = None,
        voice: str | None = None,
        **kwargs: Any,
    ) -> TTSResult:
        """Synthesize text to audio using the OpenAI TTS API."""
        effective_model = model or self._default_model
        effective_voice = voice or self._default_voice
        params: dict[str, Any] = {**self._default_params, **kwargs}

        try:
            raw = self._client(
                text=text,
                model=effective_model,
                voice=effective_voice,
                **params,
            )
        except Exception as exc:
            raise TTSProviderError(f"OpenAI TTS call failed: {exc!s}") from exc

        if isinstance(raw, tuple):
            audio_bytes, usage_dict = raw[0], raw[1]
        else:
            audio_bytes, usage_dict = raw, None

        if not isinstance(audio_bytes, bytes):
            raise TTSProviderError(
                "OpenAI TTS client must return bytes or (bytes, usage_dict)"
            )

        prompt_tokens, completion_tokens, total_tokens = _extract_usage(usage_dict)

        return TTSResult(
            audio=audio_bytes,
            provider=self.provider_name,
            model=effective_model,
            voice=effective_voice,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            raw_response=usage_dict,
        )
