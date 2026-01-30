"""Approximate cost estimation for LLM runs using Standard-tier pricing.

Prices are per 1M tokens (input, output). Used only for CLI summary;
not authoritative. Update from provider pricing when needed.
"""

# Standard tier, USD per 1M tokens (input, output).
# Source: OpenAI platform pricing (Standard tier).
MODEL_COST_PER_1M: dict[str, tuple[float, float]] = {
    # GPT-5 family
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
    if model and model in MODEL_COST_PER_1M:
        inp, out = MODEL_COST_PER_1M[model]
        cost_usd = (prompt_total * inp + completion_total * out) / 1_000_000.0
        cost_usd = round(cost_usd, 4)

    return (model, prompt_total, completion_total, total_tokens, cost_usd)
