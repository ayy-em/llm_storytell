"""ISO 639-1 language code validation.

Validates two-letter ISO 639-1 codes. Invalid codes raise ValueError
with a verbose message so the pipeline fails fast.
"""

# Official ISO 639-1 two-letter codes (subset of ISO 639).
# Source: ISO 639-1 / Library of Congress.
_VALID_ISO639_1: frozenset[str] = frozenset(
    {
        "aa",
        "ab",
        "ae",
        "af",
        "ak",
        "am",
        "an",
        "ar",
        "as",
        "av",
        "ay",
        "az",
        "ba",
        "be",
        "bg",
        "bh",
        "bi",
        "bm",
        "bn",
        "bo",
        "br",
        "bs",
        "ca",
        "ce",
        "ch",
        "co",
        "cr",
        "cs",
        "cu",
        "cv",
        "cy",
        "da",
        "de",
        "dv",
        "dz",
        "ee",
        "el",
        "en",
        "eo",
        "es",
        "et",
        "eu",
        "fa",
        "ff",
        "fi",
        "fj",
        "fo",
        "fr",
        "fy",
        "ga",
        "gd",
        "gl",
        "gn",
        "gu",
        "gv",
        "ha",
        "he",
        "hi",
        "ho",
        "hr",
        "ht",
        "hu",
        "hy",
        "hz",
        "ia",
        "id",
        "ie",
        "ig",
        "ii",
        "ik",
        "io",
        "is",
        "it",
        "iu",
        "ja",
        "jv",
        "ka",
        "kg",
        "ki",
        "kj",
        "kk",
        "kl",
        "km",
        "kn",
        "ko",
        "kr",
        "ks",
        "ku",
        "kv",
        "kw",
        "ky",
        "la",
        "lb",
        "lg",
        "li",
        "ln",
        "lo",
        "lt",
        "lu",
        "lv",
        "mg",
        "mh",
        "mi",
        "mk",
        "ml",
        "mn",
        "mr",
        "ms",
        "mt",
        "my",
        "na",
        "nb",
        "nd",
        "ne",
        "ng",
        "nl",
        "nn",
        "no",
        "nr",
        "nv",
        "ny",
        "oc",
        "oj",
        "om",
        "or",
        "os",
        "pa",
        "pi",
        "pl",
        "ps",
        "pt",
        "qu",
        "rm",
        "rn",
        "ro",
        "ru",
        "rw",
        "sa",
        "sc",
        "sd",
        "se",
        "sg",
        "si",
        "sk",
        "sl",
        "sm",
        "sn",
        "so",
        "sq",
        "sr",
        "ss",
        "st",
        "su",
        "sv",
        "sw",
        "ta",
        "te",
        "tg",
        "th",
        "ti",
        "tk",
        "tl",
        "tn",
        "to",
        "tr",
        "ts",
        "tt",
        "tw",
        "ty",
        "ug",
        "uk",
        "ur",
        "uz",
        "ve",
        "vi",
        "vo",
        "wa",
        "wo",
        "xh",
        "yi",
        "yo",
        "za",
        "zh",
        "zu",
    }
)


class InvalidLanguageError(Exception):
    """Raised when a language code is not a valid ISO 639-1 code."""

    pass


def validate_iso639(code: str) -> str:
    """Validate and normalize an ISO 639-1 language code.

    Args:
        code: A candidate language code (e.g. from config or CLI).

    Returns:
        The same code normalized to lowercase (two letters).

    Raises:
        InvalidLanguageError: If code is not a valid ISO 639-1 two-letter code.
            The message includes the invalid value and states that a valid
            ISO 639-1 code is required.
    """
    if not isinstance(code, str):
        raise InvalidLanguageError(
            f"Language must be a string, got {type(code).__name__}. "
            "Use a valid ISO 639-1 two-letter code (e.g. en, es, fr)."
        )
    normalized = code.strip().lower()
    if len(normalized) != 2 or not normalized.isalpha():
        raise InvalidLanguageError(
            f"Invalid language code '{code}': must be exactly two letters. "
            "Use a valid ISO 639-1 code (e.g. en, es, fr)."
        )
    if normalized not in _VALID_ISO639_1:
        raise InvalidLanguageError(
            f"Invalid language code '{code}': '{normalized}' is not a valid "
            "ISO 639-1 code. Use a valid two-letter code (e.g. en, es, fr, de)."
        )
    return normalized
