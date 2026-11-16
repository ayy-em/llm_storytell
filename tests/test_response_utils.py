"""Tests for LLM response normalization helpers."""

import json

from llm_storytell.steps.response_utils import (
    normalize_frontmatter_document,
    strip_code_fence,
)
from llm_storytell.steps.section import _parse_markdown_with_frontmatter

FM = "---\nsection_id: 6\nlocal_summary: x\n---\n"


def test_strip_code_fence_json() -> None:
    assert json.loads(strip_code_fence('```json\n{"a": 1}\n```')) == {"a": 1}


def test_strip_code_fence_passthrough() -> None:
    assert strip_code_fence('  {"a": 1}\n') == '{"a": 1}'


def test_frontmatter_only_fenced() -> None:
    """Shape seen in a real failed run: fence closes right after the frontmatter."""
    raw = "```yaml\n" + FM + "```\n\nThe corridor narrowed.\n\nI kept walking."
    fm, body = _parse_markdown_with_frontmatter(raw)
    assert fm["section_id"] == 6
    assert body.startswith("The corridor narrowed.")
    assert "```" not in body


def test_whole_document_fenced() -> None:
    raw = "```markdown\n" + FM + "\nBody text.\n```"
    fm, body = _parse_markdown_with_frontmatter(raw)
    assert fm["local_summary"] == "x"
    assert body.strip() == "Body text."


def test_unfenced_document_unchanged() -> None:
    raw = FM + "\nBody with ``` inline fence.\n"
    assert normalize_frontmatter_document(raw) == raw.strip()


def test_bom_and_leading_whitespace() -> None:
    fm, _ = _parse_markdown_with_frontmatter("﻿\n\n" + FM + "\nBody")
    assert fm["section_id"] == 6
