"""Tests for pipeline provider creation (create_tts_provider with openai/elevenlabs)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from llm_storytell.llm import ClaudeProvider
from llm_storytell.pipeline.providers import (
    ProviderError,
    create_llm_provider,
    create_tts_provider,
)
from llm_storytell.tts_providers.elevenlabs_tts import ElevenLabsTTSProvider


class TestCreateTTSProviderElevenlabs:
    """create_tts_provider with tts_provider=elevenlabs."""

    def test_elevenlabs_returns_elevenlabs_provider(self, tmp_path: Path) -> None:
        (tmp_path / "creds.json").write_text(
            json.dumps({"ELEVENLABS_API_KEY": "sk_test_key"}), encoding="utf-8"
        )
        with patch("elevenlabs.client.ElevenLabs") as mock_klass:
            provider = create_tts_provider(
                tmp_path,
                {"tts_provider": "elevenlabs"},
            )
        assert isinstance(provider, ElevenLabsTTSProvider)
        assert provider.provider_name == "elevenlabs"
        mock_klass.assert_called_once_with(api_key="sk_test_key")

    def test_elevenlabs_missing_key_raises(self, tmp_path: Path) -> None:
        (tmp_path / "creds.json").write_text(json.dumps({}), encoding="utf-8")
        with pytest.raises(ProviderError) as exc_info:
            create_tts_provider(tmp_path, {"tts_provider": "elevenlabs"})
        assert "ELEVENLABS_API_KEY" in str(exc_info.value)

    def test_elevenlabs_accepts_elevenlabs_api_key_snake_case(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "creds.json").write_text(
            json.dumps({"elevenlabs_api_key": "sk_alt_key"}), encoding="utf-8"
        )
        with patch("elevenlabs.client.ElevenLabs") as mock_klass:
            create_tts_provider(tmp_path, {"tts_provider": "elevenlabs"})
        mock_klass.assert_called_once_with(api_key="sk_alt_key")

    def test_elevenlabs_uses_default_voice_from_config(self, tmp_path: Path) -> None:
        (tmp_path / "creds.json").write_text(
            json.dumps({"ELEVENLABS_API_KEY": "sk_k"}), encoding="utf-8"
        )
        with patch("elevenlabs.client.ElevenLabs"):
            provider = create_tts_provider(
                tmp_path,
                {"tts_provider": "elevenlabs", "tts_voice": "custom_voice_id"},
            )
        assert isinstance(provider, ElevenLabsTTSProvider)
        assert provider._default_voice == "custom_voice_id"


class TestCreateLLMProvider:
    """create_llm_provider for openai and claude."""

    def test_claude_missing_key_raises(self, tmp_path: Path) -> None:
        (tmp_path / "creds.json").write_text(json.dumps({}), encoding="utf-8")
        with pytest.raises(ProviderError) as exc_info:
            create_llm_provider(
                tmp_path,
                llm_provider="claude",
                default_model="claude-sonnet-4-6",
            )
        assert (
            "Anthropic" in str(exc_info.value)
            or "anthropic" in str(exc_info.value).lower()
        )

    def test_claude_returns_claude_provider(self, tmp_path: Path) -> None:
        (tmp_path / "creds.json").write_text(
            json.dumps({"ANTHROPIC_API_KEY": "sk-ant"}), encoding="utf-8"
        )
        with patch("anthropic.Anthropic") as mock_a:
            mock_msg = mock_a.return_value.messages.create.return_value
            mock_msg.content = [type("B", (), {"type": "text", "text": "ok"})()]
            mock_msg.usage = type("U", (), {"input_tokens": 2, "output_tokens": 3})()
            provider = create_llm_provider(
                tmp_path,
                llm_provider="claude",
                default_model="claude-sonnet-4-6",
            )
        assert isinstance(provider, ClaudeProvider)

    def test_unknown_text_provider_raises(self, tmp_path: Path) -> None:
        (tmp_path / "creds.json").write_text(
            json.dumps({"OPENAI_KEY": "sk"}), encoding="utf-8"
        )
        with pytest.raises(ProviderError) as exc_info:
            create_llm_provider(
                tmp_path,
                llm_provider="unknown-llm",
                default_model="x",
            )
        assert "Unsupported text LLM provider" in str(exc_info.value)


class TestCreateTTSProviderUnsupported:
    """create_tts_provider with unsupported provider id."""

    def test_unknown_provider_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ProviderError) as exc_info:
            create_tts_provider(tmp_path, {"tts_provider": "unknown"})
        assert "Unsupported TTS provider" in str(exc_info.value)
        assert "unknown" in str(exc_info.value)
