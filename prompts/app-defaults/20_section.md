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

## Task
Write one narrative section that realizes the given outline beat.
Respect prior content if provided.

## Rules
- Lore bible is authoritative.
- Follow the outline beat strictly. Do not add extra events.
- Maintain continuity with prior sections when context is provided.
- No meta commentary. No explanations.

## Context
Seed:
{seed}

Outline beat:
{outline_beat}

Lore bible:
{lore_bible}

Style rules:
{style_rules}

Rolling summary:
{rolling_summary}

Continuity ledger:
{continuity_context}

Location context:
{location_context}

Character context:
{character_context}

## Output
- Valid Markdown.
- Begin with YAML frontmatter exactly matching the required schema.
- No extra frontmatter fields.

### Frontmatter schema (required)
---
section_id: {section_id}
local_summary: "<≥100 chars summarizing this section>"
new_entities: []
new_locations: []
unresolved_threads: []
---

## Prose constraints
- Prose only, after frontmatter.
- No headings, lists, or summaries.
- Dialogue only if justified by context.

## Length
- {section_length} words