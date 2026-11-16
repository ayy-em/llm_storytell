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

## Inputs for this step
Seed, lore bible, style rules, location and character context, and language are given in "Story context" above.

Beats count:
{beats_count}

## Output
- Output valid JSON only (no markdown, no commentary).
- Match the schema exactly.

```json
{{
  "beats": [
    {{
      "beat_id": 1,
      "title": "Short descriptive title",
      "summary": "2–4 sentences, ≥100 characters: concrete events, setting, stakes (feeds section summaries)"
    }}
  ]
}}
```

## Constraints
- beats.length === beats_count
- beat_id starts at 1 and increments sequentially
- title: ≤10 words, ≥3 characters
- summary: ≥100 characters (substantive beat plan; avoids one-line placeholders downstream)
- Fields allowed: beat_id, title, summary