"""Helpers for normalizing raw LLM responses before parsing.

Models sometimes wrap structured output in Markdown code fences
(```json ... ``` / ```yaml ... ```) even when told not to. These helpers
remove such wrappers so parsers see the payload itself.
"""

import re

_OPENING_FENCE = re.compile(r"^```[^\n]*\n")
_CLOSING_FENCE = re.compile(r"\n?```\s*$")


def strip_code_fence(text: str) -> str:
    """Remove a single Markdown code fence wrapping the whole *text*.

    Text without a leading fence is returned stripped but otherwise unchanged.
    """
    t = text.lstrip("﻿").strip()
    if not t.startswith("```"):
        return t
    t = _OPENING_FENCE.sub("", t, count=1)
    t = _CLOSING_FENCE.sub("", t, count=1)
    return t.strip()


def normalize_frontmatter_document(text: str) -> str:
    """Unwrap a frontmatter Markdown document from stray code fences.

    Handles both a fence around the whole document and a fence around only
    the YAML frontmatter (```yaml\\n---\\n...\\n---\\n```\\n\\nbody).
    """
    t = text.lstrip("﻿").strip()
    if not t.startswith("```"):
        return t
    t = _OPENING_FENCE.sub("", t, count=1)
    match = re.match(r"^(---\s*\n.*?\n---[ \t]*\n)(.*)$", t, re.DOTALL)
    if not match:
        return _CLOSING_FENCE.sub("", t, count=1).strip()
    frontmatter, body = match.group(1), match.group(2)
    # Fence closed right after the frontmatter, or at the very end.
    body = re.sub(r"^\s*```[ \t]*\n", "", body, count=1)
    body = _CLOSING_FENCE.sub("", body, count=1)
    return frontmatter + body.strip() + "\n"
