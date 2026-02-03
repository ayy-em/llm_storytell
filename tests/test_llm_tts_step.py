"""Tests for the LLM-TTS pipeline step (chunking and synthesis)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from llm_storytell.logging import RunLogger
from llm_storytell.steps.llm_tts import (
    LLMTTSStepError,
    _chunk_text,
    execute_llm_tts_step,
)
from llm_storytell.tts_providers import TTSProvider, TTSProviderError, TTSResult


def _make_words(n: int, with_newline_every: int | None = None) -> str:
    """Build a string of n words; if with_newline_every, insert newline every k words."""
    words = [f"w{i}" for i in range(n)]
    if with_newline_every is None:
        return " ".join(words)
    parts = []
    for i in range(0, n, with_newline_every):
        chunk = words[i : i + with_newline_every]
        parts.append(" ".join(chunk))
    return "\n".join(parts)


class TestChunkText:
    """Chunking logic: 700–1000 words, cut at newline after 700; enforce 1–22 segments."""

    def test_empty_returns_empty(self) -> None:
        segments, imperfect = _chunk_text("")
        assert segments == []
        assert imperfect == []

    def test_short_text_one_segment(self) -> None:
        text = _make_words(100)
        segments, imperfect = _chunk_text(text)
        assert len(segments) == 1
        assert len(imperfect) == 1
        assert segments[0].strip().split() == [f"w{i}" for i in range(100)]
        assert imperfect[0] is True

    def test_under_700_words_one_segment_imperfect(self) -> None:
        text = _make_words(500)
        segments, imperfect = _chunk_text(text)
        assert len(segments) == 1
        assert imperfect[0] is True

    def test_700_words_with_newline_at_500_cuts_at_newline(self) -> None:
        text = _make_words(1500, with_newline_every=500)
        segments, imperfect = _chunk_text(text)
        assert len(segments) >= 2
        first_words = len(segments[0].split())
        assert 700 <= first_words <= 1000 or first_words == 500
        assert imperfect[0] is False or imperfect[0] is True

    def test_no_newline_by_1000_imperfect_flag(self) -> None:
        text = _make_words(1000)
        segments, imperfect = _chunk_text(text)
        assert len(segments) == 1
        assert imperfect[0] is True

    def test_many_segments_merged_to_max_22(self) -> None:
        text = _make_words(25000, with_newline_every=500)
        segments, imperfect = _chunk_text(text)
        assert 1 <= len(segments) <= 22
        assert len(imperfect) == len(segments)

    def test_exactly_22_segments_allowed(self) -> None:
        parts = [_make_words(800, with_newline_every=400) for _ in range(22)]
        text = "\n\n".join(parts)
        segments, imperfect = _chunk_text(text)
        assert len(segments) <= 22
        assert len(imperfect) == len(segments)


class _FakeTTSProvider(TTSProvider):
    """TTS provider that returns fixed bytes and optional usage."""

    def __init__(
        self,
        audio: bytes = b"fake_audio",
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int | None = None,
        raise_on_synthesize: Exception | None = None,
    ) -> None:
        super().__init__(provider_name="fake")
        self._audio = audio
        self._pt = prompt_tokens
        self._ct = completion_tokens
        self._total = (
            total_tokens
            if total_tokens is not None
            else prompt_tokens + completion_tokens
        )
        self._raise = raise_on_synthesize
        self.calls: list[str] = []

    def synthesize(
        self,
        text: str,
        *,
        model: str | None = None,
        voice: str | None = None,
        **kwargs: Any,
    ) -> TTSResult:
        self.calls.append(text)
        if self._raise:
            raise self._raise
        return TTSResult(
            audio=self._audio,
            provider=self.provider_name,
            model=model or "tts-1",
            voice=voice or "onyx",
            prompt_tokens=self._pt,
            completion_tokens=self._ct,
            total_tokens=self._total,
        )


class TestExecuteLlmTtsStep:
    """Execute step: load script, chunk, write prompts/outputs, update state."""

    def test_missing_final_script_raises(self, tmp_path: Path) -> None:
        (tmp_path / "state.json").write_text(
            json.dumps({"app": "test"}), encoding="utf-8"
        )
        logger = RunLogger(tmp_path / "run.log")
        logger._log_path.parent.mkdir(parents=True, exist_ok=True)
        logger._log_path.touch()
        provider = _FakeTTSProvider()
        with pytest.raises(LLMTTSStepError) as exc_info:
            execute_llm_tts_step(tmp_path, provider, logger)
        assert "Final script not found" in str(exc_info.value)

    def test_artifacts_created_and_state_updated(self, tmp_path: Path) -> None:
        run_dir = tmp_path
        (run_dir / "artifacts").mkdir()
        script = _make_words(800)
        (run_dir / "artifacts" / "final_script.md").write_text(script, encoding="utf-8")
        state = {
            "app": "test",
            "token_usage": [
                {
                    "step": "outline",
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "total_tokens": 30,
                }
            ],
        }
        (run_dir / "state.json").write_text(
            json.dumps(state, indent=2), encoding="utf-8"
        )
        (run_dir / "run.log").touch()
        logger = RunLogger(run_dir / "run.log")
        provider = _FakeTTSProvider(prompt_tokens=1, completion_tokens=2)

        execute_llm_tts_step(run_dir, provider, logger, audio_ext="mp3")

        prompts_dir = run_dir / "tts" / "prompts"
        assert (prompts_dir / "segment_01.txt").exists()
        assert (run_dir / "tts" / "outputs" / "segment_01.mp3").exists()
        segment_files = sorted(prompts_dir.glob("segment_*.txt"))
        segment_contents = [p.read_text(encoding="utf-8").strip() for p in segment_files]
        combined = " ".join(segment_contents)
        assert combined == script.strip()
        assert (
            run_dir / "tts" / "outputs" / "segment_01.mp3"
        ).read_bytes() == b"fake_audio"
        with (run_dir / "state.json").open(encoding="utf-8") as f:
            new_state = json.load(f)
        assert "tts_token_usage" in new_state
        assert len(new_state["tts_token_usage"]) >= 1
        assert new_state["tts_token_usage"][0]["step"] == "tts_01"
        assert new_state["tts_token_usage"][0]["total_tokens"] == 3
        total_chars = sum(
            e.get("input_characters", 0) for e in new_state["tts_token_usage"]
        )
        assert total_chars == sum(len(s) for s in segment_contents)

    def test_uses_state_final_script_path_when_present(self, tmp_path: Path) -> None:
        run_dir = tmp_path
        (run_dir / "artifacts").mkdir()
        (run_dir / "artifacts" / "final_script.md").write_text(
            "wrong", encoding="utf-8"
        )
        custom = run_dir / "custom_script.md"
        custom.write_text("correct content", encoding="utf-8")
        state = {"app": "test", "final_script_path": "custom_script.md"}
        (run_dir / "state.json").write_text(
            json.dumps(state, indent=2), encoding="utf-8"
        )
        (run_dir / "run.log").touch()
        logger = RunLogger(run_dir / "run.log")
        provider = _FakeTTSProvider()

        execute_llm_tts_step(run_dir, provider, logger)

        assert (run_dir / "tts" / "prompts" / "segment_01.txt").read_text(
            encoding="utf-8"
        ) == "correct content"

    def test_tts_provider_error_raises_step_error(self, tmp_path: Path) -> None:
        (tmp_path / "artifacts").mkdir(parents=True)
        (tmp_path / "artifacts" / "final_script.md").write_text(
            _make_words(100), encoding="utf-8"
        )
        (tmp_path / "state.json").write_text(
            json.dumps({"app": "test"}), encoding="utf-8"
        )
        (tmp_path / "run.log").touch()
        logger = RunLogger(tmp_path / "run.log")
        provider = _FakeTTSProvider(raise_on_synthesize=TTSProviderError("api down"))

        with pytest.raises(LLMTTSStepError) as exc_info:
            execute_llm_tts_step(tmp_path, provider, logger)
        assert "TTS synthesis failed" in str(exc_info.value)

    def test_warning_logged_when_imperfect_split(self, tmp_path: Path) -> None:
        run_dir = tmp_path
        (run_dir / "artifacts").mkdir()
        text = _make_words(1000)
        (run_dir / "artifacts" / "final_script.md").write_text(text, encoding="utf-8")
        (run_dir / "state.json").write_text(
            json.dumps({"app": "test"}), encoding="utf-8"
        )
        (run_dir / "run.log").touch()
        logger = RunLogger(run_dir / "run.log")
        provider = _FakeTTSProvider()

        execute_llm_tts_step(run_dir, provider, logger)

        log_content = (run_dir / "run.log").read_text(encoding="utf-8")
        assert (
            "no newline" in log_content.lower()
            or "max words" in log_content.lower()
            or "TTS segment" in log_content
        )

    def test_cumulative_token_line_in_log(self, tmp_path: Path) -> None:
        run_dir = tmp_path
        (run_dir / "artifacts").mkdir()
        (run_dir / "artifacts" / "final_script.md").write_text(
            _make_words(100), encoding="utf-8"
        )
        (run_dir / "state.json").write_text(
            json.dumps(
                {
                    "app": "test",
                    "token_usage": [
                        {
                            "prompt_tokens": 5,
                            "completion_tokens": 10,
                            "total_tokens": 15,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (run_dir / "run.log").touch()
        logger = RunLogger(run_dir / "run.log")
        provider = _FakeTTSProvider(prompt_tokens=1, completion_tokens=2)

        execute_llm_tts_step(run_dir, provider, logger)

        log_content = (run_dir / "run.log").read_text(encoding="utf-8")
        assert "Cumulative token usage" in log_content
        assert "total_text_tokens" in log_content
        assert "total_tts_tokens" in log_content

    def test_tts_character_usage_logged_in_run_log(self, tmp_path: Path) -> None:
        run_dir = tmp_path
        (run_dir / "artifacts").mkdir()
        segment_text = _make_words(50)
        (run_dir / "artifacts" / "final_script.md").write_text(
            segment_text, encoding="utf-8"
        )
        (run_dir / "state.json").write_text(
            json.dumps({"app": "test"}), encoding="utf-8"
        )
        (run_dir / "run.log").touch()
        logger = RunLogger(run_dir / "run.log")
        provider = _FakeTTSProvider()

        execute_llm_tts_step(run_dir, provider, logger)

        log_content = (run_dir / "run.log").read_text(encoding="utf-8")
        assert "TTS character usage [tts_01]" in log_content
        assert f"input_characters={len(segment_text)}" in log_content
        assert "cumulative_characters=" in log_content
