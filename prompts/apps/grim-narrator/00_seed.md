# Seed normalization prompt
#
# NOTE: This prompt template is currently UNUSED and RESERVED for future implementation.
# The pipeline currently passes the raw seed string directly to outline, section, and critic steps.
# This template would be used if a seed normalization step is added to the pipeline in the future.
#
# If implementing seed normalization:
# - This step would run before outline generation
# - It would transform the raw seed into a structured seed_intent object
# - The seed_intent would then be passed to downstream steps instead of raw seed
#
# DO NOT DELETE: Reserved for v1.1+ seed normalization feature.

# Seed normalization prompt

## Required inputs
- seed (string, required)
- app_name (string, required)

## Purpose
Normalize the raw seed into a deterministic, structured intent that downstream stages can rely on.
This step must not introduce new narrative elements or stylistic decisions.

## Instructions
- Treat the seed as immutable source intent.
- Do NOT invent themes, plot points, characters, or settings.
- Do NOT rewrite the seed as prose.
- Extract constraints only if they are explicitly stated or unavoidable.
- If information is missing, leave fields empty rather than guessing.

## Output format
Output MUST be valid JSON.
Do NOT wrap in markdown.
Do NOT include commentary.

## Output schema
{
  "app": "<app_name>",
  "seed_raw": "<original seed, verbatim>",
  "intent_summary": "<1–2 sentence neutral description of the intended outcome>",
  "explicit_constraints": {
    "tone": "<string or null>",
    "genre": "<string or null>",
    "format": "<string or null>",
    "length_hint": "<string or null>"
  },
  "implicit_constraints": [
    "<short factual constraint inferred directly from seed>",
    "<omit if none>"
  ],
  "excluded_elements": [
    "<elements explicitly disallowed by the seed>",
    "<omit if none>"
  ]
}

## Length targets
- intent_summary: max 40 words
- implicit_constraints: max 5 entries
- excluded_elements: max 5 entries

## Validation rules
- All fields must be present.
- Use null instead of empty strings.
- Arrays must be empty if no entries apply.
- No additional keys are allowed.
