"""Continuity management for section generation.

Provides utilities for building rolling summaries and managing continuity
ledgers to maintain narrative consistency across sections.
"""

from typing import Any

# Configuration constants for token/word estimation
# Rough estimates: 1 token ≈ 0.75 words, 1 word ≈ 1.33 tokens
# These can be adjusted for different tokenization schemes
TOKENS_PER_WORD = 1.33
WORDS_PER_TOKEN = 0.75

# Rolling summary target range (in tokens)
ROLLING_SUMMARY_MIN_TOKENS = 400
ROLLING_SUMMARY_MAX_TOKENS = 900


class ContinuityError(Exception):
    """Raised when continuity operations fail."""

    pass


def _estimate_tokens(text: str) -> int:
    """Estimate token count from text.

    Uses a simple word-based estimation. For more accurate counts,
    a tokenizer could be used, but this keeps dependencies minimal.

    Args:
        text: Text to estimate tokens for.

    Returns:
        Estimated token count.
    """
    word_count = len(text.split())
    return int(word_count * TOKENS_PER_WORD)


def build_rolling_summary(
    summaries: list[dict[str, Any]], target_min_tokens: int = ROLLING_SUMMARY_MIN_TOKENS
) -> str:
    """Build a rolling summary from recent section summaries.

    Constructs a summary that includes the most recent sections,
    ensuring it meets the minimum token target. If summaries exceed
    the maximum, older ones are truncated.

    Args:
        summaries: List of summary dictionaries from state.summaries.
            Each should have 'section_id' and 'summary' keys.
        target_min_tokens: Minimum target tokens for the rolling summary.
            Defaults to ROLLING_SUMMARY_MIN_TOKENS.

    Returns:
        Formatted rolling summary string suitable for prompt inclusion.
    """
    if not summaries:
        return "No previous sections."

    # Start with most recent summaries and work backwards
    # until we meet the minimum token target
    selected_summaries: list[dict[str, Any]] = []
    total_tokens = 0

    for summary in reversed(summaries):
        summary_text = summary.get("summary", "")
        section_id = summary.get("section_id", 0)
        tokens = _estimate_tokens(summary_text)

        # If adding this would exceed max, stop
        if total_tokens + tokens > ROLLING_SUMMARY_MAX_TOKENS:
            break

        selected_summaries.insert(0, summary)
        total_tokens += tokens

        # If we've met the minimum, we can stop (but continue if we have room)
        if total_tokens >= target_min_tokens and len(selected_summaries) >= 2:
            # Prefer having at least 2-3 sections if possible
            break

    # Format the rolling summary
    parts: list[str] = []
    for summary in selected_summaries:
        section_id = summary.get("section_id", 0)
        summary_text = summary.get("summary", "")
        parts.append(f"Section {section_id:02d}: {summary_text}")

    return "\n\n".join(parts) if parts else "No previous sections."


def merge_continuity_updates(
    continuity_ledger: dict[str, str], updates: dict[str, str]
) -> dict[str, str]:
    """Merge new continuity updates into the continuity ledger.

    Updates are merged, with newer values taking precedence for
    the same keys. The ledger is a flat key-value mapping where
    keys represent continuity elements (e.g., character states,
    locations, plot threads) and values are their current state.

    Args:
        continuity_ledger: Current continuity ledger dictionary.
        updates: New continuity updates to merge.

    Returns:
        Updated continuity ledger dictionary (new dict, does not
        modify input).
    """
    merged = dict(continuity_ledger)
    merged.update(updates)
    return merged


def get_continuity_context(continuity_ledger: dict[str, str]) -> str:
    """Format continuity ledger for prompt inclusion.

    Converts the continuity ledger dictionary into a formatted
    string suitable for inclusion in prompts.

    Args:
        continuity_ledger: Continuity ledger dictionary.

    Returns:
        Formatted continuity context string.
    """
    if not continuity_ledger:
        return "No continuity information available."

    parts: list[str] = []
    for key, value in sorted(continuity_ledger.items()):
        parts.append(f"- {key}: {value}")

    return "\n".join(parts)
