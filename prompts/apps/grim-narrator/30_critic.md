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
Your response MUST consist of exactly two blocks separated by clear markers:

**Block 1: Final Script (Plain Markdown)**
Start with the exact marker: `===FINAL_SCRIPT===`
Then output the complete corrected markdown document as plain text (NOT JSON-escaped).
End the markdown content, then start the next block.

**Block 2: Editor Report (JSON)**
Start with the exact marker: `===EDITOR_REPORT_JSON===`
Then output a valid JSON object (no markdown code blocks, no wrapping).
The JSON must be parseable by `json.loads()`.

**CRITICAL: Format Requirements**
- Do NOT include any text before `===FINAL_SCRIPT===`
- Do NOT include any text between the two blocks except the markers
- Do NOT include any text after the JSON block
- The final_script block is plain markdown - no escaping needed
- The editor_report JSON must be valid JSON with proper escaping for JSON strings only

## Output schema

**Block 1 format:**
```
===FINAL_SCRIPT===
[Your complete corrected markdown document here, as plain text]
```

**Block 2 format:**
```
===EDITOR_REPORT_JSON===
{{
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
```

**Important notes:**
- `final_script` is plain markdown text (not JSON-escaped, not in a JSON string)
- `editor_report.issues_found` is an array of strings (not objects)
- `editor_report.changes_applied` is an array of strings (not objects)
- The JSON block must be valid JSON - escape quotes within JSON string values only

## Length targets
- issues_found: 5–25 items (empty only if genuinely perfect)
- changes_applied: 5–25 items (must reflect actual edits)
- Each description: max 30 words

## Validation rules
- Top-level keys must be exactly: final_script, editor_report
- editor_report must contain exactly: issues_found, changes_applied
- No additional keys allowed anywhere
- If no issues are found, issues_found must be an empty array and changes_applied must explain why no changes were needed
