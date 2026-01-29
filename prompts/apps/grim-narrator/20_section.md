# Section generation prompt

## Required inputs
- section_index (integer, required)
- seed (string, required)
- lore_bible (string, required)

## Optional inputs
- outline_beat (object, optional)
- rolling_summary (string, optional)
- continuity_context (string, optional)
- world_history (string, optional)
- world_states (string, optional)
- style_narration (string, optional)
- style_tone (string, optional)
- location_context (string, optional)
- character_context (string, optional)

## Purpose
Write a single narrative section.
If an outline beat is provided, follow it.
If not, advance the narrative naturally from the seed while respecting the lore bible.

## Instructions
- The lore bible is authoritative and must not be contradicted.
- If outline_beat is provided:
  - Follow it strictly.
  - Do not introduce events outside its scope.
- If outline_beat is not provided:
  - Advance the narrative conservatively.
  - Do not introduce major new plot elements.
- If rolling_summary or continuity_context is provided:
  - Maintain consistency with prior content.
- Do NOT include meta commentary.
- Do NOT explain your choices.

## Context
Seed:
{seed}

Lore bible:
{lore_bible}

Outline beat:
{outline_beat}

Rolling summary (if any):
{rolling_summary}

Continuity ledger (if any):
{continuity_context}

World history (if any):
{world_history}

World states (if any):
{world_states}

Narration style (if any):
{style_narration}

Tone rules (if any):
{style_tone}

Location context (if any):
{location_context}

Character context (if any):
{character_context}

## Output format
Output MUST be valid Markdown.
Output MUST begin with a YAML frontmatter block.

## YAML frontmatter schema
---
section_id: "section_{section_index:02d}"
index: {section_index}
outline_id: "<outline_beat.id or null>"
---

## Prose requirements
- Write only the prose for this section.
- No headings outside the frontmatter.
- No summaries.
- No lists.
- Dialogue only if justified by context.

## Length targets
- Prose length: 400–800 words

## Validation rules
- Frontmatter must be present and valid YAML.
- Frontmatter keys must match the schema exactly.
- Use null if outline_beat is not provided.
- Do not add additional frontmatter fields.
