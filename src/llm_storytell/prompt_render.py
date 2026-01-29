"""Prompt template rendering with strict variable validation.

This module provides deterministic prompt template rendering with no silent
fallbacks. All template variables must be explicitly provided.
"""

import re
from pathlib import Path


class PromptRenderError(Exception):
    """Base exception for prompt rendering errors."""

    pass


class MissingVariableError(PromptRenderError):
    """Raised when required template variables are missing.

    Attributes:
        template_path: Path to the template file.
        missing_variables: List of variable names that were not provided.
    """

    def __init__(self, template_path: Path, missing_variables: list[str]) -> None:
        """Initialize MissingVariableError.

        Args:
            template_path: Path to the template file.
            missing_variables: List of missing variable names.
        """
        self.template_path = template_path
        self.missing_variables = missing_variables
        missing_str = ", ".join(sorted(missing_variables))
        super().__init__(
            f"Template '{template_path}' requires variables that were not provided: "
            f"{missing_str}"
        )


class TemplateNotFoundError(PromptRenderError):
    """Raised when a template file cannot be found."""

    def __init__(self, template_path: Path) -> None:
        """Initialize TemplateNotFoundError.

        Args:
            template_path: Path to the template file that was not found.
        """
        self.template_path = template_path
        super().__init__(f"Template file not found: {template_path}")


# Strict identifier: only [a-zA-Z_][a-zA-Z0-9_]* so JSON examples don't create vars
_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _extract_placeholders(template: str) -> set[str]:
    """Extract placeholder names from a template string.

    Only recognises {identifier} placeholders: identifier must match
    [a-zA-Z_][a-zA-Z0-9_]*. Escaped braces {{ and }} are ignored.
    JSON examples (e.g. {"beats": [...]}) do not create required variables.

    Args:
        template: The template string to parse.

    Returns:
        Set of placeholder names (without format specifiers).
    """
    # Pattern matches {name} or {name:format_spec}; excludes {{ and }}
    pattern = r"(?<!\{)\{([^}:]+)(?::[^}]*)?\}(?!\})"
    matches = re.findall(pattern, template)

    placeholders = {
        name.strip() for name in matches if _IDENTIFIER_RE.match(name.strip())
    }
    return set(placeholders)


def render_prompt(
    template_path: Path, variables: dict[str, str | int | float | bool]
) -> str:
    """Render a prompt template with provided variables.

    This function reads a template file and substitutes variables using Python's
    str.format() method. All placeholders in the template must be provided in
    the variables dictionary. No silent fallbacks or default values are used.

    Args:
        template_path: Path to the template file (must exist and be readable).
        variables: Dictionary mapping variable names to their values. Values can
            be strings, numbers, or booleans.

    Returns:
        Rendered prompt string with all variables substituted.

    Raises:
        TemplateNotFoundError: If the template file does not exist or cannot
            be read.
        MissingVariableError: If the template contains placeholders that are
            not provided in the variables dictionary.
        PromptRenderError: For other rendering errors (e.g., encoding issues,
            format errors).
    """
    # Check if template file exists
    if not template_path.exists():
        raise TemplateNotFoundError(template_path)

    # Read template file
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

    # Extract required placeholders from template
    required_vars = _extract_placeholders(template_content)

    # Check for missing variables
    provided_vars = set(variables.keys())
    missing_vars = required_vars - provided_vars

    if missing_vars:
        raise MissingVariableError(template_path, list(missing_vars))

    # Render template
    try:
        rendered = template_content.format(**variables)
    except KeyError as e:
        # This should not happen if our validation is correct, but handle it
        # gracefully just in case
        raise MissingVariableError(template_path, [str(e).strip("'\"")]) from e
    except ValueError as e:
        raise PromptRenderError(
            f"Error formatting template '{template_path}': {e}"
        ) from e

    return rendered
