# Section generation prompt

## Required inputs
- section_id (integer, required)
- section_index (integer, required)
- seed (string, required)
- outline_beat (string, required)
- lore_bible (string, required)
- style_rules (string, required)

## Optional inputs
- rolling_summary (string, optional)
- continuity_context (string, optional)
- location_context (string, optional)
- character_context (string, optional)

## Purpose
Write a single narrative section following the provided outline beat.
Maintain consistency with prior sections using rolling summary and continuity context.

## Instructions
- The lore bible is authoritative and must not be contradicted.
- Follow the outline_beat strictly.
- Do not introduce events outside the beat's scope.
- If rolling_summary or continuity_context is provided:
  - Maintain consistency with prior content.
- Do NOT include meta commentary.
- Do NOT explain your choices.

## Context
Seed:
{seed}

Lore bible:
{lore_bible}

Style rules:
{style_rules}

Outline beat:
{outline_beat}

Rolling summary (if any):
{rolling_summary}

Continuity ledger (if any):
{continuity_context}

Location context (if any):
{location_context}

Character context (if any):
{character_context}

## Output format
Output MUST be valid Markdown.
Output MUST begin with a YAML frontmatter block.

## YAML frontmatter schema
The frontmatter MUST include these exact fields (all required):

---
section_id: {section_id}
local_summary: "<A summary of this section's content, at least 100 characters long. Describe the key events, character actions, and narrative developments in this section.>"
new_entities: ["<entity1>", "<entity2>", ...]
new_locations: ["<location1>", "<location2>", ...]
unresolved_threads: ["<thread1>", "<thread2>", ...]
---

**Required fields:**
- `section_id`: Integer (use {section_id})
- `local_summary`: String, minimum 100 characters. Summarize this section's key events and developments.
- `new_entities`: Array of strings. List any new characters, objects, or concepts introduced in this section. Use empty array [] if none.
- `new_locations`: Array of strings. List any new locations introduced in this section. Use empty array [] if none.
- `unresolved_threads`: Array of strings. List any plot threads, questions, or conflicts introduced or left unresolved in this section. Use empty array [] if none.

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
