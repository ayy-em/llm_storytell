"""Prompt caching: shared template prefix, cache-break handling, SDK wrappers."""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from llm_storytell.llm import (
    CACHE_BREAK_MARKER,
    ClaudeProvider,
    OpenAIProvider,
    split_cache_prefix,
)
from llm_storytell.llm.pricing import estimate_run_cost, sum_cache_tokens
from llm_storytell.llm.token_tracking import record_token_usage
from llm_storytell.logging import RunLogger
from llm_storytell.pipeline import providers as providers_mod
from llm_storytell.prompt_render import render_prompt

PROMPTS = Path(__file__).parent.parent / "prompts" / "app-defaults"

_SHARED_VARS = {
    "seed": "A keeper finds a bottle.",
    "language": "en",
    "lore_bible": "LORE " * 50,
    "style_rules": "Terse.",
    "location_context": "A lighthouse.",
    "character_context": "Mara, keeper.",
}
_STEP_VARS = {
    "10_outline.md": {"beats_count": 3},
    "20_section.md": {
        "section_id": 1,
        "section_index": 0,
        "outline_beat": "{}",
        "rolling_summary": "None.",
        "continuity_context": "None.",
        "section_length": "300-400",
    },
    "30_critic.md": {"outline": "[]", "full_draft": "Draft."},
}


def test_default_templates_share_identical_cacheable_prefix() -> None:
    """Outline, section and critic prompts must share the exact same prefix.

    Byte-identical prefixes let one cache entry serve every call in a run.
    """
    prefixes = []
    for name, step_vars in _STEP_VARS.items():
        rendered = render_prompt(PROMPTS / name, {**_SHARED_VARS, **step_vars})
        assert rendered.count(CACHE_BREAK_MARKER) == 1, name
        prefix, rest = split_cache_prefix(rendered)
        assert prefix is not None and rest.strip()
        prefixes.append(prefix)
    assert len(set(prefixes)) == 1
    for value in _SHARED_VARS.values():
        assert str(value) in prefixes[0]


def test_per_call_variables_are_after_the_break() -> None:
    rendered = render_prompt(
        PROMPTS / "20_section.md",
        {**_SHARED_VARS, **_STEP_VARS["20_section.md"], "outline_beat": "BEAT-XYZ"},
    )
    prefix, rest = split_cache_prefix(rendered)
    assert "BEAT-XYZ" not in prefix and "BEAT-XYZ" in rest


def test_split_cache_prefix() -> None:
    assert split_cache_prefix("plain") == (None, "plain")
    prefix, rest = split_cache_prefix(f"A\n{CACHE_BREAK_MARKER}\nB")
    assert (prefix, rest) == ("A\n", "\nB")
    _, rest = split_cache_prefix(f"A{CACHE_BREAK_MARKER}B{CACHE_BREAK_MARKER}C")
    assert rest == "BC"


def test_claude_user_content_marks_prefix_for_caching() -> None:
    content = providers_mod._claude_user_content(f"CTX{CACHE_BREAK_MARKER}ASK")
    assert content == [
        {"type": "text", "text": "CTX", "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": "ASK"},
    ]
    assert providers_mod._claude_user_content("no marker") == "no marker"
    assert providers_mod._claude_user_content(f"{CACHE_BREAK_MARKER}ASK") == "ASK"


# --- SDK wrappers with fake clients ------------------------------------------


class _FakeStream:
    def __init__(self, message: Any) -> None:
        self._message = message

    def __enter__(self) -> "_FakeStream":
        return self

    def __exit__(self, *_: Any) -> None:
        return None

    def get_final_message(self) -> Any:
        return self._message


class _FakeAnthropic:
    last_kwargs: dict[str, Any] = {}

    def __init__(self, api_key: str) -> None:
        self.messages = SimpleNamespace(stream=self._stream)

    def _stream(self, **kwargs: Any) -> _FakeStream:
        _FakeAnthropic.last_kwargs = kwargs
        return _FakeStream(
            SimpleNamespace(
                content=[
                    SimpleNamespace(type="thinking", thinking=""),
                    SimpleNamespace(type="text", text="Hello"),
                ],
                stop_reason="end_turn",
                usage=SimpleNamespace(
                    input_tokens=100,
                    output_tokens=20,
                    cache_creation_input_tokens=0,
                    cache_read_input_tokens=5000,
                ),
            )
        )


def _write_creds(tmp_path: Path) -> Path:
    (tmp_path / "creds.json").write_text(
        json.dumps({"ANTHROPIC_API_KEY": "k", "OPENAI_KEY": "k"}), encoding="utf-8"
    )
    return tmp_path


def test_claude_wrapper_streams_and_reports_cache_usage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import anthropic

    monkeypatch.setattr(anthropic, "Anthropic", _FakeAnthropic)
    provider = providers_mod.create_llm_provider(
        _write_creds(tmp_path), llm_provider="claude", default_model="claude-x"
    )
    assert isinstance(provider, ClaudeProvider)
    result = provider.generate(f"CTX{CACHE_BREAK_MARKER}ASK", step="s", timeout=600)

    sent = _FakeAnthropic.last_kwargs
    assert sent["max_tokens"] == 64000
    assert sent["timeout"] == 600
    assert sent["messages"][0]["content"][0]["cache_control"] == {"type": "ephemeral"}
    assert result.content == "Hello"
    assert result.prompt_tokens == 5100  # uncached + cached input
    assert result.cache_read_tokens == 5000
    assert result.cache_write_tokens == 0


class _FakeOpenAI:
    last_kwargs: dict[str, Any] = {}

    def __init__(self, api_key: str) -> None:
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs: Any) -> Any:
        _FakeOpenAI.last_kwargs = kwargs
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="Hi"), finish_reason="stop"
                )
            ],
            usage=SimpleNamespace(
                prompt_tokens=3000,
                completion_tokens=10,
                total_tokens=3010,
                prompt_tokens_details=SimpleNamespace(cached_tokens=2048),
            ),
        )


def test_openai_wrapper_strips_marker_and_sets_cache_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import openai

    monkeypatch.setattr(openai, "OpenAI", _FakeOpenAI)
    provider = providers_mod.create_llm_provider(
        _write_creds(tmp_path), llm_provider="openai", default_model="gpt-5.2"
    )
    assert isinstance(provider, OpenAIProvider)
    result = provider.generate(f"CTX\n{CACHE_BREAK_MARKER}\nASK", step="s")

    sent = _FakeOpenAI.last_kwargs
    assert sent["messages"][0]["content"] == "CTX\n\nASK"
    key_a = sent["prompt_cache_key"]
    assert key_a.startswith("llm_storytell-")
    provider.generate(f"CTX\n{CACHE_BREAK_MARKER}\nOTHER", step="s")
    assert _FakeOpenAI.last_kwargs["prompt_cache_key"] == key_a
    assert result.cache_read_tokens == 2048
    assert result.prompt_tokens == 3000


# --- accounting ----------------------------------------------------------------


def test_record_token_usage_includes_cache_fields_only_when_used(
    tmp_path: Path,
) -> None:
    logger = RunLogger(tmp_path / "run.log")
    plain = record_token_usage(logger, "a", "openai", "gpt-5.2", 10, 5)
    assert "cache_read_tokens" not in plain
    cached = record_token_usage(
        logger, "b", "claude", "claude-sonnet-4-6", 10, 5, cache_read_tokens=8
    )
    assert cached["cache_read_tokens"] == 8
    assert "cache_read_tokens=8" in (tmp_path / "run.log").read_text()


def test_cost_estimate_prices_cached_tokens() -> None:
    usage = [
        {
            "model": "claude-sonnet-4-6",
            "prompt_tokens": 1_000_000,
            "completion_tokens": 0,
            "cache_read_tokens": 500_000,
            "cache_write_tokens": 100_000,
        }
    ]
    # 400k uncached * $3 + 500k * $0.30 + 100k * $3.75 = 1.20 + 0.15 + 0.375
    assert estimate_run_cost(usage)[4] == pytest.approx(1.725)
    assert sum_cache_tokens(usage) == (500_000, 100_000)

    openai_usage = [
        {
            "model": "gpt-5.2",
            "prompt_tokens": 1_000_000,
            "completion_tokens": 0,
            "cache_read_tokens": 1_000_000,
        }
    ]
    assert estimate_run_cost(openai_usage)[4] == pytest.approx(0.175)
