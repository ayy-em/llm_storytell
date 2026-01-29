"""Token usage tracking for LLM calls.

Provides utilities to record and persist token usage information
for each LLM call made during pipeline execution.
"""

from dataclasses import dataclass
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

    Logs the token usage to run.log and returns a dictionary
    that can be appended to state.json's token_usage array.

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

    # Log to run.log
    logger.log_token_usage(
        step=step,
        provider=provider,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )

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
