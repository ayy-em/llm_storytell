"""Tests for ElevenLabs TTS provider."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from llm_storytell.tts_providers import TTSProviderError, TTSResult
from llm_storytell.tts_providers.elevenlabs_tts import (
    DEFAULT_VOICE_ID,
    DEFAULT_MODEL_ID,
    ElevenLabsTTSProvider,
    _audio_to_bytes,
    _elevenlabs_model_from_config,
    _is_openai_tts_model,
)


class TestOpenAIModelGuard:
    """Guard so OpenAI TTS model names are not sent to ElevenLabs."""

    def test_tts1_is_openai(self) -> None:
        assert _is_openai_tts_model("tts-1") is True
        assert _is_openai_tts_model("tts-1-hd") is True

    def test_gpt4o_mini_is_openai(self) -> None:
        assert _is_openai_tts_model("gpt-4o-mini-tts") is True
        assert _is_openai_tts_model("gpt-4o-mini") is True

    def test_elevenlabs_model_not_openai(self) -> None:
        assert _is_openai_tts_model("eleven_multilingual_v2") is False
        assert _is_openai_tts_model("eleven_monolingual_v1") is False

    def test_elevenlabs_model_from_config_uses_default_for_openai(self) -> None:
        assert _elevenlabs_model_from_config("tts-1") == DEFAULT_MODEL_ID
        assert _elevenlabs_model_from_config("gpt-4o-mini-tts") == DEFAULT_MODEL_ID
        assert _elevenlabs_model_from_config(None) == DEFAULT_MODEL_ID
        assert _elevenlabs_model_from_config("") == DEFAULT_MODEL_ID

    def test_elevenlabs_model_from_config_keeps_elevenlabs_id(self) -> None:
        assert (
            _elevenlabs_model_from_config("eleven_multilingual_v2")
            == "eleven_multilingual_v2"
        )
        assert _elevenlabs_model_from_config("eleven_turbo_v2") == "eleven_turbo_v2"


class TestAudioToBytes:
    """Tests for _audio_to_bytes helper."""

    def test_bytes_passthrough(self) -> None:
        data = b"\xff\xfb\x90\x00"
        assert _audio_to_bytes(data) == data

    def test_readable_returns_read(self) -> None:
        data = b"mp3content"
        obj = MagicMock()
        obj.read.return_value = data
        assert _audio_to_bytes(obj) == data

    def test_iterable_chunks_joined(self) -> None:
        chunks = [b"ab", b"cd", b"ef"]
        assert _audio_to_bytes(iter(chunks)) == b"abcdef"

    def test_unexpected_type_raises(self) -> None:
        with pytest.raises(TTSProviderError) as exc_info:
            _audio_to_bytes("not bytes or stream")
        assert "unexpected type" in str(exc_info.value).lower()


class _FakeElevenLabsClient:
    """Test double for ElevenLabs client with text_to_speech.convert."""

    def __init__(
        self,
        returns: bytes | list[bytes] | None = None,
        raise_exc: Exception | None = None,
    ) -> None:
        self._returns = [returns] if isinstance(returns, bytes) else (returns or [b""])
        self._raise = raise_exc
        self.calls: list[dict[str, Any]] = []

    def convert(self, **kwargs: Any) -> bytes:
        self.calls.append(kwargs)
        if self._raise is not None:
            raise self._raise
        if not self._returns:
            return b""
        return self._returns.pop(0)

    @property
    def text_to_speech(self) -> Any:
        return self


class TestElevenLabsTTSProviderSuccess:
    """ElevenLabsTTSProvider happy-path behaviour."""

    def test_synthesize_returns_tts_result(self) -> None:
        audio_bytes = b"\xff\xfb\x90\x00"
        client = _FakeElevenLabsClient(returns=audio_bytes)
        provider = ElevenLabsTTSProvider(
            client=client,
            default_model="eleven_multilingual_v2",
            default_voice=DEFAULT_VOICE_ID,
        )

        result = provider.synthesize("Hello world")

        assert isinstance(result, TTSResult)
        assert result.audio == audio_bytes
        assert result.provider == "elevenlabs"
        assert result.model == "eleven_multilingual_v2"
        assert result.voice == DEFAULT_VOICE_ID
        assert result.prompt_tokens is None
        assert result.completion_tokens is None
        assert result.total_tokens is None
        assert len(client.calls) == 1
        call = client.calls[0]
        assert call["text"] == "Hello world"
        assert call["voice_id"] == DEFAULT_VOICE_ID
        assert call["model_id"] == "eleven_multilingual_v2"

    def test_synthesize_allows_model_voice_override(self) -> None:
        client = _FakeElevenLabsClient(returns=b"audio")
        provider = ElevenLabsTTSProvider(
            client=client,
            default_model="eleven_multilingual_v2",
            default_voice=DEFAULT_VOICE_ID,
        )

        result = provider.synthesize(
            "Hi",
            model="eleven_monolingual_v1",
            voice="other_voice_id",
        )

        assert result.model == "eleven_monolingual_v1"
        assert result.voice == "other_voice_id"
        assert client.calls[0]["model_id"] == "eleven_monolingual_v1"
        assert client.calls[0]["voice_id"] == "other_voice_id"

    def test_synthesize_passes_output_format(self) -> None:
        client = _FakeElevenLabsClient(returns=b"audio")
        provider = ElevenLabsTTSProvider(
            client=client,
            default_voice=DEFAULT_VOICE_ID,
            output_format="mp3_44100_128",
        )
        provider.synthesize("Text")
        assert client.calls[0]["output_format"] == "mp3_44100_128"

    def test_synthesize_ignores_openai_model_from_step(self) -> None:
        """When step passes tts_model=tts-1 (from app config), use provider default."""
        client = _FakeElevenLabsClient(returns=[b"audio1", b"audio2"])
        provider = ElevenLabsTTSProvider(
            client=client,
            default_model="eleven_multilingual_v2",
            default_voice=DEFAULT_VOICE_ID,
        )
        provider.synthesize("Hi", model="tts-1")
        assert client.calls[0]["model_id"] == "eleven_multilingual_v2"
        provider.synthesize("Hi", model="gpt-4o-mini-tts")
        assert client.calls[1]["model_id"] == "eleven_multilingual_v2"


class TestElevenLabsTTSProviderErrors:
    """Error propagation and empty response."""

    def test_client_exception_raises_tts_provider_error(self) -> None:
        client = _FakeElevenLabsClient(returns=b"x", raise_exc=ValueError("API error"))
        provider = ElevenLabsTTSProvider(
            client=client,
            default_voice=DEFAULT_VOICE_ID,
        )

        with pytest.raises(TTSProviderError) as exc_info:
            provider.synthesize("Hi")

        assert "ElevenLabs TTS call failed" in str(exc_info.value)
        assert "API error" in str(exc_info.value)

    def test_empty_audio_raises(self) -> None:
        client = _FakeElevenLabsClient(returns=b"")
        provider = ElevenLabsTTSProvider(
            client=client,
            default_voice=DEFAULT_VOICE_ID,
        )

        with pytest.raises(TTSProviderError) as exc_info:
            provider.synthesize("Hi")

        assert "no audio" in str(exc_info.value).lower()
