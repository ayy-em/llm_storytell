"""Token usage tracking for LLM calls.

Provides utilities to record and persist token usage information
for each LLM call made during pipeline execution.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..logging import RunLogger


@dataclass
class TokenUsage:
    """Token usage information for a single LLM call.

    Attributes:
        step: Name of the pipeline step that made the call.
        provider: LLM provider name (e.g., "openai").
        model: Model name (e.g., "gpt-4").
        prompt_tokens: Number of prompt tokens used.
        completion_tokens: Number of completion tokens used.
        total_tokens: Total tokens used.
    """

    step: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

    def to_dict(self) -> dict[str, Any]:
        """Convert token usage to dictionary for JSON serialization.

        Returns:
            Dictionary representation suitable for state.json.
        """
        return {
            "step": self.step,
            "provider": self.provider,
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


def _calculate_cumulative_tokens(
    state_path: Path, current_prompt: int, current_completion: int, current_total: int
) -> tuple[int, int, int]:
    """Calculate cumulative token totals from state.json and current call.

    Args:
        state_path: Path to state.json file.
        current_prompt: Prompt tokens from current call.
        current_completion: Completion tokens from current call.
        current_total: Total tokens from current call.

    Returns:
        Tuple of (cumulative_prompt, cumulative_completion, cumulative_total).
    """
    cumulative_prompt = current_prompt
    cumulative_completion = current_completion
    cumulative_total = current_total

    # Try to read existing token usage from state.json
    if state_path.exists():
        try:
            with state_path.open(encoding="utf-8") as f:
                state = json.load(f)
                token_usage = state.get("token_usage", [])
                if isinstance(token_usage, list):
                    for entry in token_usage:
                        if isinstance(entry, dict):
                            cumulative_prompt += entry.get("prompt_tokens", 0)
                            cumulative_completion += entry.get("completion_tokens", 0)
                            cumulative_total += entry.get("total_tokens", 0)
        except (OSError, json.JSONDecodeError, KeyError):
            # If we can't read state.json, just use current call's tokens
            pass

    return cumulative_prompt, cumulative_completion, cumulative_total


def _append_cumulative_log(log_path: Path, cumulative_prompt: int, cumulative_completion: int, cumulative_total: int) -> None:
    """Append cumulative token totals to the log file.

    Args:
        log_path: Path to run.log file.
        cumulative_prompt: Cumulative prompt tokens.
        cumulative_completion: Cumulative completion tokens.
        cumulative_total: Cumulative total tokens.
    """
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    message = (
        f"Cumulative token usage: prompt_tokens={cumulative_prompt}, "
        f"completion_tokens={cumulative_completion}, total_tokens={cumulative_total}"
    )
    entry = f"[{timestamp}] [INFO] {message}\n"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(entry)


def record_token_usage(
    logger: RunLogger,
    step: str,
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int | None = None,
) -> dict[str, Any]:
    """Record token usage for an LLM call.

    Logs the token usage to run.log (single line with prompt/completion/total tokens)
    and appends a cumulative total line. Returns a dictionary that can be appended
    to state.json's token_usage array.

    Args:
        logger: RunLogger instance for the current run.
        step: Name of the pipeline step that made the call.
        provider: LLM provider name (e.g., "openai").
        model: Model name (e.g., "gpt-4").
        prompt_tokens: Number of prompt tokens used.
        completion_tokens: Number of completion tokens used.
        total_tokens: Total tokens used. If None, calculated as
            prompt_tokens + completion_tokens.

    Returns:
        Dictionary representation of token usage for state.json.
    """
    if total_tokens is None:
        total_tokens = prompt_tokens + completion_tokens

    # Log single line with token counts (simplified format: just the three values)
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    message = (
        f"Token usage: prompt_tokens={prompt_tokens}, "
        f"completion_tokens={completion_tokens}, total_tokens={total_tokens}"
    )
    entry = f"[{timestamp}] [INFO] {message}\n"
    with logger.log_path.open("a", encoding="utf-8") as f:
        f.write(entry)

    # Calculate cumulative totals from state.json
    state_path = logger.log_path.parent / "state.json"
    cumulative_prompt, cumulative_completion, cumulative_total = _calculate_cumulative_tokens(
        state_path, prompt_tokens, completion_tokens, total_tokens
    )

    # Append cumulative line immediately after
    _append_cumulative_log(logger.log_path, cumulative_prompt, cumulative_completion, cumulative_total)

    # Return dict for state.json
    usage = TokenUsage(
        step=step,
        provider=provider,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )

    return usage.to_dict()
