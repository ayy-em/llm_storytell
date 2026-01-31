"""Tests for CLI word-count flag and derivation helpers."""

from llm_storytell.cli import _section_length_midpoint


class TestSectionLengthMidpoint:
    """Tests for _section_length_midpoint."""

    def test_parses_range_midpoint(self) -> None:
        """Range '400-600' returns midpoint 500."""
        assert _section_length_midpoint("400-600") == 500

    def test_parses_single_number(self) -> None:
        """Single number '500' returns 500."""
        assert _section_length_midpoint("500") == 500

    def test_parses_small_range(self) -> None:
        """Range '100-200' returns 150."""
        assert _section_length_midpoint("100-200") == 150

    def test_invalid_fallback_500(self) -> None:
        """Invalid or unparseable string falls back to 500."""
        assert _section_length_midpoint("invalid") == 500
        assert _section_length_midpoint("") == 500
