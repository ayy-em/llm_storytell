# Technical Specification

## Overview

This project implements a **deterministic, file-driven content generation pipeline** capable of producing long-form narrative text and, in later versions, narrated audio and video.

The system is designed to be:

* Runnable **locally** (v1.x)
* Reproducible given identical inputs
* Extensible via configuration and content files
* Driven by a single orchestrated pipeline
* Safe for automated agent-driven development
* Provider-agnostic with respect to LLM backends

The pipeline is intentionally **sequential**, not conversational.
All long-term memory is explicit and persisted to disk.
All run outputs are treated as immutable after completion.

Schemas are authoritative: all structured outputs must validate against schemas in `src/llm_storytell/schemas/`. Output schemas are frozen. Any format change requires:
- SPEC update
- Schema update
- Explicit approval


The pipeline is designed to support **variable output scale**, ranging from:
* Single-section, short-form stories generated from minimal context
* Multi-section, long-form narratives using extensive rotating context

While v1.0 ships with a single app (`grim-narrator`) and a default configuration, the orchestrator must not assume fixed story length, fixed beat count, or fixed context volume.

---

## Concept: Apps (Content Profiles)

An **app** defines a complete content profile, including:

* Lore and world rules
* Context snippets (locations, characters, etc.)
* Tone, narration, and stylistic constraints
* Expected output length and structure
* Audio / presentation defaults (v1.1+)

The pipeline itself is generic. Behavior changes based on the selected app.

### MVP apps

* `grim-narrator` (only app in v1.0)

The architecture must assume multiple apps from the beginning.

---

## Repository Structure (Authoritative)

```
LLM-Storytell/
  README.md
  SPEC.md
  CONTRIBUTING.md
  TASKS.md
  COMPLETED_TASKS.md

  config/
    pipeline.yaml
    model.yaml
    creds.json (gitignored)

  context/
    <app_name>/
      lore_bible.md
      world/
        *.md
      locations/
        *.md
      characters/
        *.md
      style/
        narration.md
        tone.md

  prompts/
    README.md
    shared/
      dev_workflow_prompt.md
    apps/
      <app_name>/
        00_seed.md
        10_outline.md
        20_section.md
        21_summarize.md
        30_critic.md

  runs/
    <run_id>/
      run.log
      inputs.json
      state.json
      artifacts/

  src/
    llm_storytell/
      cli.py
      pipeline/
      steps/
      schemas/
      logging.py
      llm/
```

Generated content must never be committed.

---
## Approved third-party libraries

* requests for HTTP
* httpx if async is needed
* pydantic for validation
* tenacity for retries (optional)
* polars, numpy and pandas
* jsonschema for schema validation

## CLI Interface

### Command (MacOS)

```bash
source .venv/bin/activate
python -m llm_storytell run \
  --app <app_name> \
  --seed "<story description>" \
  --beats <int>
```

### Required arguments

* `--app`

  * Name of the app to run
  * Must correspond to a directory under `context/`
* `--seed`

  * Short natural-language description (2–3 sentences)
  * Describes setting, POV, and general premise

### Optional arguments (v1.0 defaults)

* `--beats`

  * Optional override for number of outline beats
  * Default: 5 (v1.0 hardcoded default; app-defined defaults planned for future versions)
  * Allowed range: **1–20**
* `--sections`

  * Alias of `--beats` (one section per beat)
  * Included for clarity; only one should be used
* `--run-id`

  * Optional override
  * Default format: `run-YYYYMMDD-HHMMSS`
* `--config-path`

  * Default: `config/`
* `--model`

  * Optional override for the model identifier used for **all** LLM calls in this run.
  * Default: `gpt-4.1-mini`
  * If the provider API does not recognize the requested model, the run fails immediately (no retries).

Apps define *recommended* values. The pipeline enforces *absolute* limits.

---

## Context Loading (v1.0)

Context loading is **app-defined but platform-executed**. A single `ContextLoader` validates and selects context at run start; all steps use shared `build_prompt_context_vars(context_dir, state)` for prompt variables.

### Required (run fails early with clear message if missing)

* `context/<app>/lore_bible.md` must exist.
* At least one `.md` file in `context/<app>/characters/` must exist (directory must exist and be non-empty).

### Optional (missing folders must not stop output)

* **Locations:** If `context/<app>/locations/` exists and contains `.md` files, exactly **one** location is included (deterministic: first alphabetically). Otherwise `location_context` is `""`.
* **World:** If `context/<app>/world/` exists and contains `.md` files, **all** world files are loaded in alphabetical order, appended to lore_bible with a clear separator header (`---\n## World context (from world/*.md)\n\n`), and the list of world file paths is recorded in `state.json` under `selected_context.world_files`. If absent, generation still proceeds.

### Selection rules

* **Deterministic:** No randomness. Location: first file alphabetically. Characters: first N alphabetically (N = up to 3, or all if fewer). World: all files in alphabetical order.
* **Logged:** Selections are written to `run.log`.
* **Persisted:** `state.json.selected_context` records `characters` (list of basenames), `location` (basename or null), and `world_files` (list of basenames) for reproducibility.

No pipeline logic may assume a fixed number of context files. Missing optional folders must not stop output.

---

## Pipeline Stages (v1.0)

### Criteria of Success for a Run
A run is successful if all expected artifacts exist and are non-empty:
- outline
- all sections
- summaries
- final_script
- editor_report


### Stage 0: Run Initialization

**Purpose**

* Establish deterministic run context

**Actions**

* Create `runs/<run_id>/`
* Write `inputs.json`
* Initialize `state.json`
* Initialize `run.log`
* Load and validate context (required: lore_bible + at least one character); select context deterministically; log and persist `selected_context`

---

### Stage 1: Outline Pass

**Purpose**
Generate a high-level narrative structure.

**Inputs**

* `seed` (from state)
* `beats_count` (from inputs)
* `lore_bible` (from context)
* `style_rules` (from context)
* `location_context` (from selected context)
* `character_context` (from selected context)

**Process**

* Generate **N outline beats** (N is app-defined or overriden via CLI, N ranges from 1 to 20)

**Outputs**

* `10_outline.json`
* Stored in `state.json.outline`

Validated against `outline.schema.json`.

---

### Stage 2: Draft Pass (Iterative)

Runs once per outline beat. The draft pass must function correctly for any number of sections between **1 and 20**, inclusive.

#### Inputs per section

* `seed` (from state)
* Current outline beat (from state.outline)
* Rolling summary (built from state.summaries)
* Continuity ledger (from state.continuity_ledger)
* `lore_bible` (from context)
* `style_rules` (from context)
* `location_context` (from selected context, optional)
* `character_context` (from selected context, optional)

#### Outputs per section

* `20_section_<NN>.md`
* Section metadata block
* Section summary JSON

All structured outputs validated against schemas.

---

### Post-section Summarization

**Purpose**

* Prevent context drift
* Extract structured continuity updates

**State updates**

* Append to `summaries[]`
* Merge into `continuity_ledger`

---

### Stage 3: Critic / Fixer / Editor Pass

**Purpose**
Consolidate and correct.

**Inputs**

* `seed` (from state)
* `full_draft` (combined from all section artifacts)
* `outline` (from state)
* `lore_bible` (from context)
* `style_rules` (from context)
* `location_context` (from selected context, optional)
* `character_context` (from selected context, optional)

**Checks**

* Contradictions
* Overused phrasing
* POV / tense consistency
* Tone adherence

**Outputs**

* `final_script.md`
* `editor_report.json`

---

## Prompt Variable Contracts

Each pipeline step has a strict contract defining which variables are provided to prompt templates. This ensures consistency between code and prompts, and enables fail-fast validation.

### Variable Sources

Variables come from three sources:
1. **State** (`state.json`): `seed`, `outline`, `summaries`, `continuity_ledger`
2. **Context files**: `lore_bible`, `style_rules`, `location_context`, `character_context`
3. **Step-specific**: `beats_count`, `section_index`, `section_id`, `outline_beat`, `rolling_summary`, `full_draft`

### Per-Step Contracts

#### Outline Step (`10_outline.md`)

**Required variables:**
- `seed` (string): Raw seed from CLI
- `beats_count` (integer): Number of outline beats to generate (1-20)
- `lore_bible` (string): Combined lore bible content (includes world/*.md if present, with separator)
- `style_rules` (string): Combined style/*.md files
- `location_context` (string): Selected location file content (may be empty)
- `character_context` (string): Combined selected character files (may be empty)

**Optional variables:** None

**Validation:** All variables must be provided. `prompt_render.py` validates strict matching.

#### Section Step (`20_section.md`)

**Required variables:**
- `section_id` (integer): 1-based section identifier
- `section_index` (integer): 0-based section index
- `seed` (string): Raw seed from state
- `outline_beat` (string): JSON-serialized outline beat object
- `lore_bible` (string): Combined lore bible content (includes world/*.md if present, with separator)
- `style_rules` (string): Combined style/*.md files

**Optional variables:**
- `rolling_summary` (string): Summary of prior sections (may be empty for first section)
- `continuity_context` (string): Continuity ledger context (may be empty)
- `location_context` (string): Selected location file content (may be empty)
- `character_context` (string): Combined selected character files (may be empty)

**Validation:** Required variables must be provided. Optional variables are provided but may be empty strings.

#### Summarize Step (`21_summarize.md`)

**Required variables:**
- `section_id` (integer): 1-based section identifier
- `section_content` (string): Full markdown content of the section to summarize

**Optional variables:**
- `lore_bible` (string): Currently not provided, reserved for future use

**Validation:** Required variables must be provided.

#### Critic Step (`30_critic.md`)

**Required variables:**
- `seed` (string): Raw seed from state
- `lore_bible` (string): Combined lore bible content (includes world/*.md if present, with separator)
- `style_rules` (string): Combined style/*.md files
- `full_draft` (string): Combined markdown from all sections
- `outline` (string): JSON-serialized outline array

**Optional variables:**
- `location_context` (string): Selected location file content (may be empty)
- `character_context` (string): Combined selected character files (may be empty)

**Validation:** Required variables must be provided. Optional variables are provided but may be empty strings.

### Variable Naming Consistency

- **Style inputs:** Always use `style_rules` (combined from `style/*.md`). Do not use `style_narration` or `style_tone` (these are not provided).
- **Context inputs:** Use `location_context` and `character_context` (may be empty strings if no context selected).
- **State inputs:** Use `seed`, `outline`, `summaries`, `continuity_ledger` (from state.json).

### Unused Prompt Templates

- `00_seed.md`: Reserved for future seed normalization step. Currently unused. The pipeline passes raw `seed` directly to all steps.

### Validation and Fail-Fast Behavior

The `prompt_render.py` module enforces strict variable validation:
- Only `{identifier}` placeholders are recognised (identifier = `[a-zA-Z_][a-zA-Z0-9_]*`). JSON examples (e.g. `{"beats": [...]}`) in templates do not create required variables.
- All placeholders in prompt templates must be provided in the variables dictionary
- Missing required variables raise `MissingVariableError` immediately
- No silent fallbacks or default values
- This ensures prompt-code consistency is caught at runtime, not silently ignored

---

## Logging (Universal, App-agnostic)

Logging is defined once at the platform level and applies uniformly to all apps. Each pipeline run produces a single authoritative log file:

```
runs/<run_id>/run.log
```

Logging behavior must not vary by app. Apps may influence content generation, but not observability.

**Logged events (required)**

* Run initialization (run_id, app, seed)
* Selected context files (including randomized selections)
* Each pipeline stage:
    start timestamp
    end timestamp
    success / failure
* Artifact creation (file path, size)
* Validation failures
* LLM provider metadata:
    provider name
    model name
    prompt token count
    completion token count
    total tokens used

**Explicitly not logged**

- Secrets, credentials, or API keys

Logging exists for:
- Debugging content quirks
- Cost visibility
- Future alerting and guardrails

### Token Usage Tracking (v1.0 required, alerting later)

For each LLM call, the orchestrator must record:

* Prompt token count
* Completion token count
* Total tokens consumed
* Provider name

These metrics must be:

* Logged to `run.log`
* Stored in `state.json` under a `token_usage[]` field
---

## State Management

### `state.json` structure

```json
{
  "app": "grim-narrator",
  "seed": "...",
  "selected_context": {
    "location": "<basename or null>",
    "characters": ["<basename>", ...],
    "world_files": ["<basename>", ...]
  },
  "outline": [...],
  "sections": [...],
  "summaries": [...],
  "continuity_ledger": {...},
  "token_usage": [
    {
      "step": "...",
      "provider": "openai",
      "model": "gpt-x",
      "prompt_tokens": ...,
      "completion_tokens": ...,
      "total_tokens": ...
    }
  ]
}
```

### Rules

* State is updated only after successful step completion
* Failed steps do not mutate state
* State is append-only where possible

---

## LLM Provider Abstraction (v1.0 requirement)

LLM access must be abstracted from the beginning.

### Design requirements

* No step may directly call a vendor SDK
* All calls go through a provider interface, e.g.:

```python
class LLMProvider:
    def generate(self, prompt: str, **kwargs) -> LLMResult
```

* The provider returns a structured result (`LLMResult`) that includes:
  * provider name
  * model identifier
  * prompt / completion / total token counts (when available from the backend)

### Initial implementation

* OpenAI-backed provider only (`OpenAIProvider`)
* Token usage from the OpenAI response (`usage.prompt_tokens`, `usage.completion_tokens`, `usage.total_tokens`) is surfaced through `LLMResult`
* Pipeline steps use this metadata together with `record_token_usage()` to log and persist token usage into `run.log` and `state.json.token_usage[]`

### Rationale

* Enables future support for:

  * Multiple providers
  * Local models
  * Fallback strategies
  * Cost-aware routing

---

## Pipeline Configuration

Defined in `config/pipeline.yaml`.

The pipeline is declarative:

* Step order
* Prompt template paths
* Validators
* Loop definitions

The orchestrator executes strictly in order.

---

## Run Artifacts

Each run produces:

```
runs/<run_id>/
  run.log
  inputs.json
  state.json
  artifacts/
    10_outline.json
    20_section_01.md
    ...
    final_script.md
    editor_report.json
```

Runs are immutable once complete.

---
python -m llm_storytell run --app grim-narrator --seed "Police brutality, no matter how severe, is just a mundane part of existence in the lower 
levels of Skrepa Union's MotherCity"
## Roadmap (Directional)

* **v1.0** – Local, text-only pipeline (multi-app capable)
* **v1.0.1** - Add soft warnings when approaching context limits
* **v1.1** – Text-to-speech audiobook output
* **v1.2** – Background music mixing and audio polish
* **v1.3** – Cloud execution + scheduled delivery (Telegram / email)
* **v1.4** – One-command video generation
* **v1.4.1** – Burned-in subtitles
* **v1.5** – Vector database for large-scale context retrieval and rotation
* **v1.6** – Multi-LLM provider support, routing, and cost-aware selection

---

## Non-goals (v1.x)

* Interactive chat interfaces
* Streaming generation
* Multi-user concurrency
* UI beyond CLI
* Monetization or platform integration

---

## Definition of Done (v1.0)

* CLI produces a complete `final_script.md`
* Context selection is logged and reproducible
* All structured outputs validate against schemas
* No hidden state outside `runs/`
* Pipeline failures are detectable and debuggable
* No manual intervention required once invoked
* The task is not done unless the pipeline can be executed manually at least once for a real run.

