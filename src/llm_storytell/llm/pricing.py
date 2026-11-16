"""Approximate cost estimation for LLM runs using Standard-tier pricing.

Prices are per 1M tokens (input, output). Used only for CLI summary;
not authoritative. Update from provider pricing when needed.
"""

import re

# Standard tier, USD per 1M tokens (input, output).
# Sources: OpenAI platform pricing (Standard tier); Anthropic model pricing
# (first-party API, prompts without caching). Last reviewed 2026-11.
MODEL_COST_PER_1M: dict[str, tuple[float, float]] = {
    # Anthropic Claude
    "claude-opus-5-5": (4.00, 20.00),
    "claude-opus-5": (5.00, 25.00),
    "claude-opus-4-8": (5.00, 25.00),
    "claude-opus-4-7": (5.00, 25.00),
    "claude-opus-4-6": (5.00, 25.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-haiku-4-5": (1.00, 5.00),
    # GPT-5 family
    "gpt-5.5": (5.00, 30.00),
    "gpt-5.4": (2.50, 15.00),
    "gpt-5.2": (1.75, 14.00),
    "gpt-5.1": (1.25, 10.00),
    "gpt-5": (1.25, 10.00),
    "gpt-5-mini": (0.25, 2.00),
    "gpt-5-nano": (0.05, 0.40),
    "gpt-5.2-chat-latest": (1.75, 14.00),
    "gpt-5.1-chat-latest": (1.25, 10.00),
    "gpt-5-chat-latest": (1.25, 10.00),
    "gpt-5.2-codex": (1.75, 14.00),
    "gpt-5.1-codex-max": (1.25, 10.00),
    "gpt-5.1-codex": (1.25, 10.00),
    "gpt-5-codex": (1.25, 10.00),
    "gpt-5.2-pro": (21.00, 168.00),
    "gpt-5-pro": (15.00, 120.00),
    # GPT-4.1 / 4o
    "gpt-4.1": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-2024-05-13": (5.00, 15.00),
}

# TTS: USD per 1M characters (input).
# OpenAI: platform pricing. ElevenLabs: converted from USD per 1k chars (×1000).
TTS_COST_PER_1M_CHARS: dict[str, float] = {
    # OpenAI
    "tts-1": 15.00,
    "tts-1-hd": 30.00,
    "gpt-4o-mini-tts": 15.50,
    # ElevenLabs ($ per 1k chars → $ per 1M chars)
    "eleven_flash_v2_5": 80.00,  # $0.08 per 1k
    "eleven_multilingual_v2": 170.00,  # $0.17 per 1k
}


# Dated snapshot suffixes, e.g. gpt-5-mini-2025-08-07 or claude-haiku-4-5-20251001.
_SNAPSHOT_SUFFIX = re.compile(r"-(\d{4}-\d{2}-\d{2}|\d{8})$")


def _lookup_model_rates(model: str) -> tuple[float, float] | None:
    """Return (input, output) USD per 1M tokens; falls back to the undated alias."""
    if model in MODEL_COST_PER_1M:
        return MODEL_COST_PER_1M[model]
    return MODEL_COST_PER_1M.get(_SNAPSHOT_SUFFIX.sub("", model))


def estimate_run_cost(
    token_usage: list[dict],
) -> tuple[str | None, int, int, int, float | None]:
    """Aggregate token usage and estimate cost for a run.

    Args:
        token_usage: List of entries from state.json token_usage (each
            with prompt_tokens, completion_tokens, total_tokens, model).

    Returns:
        (model, prompt_total, completion_total, total_tokens, cost_usd).
        model is from the first entry, or None if list is empty.
        cost_usd is None if the model is not in MODEL_COST_PER_1M.
    """
    prompt_total = 0
    completion_total = 0
    total_tokens = 0
    model: str | None = None

    for entry in token_usage:
        if not isinstance(entry, dict):
            continue
        prompt_total += entry.get("prompt_tokens", 0) or 0
        completion_total += entry.get("completion_tokens", 0) or 0
        total_total = entry.get("total_tokens")
        if isinstance(total_total, int):
            total_tokens += total_total
        else:
            total_tokens += (entry.get("prompt_tokens", 0) or 0) + (
                entry.get("completion_tokens", 0) or 0
            )
        if model is None and entry.get("model"):
            model = str(entry["model"]).strip() or None

    cost_usd: float | None = None
    rates = _lookup_model_rates(model) if model else None
    if rates is not None:
        inp, out = rates
        cost_usd = (prompt_total * inp + completion_total * out) / 1_000_000.0
        cost_usd = round(cost_usd, 4)

    return (model, prompt_total, completion_total, total_tokens, cost_usd)


def estimate_tts_cost(
    tts_usage: list[dict],
) -> tuple[int, float | None]:
    """Aggregate TTS character usage and estimate cost for a run.

    Args:
        tts_usage: List of entries from state.json tts_token_usage (each
            may have input_characters, model).

    Returns:
        (total_input_characters, cost_usd).
        cost_usd is None if the model (from first entry) is not in
        TTS_COST_PER_1M_CHARS.
    """
    total_chars = 0
    model: str | None = None

    for entry in tts_usage:
        if not isinstance(entry, dict):
            continue
        total_chars += entry.get("input_characters", 0) or 0
        if model is None and entry.get("model"):
            model = str(entry["model"]).strip() or None

    cost_usd: float | None = None
    if model and model in TTS_COST_PER_1M_CHARS:
        rate = TTS_COST_PER_1M_CHARS[model]
        cost_usd = (total_chars * rate) / 1_000_000.0
        cost_usd = round(cost_usd, 4)

    return (total_chars, cost_usd)
