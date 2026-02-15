# Outline generation

## Inputs
- seed
- beats_count
- lore_bible
- style_rules
- location_context
- character_context
- language (ISO 639-1 code for the story language, e.g. en, es)

## Task
Generate a deterministic narrative outline that decomposes the seed into exactly `beats_count` ordered beats.
This outline is the sole structural plan for downstream sections.
The story must be written in the language indicated by `language` (ISO 639-1 code).

## Rules
- Seed defines intent.
- The entire story (outline and downstream sections) must be in the language corresponding to the given ISO 639-1 code.
- Lore bible is authoritative.
- Do not add prose, dialogue, or stylistic embellishment.
- Beats must represent meaningful narrative transitions.
- Do not contradict lore or context.

## Context
Seed:
{seed}

Lore bible:
{lore_bible}

Style rules:
{style_rules}

Location context:
{location_context}

Character context:
{character_context}

Beats count:
{beats_count}

Language (ISO 639-1 code; write the story in this language):
{language}

## Output
- Output valid JSON only (no markdown, no commentary).
- Match the schema exactly.

```json
{{
  "beats": [
    {{
      "beat_id": 1,
      "title": "Short descriptive title",
      "summary": "1–2 sentence factual description of the narrative event"
    }}
  ]
}}
```

## Constraints
- beats.length === beats_count
- beat_id starts at 1 and increments sequentially
- title: ≤10 words, ≥3 characters
- summary: ≥20 characters
- Fields allowed: beat_id, title, summary