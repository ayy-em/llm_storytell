"""Prompt template rendering with strict variable validation.

Uses Python's built-in format-string parser (string.Formatter) instead of regex,
so escaped braces {{ }} work correctly and JSON examples don't accidentally
create "required variables".

Contract:
- Only plain identifier placeholders are allowed: {seed}, {beats_count}, etc.
- Identifiers must match: [A-Za-z_][A-Za-z0-9_]*
- Any other placeholder form (attribute/index access, whitespace, quotes, etc.)
  is rejected with a clear error.
- Missing variables are reported as a sorted list (deterministic).
"""

from __future__ import annotations

import re
from pathlib import Path
from string import Formatter


class PromptRenderError(Exception):
    """Base exception for prompt rendering errors."""


class MissingVariableError(PromptRenderError):
    """Raised when required template variables are missing."""

    def __init__(self, template_path: Path, missing_variables: list[str]) -> None:
        self.template_path = template_path
        self.missing_variables = missing_variables
        missing_str = ", ".join(missing_variables)
        super().__init__(
            f"Template '{template_path}' requires variables that were not provided: "
            f"{missing_str}"
        )


class TemplateNotFoundError(PromptRenderError):
    """Raised when a template file cannot be found."""

    def __init__(self, template_path: Path) -> None:
        self.template_path = template_path
        super().__init__(f"Template file not found: {template_path}")


class UnsupportedPlaceholderError(PromptRenderError):
    """Raised when a template contains a placeholder that violates the contract."""

    def __init__(self, template_path: Path, placeholder: str) -> None:
        self.template_path = template_path
        self.placeholder = placeholder
        super().__init__(
            f"Template '{template_path}' contains unsupported placeholder: "
            f"{{{placeholder}}}. Only simple identifiers like {{seed}} are allowed. "
            f"If you meant literal braces, escape them as '{{{{' and '}}}}'."
        )


_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _extract_required_identifiers(template_path: Path, template: str) -> set[str]:
    """Extract required placeholder names from a format template.

    Uses Python's format parser. Escaped braces {{ }} are handled correctly.

    Raises:
        UnsupportedPlaceholderError: if a placeholder is not a plain identifier.
        PromptRenderError: on invalid format strings.
    """
    required: set[str] = set()
    fmt = Formatter()

    try:
        for _, field_name, _, _ in fmt.parse(template):
            if field_name is None or field_name == "":
                continue

            # Disallow any "fancy" field like foo.bar, foo[0], !r, etc.
            # (Formatter.parse() returns the raw field_name; conversion/format_spec
            # are separate, but we also disallow nested fields by contract.)
            if not _IDENTIFIER_RE.fullmatch(field_name):
                raise UnsupportedPlaceholderError(template_path, field_name)

            required.add(field_name)
    except ValueError as e:
        # Raised by Formatter.parse for malformed format strings.
        raise PromptRenderError(
            f"Invalid format string in template '{template_path}': {e}. "
            "If you intended literal braces, escape them as '{{' and '}}'."
        ) from e

    return required


def render_prompt(
    template_path: Path,
    variables: dict[str, str | int | float | bool],
) -> str:
    """Render a prompt template with strict validation.

    - Validates template exists and is UTF-8.
    - Validates placeholders are only simple identifiers.
    - Validates all required identifiers are provided.
    - Renders via str.format(**variables).
    """
    if not template_path.exists():
        raise TemplateNotFoundError(template_path)

    try:
        template_content = template_path.read_text(encoding="utf-8")
    except OSError as e:
        raise PromptRenderError(
            f"Error reading template file '{template_path}': {e}"
        ) from e
    except UnicodeDecodeError as e:
        raise PromptRenderError(
            f"Template file '{template_path}' is not valid UTF-8: {e}"
        ) from e

    required_vars = _extract_required_identifiers(template_path, template_content)
    provided_vars = set(variables.keys())
    missing = sorted(required_vars - provided_vars)

    if missing:
        raise MissingVariableError(template_path, missing)

    try:
        return template_content.format(**variables)
    except KeyError as e:
        # Shouldn't happen due to pre-check, but keep it clean.
        key = e.args[0] if e.args else str(e).strip("'\"")
        raise MissingVariableError(template_path, [str(key)]) from e
    except (ValueError, IndexError) as e:
        # ValueError: bad format spec; IndexError: positional fields (disallowed)
        raise PromptRenderError(
            f"Error formatting template '{template_path}': {e}. "
            "If you intended literal braces, escape them as '{{' and '}}'."
        ) from e
