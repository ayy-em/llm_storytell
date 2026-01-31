"""Tests for TTS provider abstraction and OpenAI implementation."""

from __future__ import annotations

from typing import Any

import pytest

from llm_storytell.tts_providers import (
    TTSProvider,
    TTSProviderError,
    TTSResult,
)
from llm_storytell.tts_providers.openai_tts import OpenAITTSProvider


class TestTTSResult:
    """Tests for the TTSResult dataclass."""

    def test_holds_audio_and_metadata(self) -> None:
        """TTSResult stores audio bytes and optional usage metadata."""
        result = TTSResult(
            audio=b"\xff\xfb\x90\x00",
            provider="openai",
            model="tts-1",
            voice="onyx",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            raw_response={"input_tokens": 10},
        )
        assert result.audio == b"\xff\xfb\x90\x00"
        assert result.provider == "openai"
        assert result.model == "tts-1"
        assert result.voice == "onyx"
        assert result.prompt_tokens == 10
        assert result.completion_tokens == 5
        assert result.total_tokens == 15
        assert result.raw_response == {"input_tokens": 10}

    def test_usage_optional(self) -> None:
        """TTSResult allows None for usage fields (best-effort)."""
        result = TTSResult(
            audio=b"audio",
            provider="openai",
            model="tts-1",
            voice="alloy",
        )
        assert result.prompt_tokens is None
        assert result.completion_tokens is None
        assert result.total_tokens is None
        assert result.raw_response is None


class TestTTSProviderInterface:
    """Tests for the TTSProvider interface."""

    def test_synthesize_not_implemented(self) -> None:
        """Base TTSProvider.synthesize raises NotImplementedError."""
        provider = TTSProvider(provider_name="test-provider")
        with pytest.raises(NotImplementedError) as exc_info:
            provider.synthesize("Hello", model="tts-1", voice="onyx")
        assert "synthesize() is not implemented" in str(exc_info.value)


class _FakeTTSClient:
    """Test double for the TTS client callable."""

    def __init__(
        self,
        returns: list[bytes | tuple[bytes, dict[str, Any] | None]] | None = None,
    ) -> None:
        self._returns = list(returns or [])
        self.calls: list[dict[str, Any]] = []
        self._raise: Exception | None = None

    def set_raise(self, exc: Exception) -> None:
        """Configure the client to raise on next call."""
        self._raise = exc

    def __call__(
        self,
        text: str,
        *,
        model: str,
        voice: str,
        **kwargs: Any,
    ) -> bytes | tuple[bytes, dict[str, Any] | None]:
        self.calls.append({"text": text, "model": model, "voice": voice, **kwargs})
        if self._raise is not None:
            exc, self._raise = self._raise, None
            raise exc
        if not self._returns:
            raise RuntimeError("no fake response configured")
        return self._returns.pop(0)


class TestOpenAITTSProviderSuccess:
    """OpenAITTSProvider happy-path behaviour."""

    def test_synthesize_returns_tts_result_with_usage(self) -> None:
        """Successful call returns TTSResult with audio and token usage."""
        audio_bytes = b"\xff\xfb\x90\x00\x00"
        usage = {
            "input_tokens": 50,
            "output_tokens": 100,
            "total_tokens": 150,
        }
        client = _FakeTTSClient(returns=[(audio_bytes, usage)])
        provider = OpenAITTSProvider(
            client,
            default_model="tts-1",
            default_voice="onyx",
            speed=1.0,
        )

        result = provider.synthesize("Hello world", speed=1.2)

        assert isinstance(result, TTSResult)
        assert result.audio == audio_bytes
        assert result.provider == "openai"
        assert result.model == "tts-1"
        assert result.voice == "onyx"
        assert result.prompt_tokens == 50
        assert result.completion_tokens == 100
        assert result.total_tokens == 150
        assert result.raw_response == usage

        assert len(client.calls) == 1
        call = client.calls[0]
        assert call["text"] == "Hello world"
        assert call["model"] == "tts-1"
        assert call["voice"] == "onyx"
        assert call["speed"] == 1.2

    def test_synthesize_allows_model_voice_override(self) -> None:
        """Caller can override model and voice per call."""
        client = _FakeTTSClient(returns=[(b"audio", None)])
        provider = OpenAITTSProvider(
            client,
            default_model="tts-1",
            default_voice="onyx",
        )

        result = provider.synthesize(
            "Hi",
            model="tts-1-hd",
            voice="nova",
        )

        assert result.model == "tts-1-hd"
        assert result.voice == "nova"
        assert len(client.calls) == 1
        assert client.calls[0]["model"] == "tts-1-hd"
        assert client.calls[0]["voice"] == "nova"

    def test_synthesize_accepts_tts_arguments(self) -> None:
        """Extra kwargs (e.g. tts_arguments) are passed to the client."""
        client = _FakeTTSClient(returns=[(b"audio", None)])
        provider = OpenAITTSProvider(
            client,
            default_model="gpt-4o-mini-tts",
            default_voice="Onyx",
            response_format="mp3",
        )

        provider.synthesize(
            "Text",
            speed=1.1,
            response_format="opus",
        )

        call = client.calls[0]
        assert call["speed"] == 1.1
        assert call["response_format"] == "opus"

    def test_client_can_return_bytes_only(self) -> None:
        """Client may return only bytes; usage is None (best-effort)."""
        client = _FakeTTSClient(returns=[b"raw-audio-bytes"])
        provider = OpenAITTSProvider(
            client,
            default_model="tts-1",
            default_voice="alloy",
        )

        result = provider.synthesize("No usage")

        assert result.audio == b"raw-audio-bytes"
        assert result.prompt_tokens is None
        assert result.completion_tokens is None
        assert result.total_tokens is None
        assert result.raw_response is None


class TestOpenAITTSProviderErrorPropagation:
    """Tests for error propagation."""

    def test_client_exception_raises_tts_provider_error(self) -> None:
        """When the client raises, TTSProviderError is raised with message."""
        client = _FakeTTSClient(returns=[(b"x", None)])
        client.set_raise(ValueError("Invalid voice"))
        provider = OpenAITTSProvider(
            client,
            default_model="tts-1",
            default_voice="onyx",
        )

        with pytest.raises(TTSProviderError) as exc_info:
            provider.synthesize("Hi")

        assert "OpenAI TTS call failed" in str(exc_info.value)
        assert "Invalid voice" in str(exc_info.value)
        assert exc_info.value.__cause__ is not None

    def test_client_returns_non_bytes_raises(self) -> None:
        """When client returns non-bytes (and not tuple), TTSProviderError."""
        client = _FakeTTSClient(returns=[("not-bytes", None)])  # type: ignore[list-item]

        provider = OpenAITTSProvider(
            client,
            default_model="tts-1",
            default_voice="onyx",
        )

        with pytest.raises(TTSProviderError) as exc_info:
            provider.synthesize("Hi")

        assert "return bytes" in str(exc_info.value).lower()


class TestOpenAITTSProviderUsageExtraction:
    """Tests for token usage extraction (best-effort)."""

    def test_usage_prompt_completion_total_keys(self) -> None:
        """Usage dict with prompt_tokens, completion_tokens, total_tokens is extracted."""
        client = _FakeTTSClient(
            returns=[
                (
                    b"a",
                    {
                        "prompt_tokens": 10,
                        "completion_tokens": 20,
                        "total_tokens": 30,
                    },
                )
            ]
        )
        provider = OpenAITTSProvider(
            client,
            default_model="tts-1",
            default_voice="onyx",
        )

        result = provider.synthesize("Hi")

        assert result.prompt_tokens == 10
        assert result.completion_tokens == 20
        assert result.total_tokens == 30

    def test_usage_input_output_keys_mapped(self) -> None:
        """Usage dict with input_tokens, output_tokens is mapped to result."""
        client = _FakeTTSClient(
            returns=[
                (
                    b"a",
                    {
                        "input_tokens": 5,
                        "output_tokens": 15,
                    },
                )
            ]
        )
        provider = OpenAITTSProvider(
            client,
            default_model="tts-1",
            default_voice="onyx",
        )

        result = provider.synthesize("Hi")

        assert result.prompt_tokens == 5
        assert result.completion_tokens == 15
        assert result.total_tokens == 20

    def test_usage_empty_or_none_tolerated(self) -> None:
        """Empty or None usage dict yields None usage fields."""
        client = _FakeTTSClient(returns=[(b"a", None), (b"b", {})])
        provider = OpenAITTSProvider(
            client,
            default_model="tts-1",
            default_voice="onyx",
        )

        r1 = provider.synthesize("One")
        r2 = provider.synthesize("Two")

        assert r1.prompt_tokens is None and r1.completion_tokens is None
        assert r2.prompt_tokens is None and r2.completion_tokens is None
