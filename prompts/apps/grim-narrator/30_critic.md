# Critic / fixer prompt

## Required inputs
- seed (string, required)
- lore_bible (string, required)
- style_rules (string, required)
- full_draft (string, required)
- outline (string, required)

## Optional inputs
- location_context (string, optional)
- character_context (string, optional)

## Purpose
Produce a corrected final script and a machine-readable editor report.
Corrections must preserve intent, continuity, and lore consistency.

## Non-negotiable constraints (HARD)
- The lore bible is authoritative. Do NOT contradict it.
- Do NOT introduce new plot elements, factions, locations, rules, or characters not already present in the draft or provided context.
- Do NOT reorder or delete sections.
- Do NOT add headings or frontmatter. Output should be plain Markdown prose only.
- Prefer minimal edits that fix issues over large rewrites.

## Layered checklist (perform in this order)

### Layer 1: Consistency & continuity (hard correctness)
- Check for contradictions with:
  - lore_bible
  - outline (ensure beat order and intent match)
- Fix contradictions and continuity errors with minimal edits.

### Layer 2: Structural integrity (format and invariants)
- Ensure the final script preserves the same section ordering as full_draft.
- Remove accidental artifacts:
  - duplicated paragraphs
  - broken markdown formatting
  - stray section separators (if any)
- Ensure the final script is one coherent markdown document.

### Layer 3: Language hygiene (repetition & clarity)
- Identify and reduce:
  - overused words / repeated phrases
  - redundant sentences
  - unclear pronoun references
- Do NOT change plot content while doing this.

### Layer 4: Style alignment (polish within constraints)
- Apply style rules to fix inconsistencies in voice.
- Do NOT add decorative flourish if it changes intent.

## Context
Seed:
{seed}

Lore bible:
{lore_bible}

Style rules:
{style_rules}

Outline:
{outline}

Location context (if any):
{location_context}

Character context (if any):
{character_context}

Full draft:
{full_draft}

## Output format
Output MUST be valid JSON that can be parsed by `json.loads()`.
Do NOT wrap in markdown code blocks (no ```json markers).
Do NOT include commentary or explanatory text.
Do NOT add any text before or after the JSON.
Start your response with a single opening brace and end with a single closing brace.

**CRITICAL: JSON escaping for final_script**
The `final_script` field contains markdown text that MUST be a properly escaped JSON string.
- Every double quote `"` inside the markdown must be escaped as `\"`
- Every backslash `\` must be escaped as `\\`
- Newlines must be escaped as `\n` (do NOT use actual line breaks in the JSON string value)
- Tabs must be escaped as `\t`
- The entire markdown document must be a single continuous JSON string value
- Example: `"final_script": "# Title\\n\\nParagraph with \\\"quotes\\\"."`

**Test your JSON**: Before responding, verify your JSON is valid. If `final_script` contains markdown with quotes or special characters, they MUST be escaped.

## Output schema (STRICT)
{{
  "final_script": "<full corrected markdown text, properly escaped as JSON string>",
  "editor_report": {{
    "issues_found": [
      "<string description 1>",
      "<string description 2>",
      ...
    ],
    "changes_applied": [
      "<string description 1>",
      "<string description 2>",
      ...
    ]
  }}
}}

**Important notes:**
- `final_script` is a single string containing the entire corrected markdown document.
- `editor_report.issues_found` is an array of strings (not objects).
- `editor_report.changes_applied` is an array of strings (not objects).

## Length targets
- issues_found: 5–25 items (empty only if genuinely perfect)
- changes_applied: 5–25 items (must reflect actual edits)
- Each description: max 30 words

## Validation rules
- Top-level keys must be exactly: final_script, editor_report
- editor_report must contain exactly: issues_found, changes_applied
- No additional keys allowed anywhere
- If no issues are found, issues_found must be an empty array and changes_applied must explain why no changes were needed
