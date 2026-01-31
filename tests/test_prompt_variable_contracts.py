"""Tests for prompt variable contract validation.

Ensures prompt templates only reference variables that are provided by their
corresponding pipeline steps.
"""

import sys
from pathlib import Path

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from llm_storytell.prompt_render import _extract_required_identifiers


# Define allowed variables per step (from SPEC.md prompt variable contracts)
OUTLINE_REQUIRED = {
    "seed",
    "beats_count",
    "lore_bible",
    "style_rules",
    "location_context",
    "character_context",
}
OUTLINE_OPTIONAL: set[str] = set()
OUTLINE_ALLOWED = OUTLINE_REQUIRED | OUTLINE_OPTIONAL

SECTION_REQUIRED = {
    "section_id",
    "section_index",
    "seed",
    "outline_beat",
    "lore_bible",
    "style_rules",
    "section_length",
}
SECTION_OPTIONAL = {
    "rolling_summary",
    "continuity_context",
    "location_context",
    "character_context",
}
SECTION_ALLOWED = SECTION_REQUIRED | SECTION_OPTIONAL

SUMMARIZE_REQUIRED = {
    "section_id",
    "section_content",
}
SUMMARIZE_OPTIONAL: set[str] = set()
SUMMARIZE_ALLOWED = SUMMARIZE_REQUIRED | SUMMARIZE_OPTIONAL

CRITIC_REQUIRED = {
    "seed",
    "lore_bible",
    "style_rules",
    "full_draft",
    "outline",
}
CRITIC_OPTIONAL = {
    "location_context",
    "character_context",
}
CRITIC_ALLOWED = CRITIC_REQUIRED | CRITIC_OPTIONAL


def _get_prompt_path(prompt_name: str) -> Path:
    """Get path to a prompt template file (app-defaults)."""
    project_root = Path(__file__).parent.parent
    return project_root / "prompts" / "app-defaults" / prompt_name


def _extract_variables_from_prompt(prompt_path: Path) -> set[str]:
    """Extract required identifier placeholders from a prompt template.

    Uses prompt_render's _extract_required_identifiers (identifier-only contract).
    """
    if not prompt_path.exists():
        pytest.skip(f"Prompt template not found: {prompt_path}")
    content = prompt_path.read_text(encoding="utf-8")
    return _extract_required_identifiers(prompt_path, content)


class TestPromptVariableContracts:
    """Test that prompt templates only reference allowed variables."""

    def test_outline_prompt_variables(self) -> None:
        """Test that 10_outline.md only references allowed variables."""
        prompt_path = _get_prompt_path("10_outline.md")
        referenced_vars = _extract_variables_from_prompt(prompt_path)

        # All referenced variables must be in allowed set
        unknown_vars = referenced_vars - OUTLINE_ALLOWED
        assert not unknown_vars, (
            f"10_outline.md references unknown variables: {unknown_vars}. "
            f"Allowed: {OUTLINE_ALLOWED}"
        )

    def test_section_prompt_variables(self) -> None:
        """Test that 20_section.md only references allowed variables."""
        prompt_path = _get_prompt_path("20_section.md")
        referenced_vars = _extract_variables_from_prompt(prompt_path)

        # All referenced variables must be in allowed set
        unknown_vars = referenced_vars - SECTION_ALLOWED
        assert not unknown_vars, (
            f"20_section.md references unknown variables: {unknown_vars}. "
            f"Allowed: {SECTION_ALLOWED}"
        )

    def test_summarize_prompt_variables(self) -> None:
        """Test that 21_summarize.md only references allowed variables."""
        prompt_path = _get_prompt_path("21_summarize.md")
        referenced_vars = _extract_variables_from_prompt(prompt_path)

        # All referenced variables must be in allowed set
        unknown_vars = referenced_vars - SUMMARIZE_ALLOWED
        assert not unknown_vars, (
            f"21_summarize.md references unknown variables: {unknown_vars}. "
            f"Allowed: {SUMMARIZE_ALLOWED}"
        )

    def test_critic_prompt_variables(self) -> None:
        """Test that 30_critic.md only references allowed variables."""
        prompt_path = _get_prompt_path("30_critic.md")
        referenced_vars = _extract_variables_from_prompt(prompt_path)

        # All referenced variables must be in allowed set
        unknown_vars = referenced_vars - CRITIC_ALLOWED
        assert not unknown_vars, (
            f"30_critic.md references unknown variables: {unknown_vars}. "
            f"Allowed: {CRITIC_ALLOWED}"
        )
