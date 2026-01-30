# Outline generation

## Inputs
- seed
- beats_count
- lore_bible
- style_rules
- location_context
- character_context

## Task
Generate a deterministic narrative outline that decomposes the seed into exactly `beats_count` ordered beats.
This outline is the sole structural plan for downstream sections.

## Rules
- Seed defines intent.
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

## Output
- Output valid JSON only (no markdown, no commentary).
- Match the schema exactly.

```json
{
  "beats": [
    {
      "beat_id": 1,
      "title": "Short descriptive title",
      "summary": "1–2 sentence factual description of the narrative event"
    }
  ]
}
```

## Constraints
- beats.length === beats_count
- beat_id starts at 1 and increments sequentially
- title: ≤10 words, ≥3 characters
- summary: ≥20 characters
- Fields allowed: beat_id, title, summary