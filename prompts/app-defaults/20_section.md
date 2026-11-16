# Story context
Seed:
{seed}

Language (ISO 639-1 code; the story is written in this language):
{language}

Lore bible:
{lore_bible}

Style rules:
{style_rules}

Location context:
{location_context}

Character context:
{character_context}

<!-- cache-break -->

# Section generation

## Inputs
Required:
- section_id
- seed
- outline_beat
- lore_bible
- style_rules

Optional:
- rolling_summary
- continuity_context
- location_context
- character_context
- section_length (target word range, e.g. "400-600")
- language (ISO 639-1 code; write this section in this language)

## Task
Write one narrative section that realizes the given outline beat.
Respect prior content if provided.
Write the section in the language indicated by `language` (ISO 639-1 code).

## Rules
- Lore bible is authoritative.
- Follow the outline beat strictly. Do not add extra events.
- Maintain continuity with prior sections when context is provided.
- No meta commentary. No explanations.

## Inputs for this section
Seed, lore bible, style rules, location and character context, and language are given in "Story context" above.

Outline beat:
{outline_beat}

Rolling summary:
{rolling_summary}

Continuity ledger:
{continuity_context}

## Output
- Valid Markdown.
- Begin with YAML frontmatter exactly matching the required schema.
- No extra frontmatter fields.
- `new_entities`, `new_locations`, `unresolved_threads`: lists of double-quoted plain strings (use `[]` when empty). Never `key: value` items — write `- "Name — short description"`, not `- name: "description"`.
- **Before you finish:** count characters in `local_summary` only. If under **100**, add another sentence with on-scene detail (who, where, what changed) until it reaches at least **100** characters.

### Frontmatter schema (required)
---
section_id: {section_id}
local_summary: "<≥100 chars summarizing this section (tie to the outline beat; 2–3 sentences preferred)>"
new_entities:
  - "<entity name — short description>"
new_locations:
  - "<location name — short description>"
unresolved_threads:
  - "<open question or thread, one sentence>"
---

## Prose constraints
- Prose only, after frontmatter.
- No headings, lists, or summaries.
- Dialogue only if justified by context.

## Length
- {section_length} words