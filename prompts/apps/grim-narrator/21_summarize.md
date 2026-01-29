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
  "section_id": <integer>,
  "summary": "<2–4 sentence factual summary, minimum 200 characters>",
  "continuity_updates": {{
    "<key1>": "<value1>",
    "<key2>": "<value2>",
    ...
  }}
}}

**continuity_updates format:**
- Must be a dictionary (object) with string keys and string values.
- Keys represent continuity elements (e.g., "protagonist_state", "current_location", "mood", "plot_thread_1").
- Values are string descriptions of the current state.
- Use empty object {{}} if no continuity updates apply.
- Do NOT use arrays. All values must be strings.

## Length targets
- summary: minimum 200 characters, max 80 words
- continuity_updates: include only relevant updates (typically 0-5 key-value pairs)

## Validation rules
- All required keys must be present: section_id, summary, continuity_updates
- section_id must be an integer
- summary must be a string with at least 200 characters
- continuity_updates must be an object (dictionary) with string keys and string values
- No additional keys are allowed
