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
{
  "beats": [
    {
      "id": "beat_01",
      "title": "Short, descriptive title",
      "summary": "1–2 sentence factual description of the narrative event",
      "primary_characters": ["<character_id>"],
      "location": "<location_id or null>",
      "state_changes": [
        "brief description of any world or character state change"
      ]
    }
  ]
}

## Length targets
- beats array length MUST equal beats_count
- title: max 10 words
- summary: max 40 words
- state_changes: max 3 entries per beat

## Validation rules
- Beat IDs must be sequential and zero-padded.
- Do not add or remove fields.
- Use null instead of empty strings.
- Arrays must be empty if no values apply.
- Do not infer characters or locations not present in context.
