# Section summarization prompt

## Required inputs
- section_id (string, required)
- section_content (string, required)

## Optional inputs
- lore_bible (string, optional)

## Purpose
Produce a machine-readable summary and continuity update for a single section.
This output supports rolling summaries and continuity enforcement but must work even in minimal setups.

## Instructions
- Summarize factual events only.
- Extract continuity-relevant facts if present.
- If no clear continuity updates exist, return empty arrays.
- Do NOT critique style.
- Do NOT restate prose verbatim.
- Do NOT infer information not explicitly stated.

## Section content
{section_content}

## Output format
Output MUST be valid JSON.
Do NOT wrap in markdown.
Do NOT include commentary.

## Output schema
{{
  "section_id": "<string>",
  "summary": "<2–4 sentence factual summary>",
  "continuity_updates": {{
    "characters": [],
    "locations": [],
    "world": []
  }}
}}

## Length targets
- summary: max 80 words
- continuity_updates arrays: max 5 total entries combined

## Validation rules
- All keys must be present.
- Arrays must be empty if no updates apply.
- No additional keys are allowed.
