"""TTS provider abstraction.

This module defines the public interface for text-to-speech synthesis
from the pipeline, along with an OpenAI-backed implementation.

Design goals
------------

* Pipeline steps must not call vendor SDKs directly.
* Providers can be swapped without changing step code.
* Provider responses expose audio bytes and optional token/usage
  metadata (best-effort) for logging and state updates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class TTSResult:
    """Result of a single TTS synthesis call.

    Attributes:
        audio:
            Raw audio bytes (e.g. MP3) returned by the provider.
        provider:
            Provider identifier (e.g. ``\"openai\"``).
        model:
            Model identifier used for the call.
        voice:
            Voice identifier used for the call.
        prompt_tokens:
            Input/token count if reported by the provider (best-effort).
        completion_tokens:
            Output/token count if reported by the provider (best-effort).
        total_tokens:
            Total tokens if reported by the provider (best-effort).
        raw_response:
            Provider-specific raw response, retained for debugging.
            Callers should not rely on its shape.
    """

    audio: bytes
    provider: str
    model: str
    voice: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    raw_response: Any | None = None


class TTSProviderError(RuntimeError):
    """Raised when a TTS provider call fails."""


class TTSProvider:
    """Abstract base class for TTS providers.

    Implementations must override :meth:`synthesize` and return
    :class:`TTSResult` instances. The interface is minimal and
    vendor-agnostic so that pipeline steps do not depend on
    specific SDKs.
    """

    provider_name: str

    def __init__(self, provider_name: str) -> None:
        self.provider_name = provider_name

    def synthesize(
        self,
        text: str,
        *,
        model: str | None = None,
        voice: str | None = None,
        **kwargs: Any,
    ) -> TTSResult:  # pragma: no cover - interface only
        """Convert text to audio.

        Args:
            text:
                Text to synthesize to speech.
            model:
                Optional model identifier. If omitted, the provider's
                default model is used.
            voice:
                Optional voice identifier. If omitted, the provider's
                default voice is used.
            **kwargs:
                Provider-specific parameters (e.g. ``speed``,
                ``response_format``). Callers should pass only simple,
                serializable values.

        Returns:
            :class:`TTSResult` with audio bytes and optional usage metadata.
        """
        msg = f"{self.__class__.__name__}.synthesize() is not implemented"
        raise NotImplementedError(msg)
