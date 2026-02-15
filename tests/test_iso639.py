"""Tests for ISO 639-1 language code validation."""

import pytest

from llm_storytell.iso639 import InvalidLanguageError, validate_iso639


class TestValidateIso639:
    """Tests for validate_iso639."""

    def test_valid_code_returns_normalized_lowercase(self) -> None:
        """Valid two-letter codes return normalized lowercase."""
        assert validate_iso639("en") == "en"
        assert validate_iso639("EN") == "en"
        assert validate_iso639("En") == "en"
        assert validate_iso639("es") == "es"
        assert validate_iso639("fr") == "fr"
        assert validate_iso639("  de  ") == "de"
        assert validate_iso639("zh") == "zh"
        assert validate_iso639("ja") == "ja"

    def test_invalid_code_not_in_list_raises(self) -> None:
        """Invalid code (not in ISO 639-1 set) raises InvalidLanguageError with message."""
        with pytest.raises(InvalidLanguageError) as exc_info:
            validate_iso639("xx")
        msg = str(exc_info.value)
        assert "xx" in msg or "invalid" in msg.lower()
        assert "ISO 639" in msg

    def test_non_two_letter_raises(self) -> None:
        """Non-two-letter string raises with clear message."""
        with pytest.raises(InvalidLanguageError) as exc_info:
            validate_iso639("eng")
        msg = str(exc_info.value)
        assert "two letters" in msg or "exactly" in msg.lower()
        assert "ISO 639" in msg

    def test_empty_raises(self) -> None:
        """Empty or single letter raises."""
        with pytest.raises(InvalidLanguageError):
            validate_iso639("")
        with pytest.raises(InvalidLanguageError):
            validate_iso639("e")

    def test_non_alpha_raises(self) -> None:
        """Non-alpha characters raise."""
        with pytest.raises(InvalidLanguageError):
            validate_iso639("e1")
        with pytest.raises(InvalidLanguageError):
            validate_iso639("12")

    def test_non_string_raises(self) -> None:
        """Non-string input raises with type in message."""
        with pytest.raises(InvalidLanguageError) as exc_info:
            validate_iso639(123)  # type: ignore[arg-type]
        assert (
            "string" in str(exc_info.value).lower()
            or "int" in str(exc_info.value).lower()
        )
