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
Output MUST be valid JSON.
Do NOT wrap in markdown.
Do NOT include commentary.

## Output schema (STRICT)
{{
  "final_script": "<full corrected markdown text>",
  "editor_report": {{
    "issues_found": [
      {{
        "type": "consistency | structure | hygiene | style",
        "description": "Short description of the issue (include what/where, no essays)"
      }}
    ],
    "changes_applied": [
      {{
        "description": "Short description of the change applied (include intent)"
      }}
    ]
  }}
}}

## Length targets
- issues_found: 5–25 items (empty only if genuinely perfect)
- changes_applied: 5–25 items (must reflect actual edits)
- Each description: max 30 words

## Validation rules
- Top-level keys must be exactly: final_script, editor_report
- editor_report must contain exactly: issues_found, changes_applied
- No additional keys allowed anywhere
- If no issues are found, issues_found must be an empty array and changes_applied must explain why no changes were needed
