# Outline generation prompt

## Required inputs
- seed (string, required)
- beats_count (integer, required)
- lore_bible (string, required)
- style_rules (string, required)
- location_context (string, required)
- character_context (string, required)

## Purpose
Generate a structured, machine-readable narrative outline that decomposes the seed into a fixed number of beats.
This outline serves as the sole structural plan for all downstream section generation.

## Instructions
- Use the seed as the authoritative source of intent.
- Do NOT introduce plot elements that contradict the lore bible.
- Do NOT include prose, dialogue, or stylistic embellishment.
- Each beat must represent a meaningful narrative transition.
- Beats must be ordered, deterministic, and internally consistent.

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

Requested number of beats:
{beats_count}

## Output format
Output MUST be valid JSON.
Do NOT wrap in markdown.
Do NOT include commentary or explanations.

## Output schema
{{
  "beats": [
    {{
      "beat_id": 1,
      "title": "Short, descriptive title",
      "summary": "1–2 sentence factual description of the narrative event"
    }}
  ]
}}

## Length targets
- beats array length MUST equal beats_count
- title: max 10 words, min 3 characters
- summary: min 20 characters

## Validation rules
- beat_id must be an integer starting at 1, incrementing sequentially (1, 2, 3, ...)
- Do not add or remove fields. Only include: beat_id, title, summary
- title must be at least 3 characters
- summary must be at least 20 characters
