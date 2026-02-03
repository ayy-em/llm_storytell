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

While v1.0 ships with a committed example app (`example_app`) and a default configuration, the orchestrator must not assume fixed story length, fixed beat count, or fixed context volume.

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

* `example_app` (committed example app in v1.0)

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

  apps/
    default_config.yaml
    <app_name>/
      context/
        lore_bible.md
        world/
          *.md
        locations/
          *.md
        characters/
          *.md
        style/
          *.md
      prompts/          (optional; if absent, app uses app-defaults)
        *.md
      app_config.yaml   (optional)

  prompts/
    README.md
    shared/
      dev_workflow_prompt.md
    app-defaults/
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
      tts/           (when TTS ran: prompts/, outputs/)
      voiceover/     (when TTS ran: stitched voiceover, bg)

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

### Arguments

| Flag | Values allowed | Description |
|------|----------------|-------------|
| `--app` | app name (required) | Name of the app to run. Must correspond to a directory under `apps/` (i.e. `apps/<app_name>/` with at least `apps/<app_name>/context/lore_bible.md`). |
| `--seed` | string (required) | Short natural-language description (2–3 sentences). Describes setting, POV, and general premise. |
| `--beats` | integer 1–20 | Number of outline beats. Default: from app config (or pipeline default). Overrides app when set. |
| `--sections` | integer 1–20 | Alias for `--beats` (one section per beat). Use one or the other. |
| `--run-id` | string | Override run ID. Default: `run-YYYYMMDD-HHMMSS`. |
| `--config-path` | path | Config directory. Default: `config/`. |
| `--model` | model identifier | Model used for **all** LLM calls in this run. Default: `gpt-4.1-mini`. Run fails immediately if the provider does not recognize the model. |
| `--section-length` | integer N | Target words per section; pipeline uses range `[N*0.8, N*1.2]`. Overrides app config when set. |
| `--word-count` | integer N (100 < N < 15000) | Target total word count for the story. Pipeline derives beat count and section length from N (and from app/CLI section length when only `--word-count` is set). When both `--beats` and `--word-count` are provided, `word-count / beats` must be in (100, 1000) (words per section). |
| `--tts` | flag | Enable TTS (text-to-speech) after critic step. Default when neither `--tts` nor `--no-tts` is set. |
| `--no-tts` | flag | Disable TTS; pipeline ends after critic step. If both `--tts` and `--no-tts` are given, `--no-tts` wins. |
| `--tts-provider` | string | TTS provider (e.g. `openai`). Overrides app config. Resolution order: CLI → `app_config.yaml` → default (OpenAI). |
| `--tts-voice` | string | TTS voice name (e.g. `Onyx`). Overrides app config. Resolution order: CLI → `app_config.yaml` → default (Onyx). |

Defaults for beats and section_length come from `apps/default_config.yaml` merged with optional `apps/<app_name>/app_config.yaml`. Apps define *recommended* values; the pipeline enforces *absolute* limits.

**TTS (v1.1+):** TTS flags control whether a text-to-speech step runs after the critic. Resolution order for `--tts-provider` and `--tts-voice` is: CLI flags → `apps/<app_name>/app_config.yaml` → pipeline defaults (OpenAI / gpt-4o-mini-tts / Onyx). The resolved voice name is **normalized to lowercase** before being sent to the TTS provider (e.g. OpenAI expects `onyx`, not `Onyx`); config and CLI may use either casing. When `--no-tts` is set, the pipeline ends after the critic step and no TTS step is run; `state.json` does not contain `tts_config`. When TTS is enabled, the pipeline runs the TTS step then the audio-prep step; **ffmpeg** (and ffprobe) must be on PATH for the audio-prep step (stitching and mixing).

**Target word count (v1.0.3):** When `--word-count N` is used, the pipeline derives `beat_count` (round N / baseline section length, clamped to 1–20) and per-section length (N / beat_count), then passes the range `[per_section*0.8, per_section*1.2]` as section_length. Generated stories are intended to fall within approximately 10% of the target word count; this is best-effort and can be verified manually or via tests.

---

## Context Loading (v1.0)

Context loading is **app-defined but platform-executed**. A single `ContextLoader` validates and selects context at run start; all steps use shared `build_prompt_context_vars(context_dir, state)` for prompt variables. Context lives under `apps/<app_name>/context/`.

### Required (run fails early with clear message if missing)

* `apps/<app_name>/context/lore_bible.md` must exist.
* At least one `.md` file in `apps/<app_name>/context/characters/` must exist (directory must exist and be non-empty).

### Optional (missing folders must not stop output)

* **Locations:** If `apps/<app_name>/context/locations/` exists and contains `.md` files, exactly **one** location is included (deterministic: first alphabetically). Otherwise `location_context` is `""`.
* **World:** If `apps/<app_name>/context/world/` exists and contains `.md` files, **all** world files are loaded in alphabetical order, appended to lore_bible with a clear separator header (`---\n## World context (from world/*.md)\n\n`), and the list of world file paths is recorded in `state.json` under `selected_context.world_files`. If absent, generation still proceeds.

### Selection rules

* **Deterministic:** No randomness. Location: first file alphabetically. Characters: first N alphabetically (N from app config or pipeline default). World: all files in alphabetical order.
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

Logging behavior does not vary by app. Apps may influence content generation, but not observability.

**Logged events (required)**

* Run initialization (run_id, app, seed)
* Selected context files (deterministic; no randomness)
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

### TTS usage and cost (v1.2)

When the TTS step runs, the pipeline records TTS usage and estimates cost:

* **Per segment:** Each TTS call logs the number of characters sent; `state.json` `tts_token_usage[]` entries include `input_characters` per segment.
* **Run completion:** The pipeline logs and prints a combined summary: Chat token counts (input, output, total) and TTS characters requested, then a line such as `Estimated cost: $X Chat + $Y TTS = $Z total`. Cost is derived from provider/model pricing (e.g. per 1M characters for TTS).

### Context size warning (v1.0.1)

When combined context (lore + style + location + characters) approaches or exceeds a defined character threshold, a **WARNING** is logged to `run.log`. Context selection and pipeline success/failure are unchanged; the run does not fail.

* **Pipeline-level default:** A default character threshold (e.g. 15 000) is defined. When combined context length is at or above this value, one warning is logged.
* **Per-model overrides:** A dictionary maps model identifiers to character thresholds. If the run's model is in this map, that threshold is used; otherwise the pipeline default is used.
* **Message:** The log entry includes total character count and the threshold used.
* **No failure:** Missing or excessive context does not change selection logic or cause the run to fail.
---

## State Management

### `state.json` structure

```json
{
  "app": "example_app",
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
  "token_usage": [...],
  "tts_config": { "tts_provider": "...", "tts_model": "...", "tts_voice": "...", ... },
  "tts_token_usage": [...],
  "final_script_path": "artifacts/final_script.md",
  "editor_report_path": "artifacts/editor_report.json"
}
```

When `--no-tts` is set, `tts_config` is omitted. `tts_token_usage` is present only after the TTS step has run successfully; each entry includes `input_characters` (characters sent to the TTS API for that segment). `final_script_path` and `editor_report_path` are set after the critic step.

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

Enables future support for:
- Multiple providers
- Local models
- Fallback strategies
- Cost-aware routing

---

## Pipeline Configuration

Step order is fixed and implemented in the pipeline runner (`pipeline/runner.py`), invoked from `cli.py`. The file `config/pipeline.yaml` exists but may be empty or used for reference only; the pipeline does not load step order from YAML in v1.0.

The orchestrator executes strictly in order:

1. **Run init** — create run directory, inputs.json, state.json, run.log; load and select context.
2. **Outline** — generate outline beats.
3. **For each beat:** section, then summarize.
4. **Critic** — final script and editor report.
5. **When TTS is enabled (default):** **TTS step** (chunk final script, synthesize segments to audio) → **audio-prep step** (stitch segments, add background music, mix to final narration). When `--no-tts` is set, the pipeline ends after the critic step.

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
    30_critic_raw_response.txt
    final_script.md
    editor_report.json
    narration-<app_name>.<ext>   (when TTS/audio ran)
  llm_io/
    <stage_name>/
      prompt.txt
      response.txt   (only when non-empty)
      meta.json
      raw_response.json
  tts/                            (when TTS enabled and TTS step ran)
    prompts/
      segment_01.txt
      ...
    outputs/
      segment_01.<ext>
      ...
  voiceover/                      (when TTS/audio ran)
    voiceover.<ext>
    concat_list.txt
    bg_looped.wav
    bg_enveloped.wav
```

Runs are immutable once complete.

### Failure semantics

* **Missing required context** (e.g. no `lore_bible.md` or no character file): run fails at initialization with a clear error message; no run directory is left behind (or init is atomic so partial state is not committed).
* **Step failure** (outline, section, summarize, critic): process exits non-zero; error is printed to stderr; details are written to `run.log`; `state.json` is not updated for the failed step (state is only updated after successful step completion).
* **Validation failure** (schema or prompt variable): step raises; orchestrator logs and exits non-zero; see `run.log` for the failing step and artifact.
* **TTS step failure:** Missing final script, chunking producing no segments or more than 22, or TTS provider error raises `LLMTTSStepError`; process exits non-zero; error printed to stderr; state not updated for TTS. Imperfect chunking (no newline by max words) logs a warning but does not fail.
* **Audio-prep step failure:** Missing `tts/outputs`, ffmpeg/ffprobe not on PATH or non-zero exit, or no background music file found raises `AudioPrepStepError`; process exits non-zero; error printed to stderr. **ffmpeg** (and ffprobe) must be on PATH when TTS/audio is run.

---

## Roadmap (Directional)

* **v1.0** – Local, text-only pipeline (multi-app capable)
* **v1.0.1** – Soft warnings when approaching context limits
* **v1.0.2** – App-specific pipeline configurations
* **v1.0.3** – Generating stories with target word count
* **v1.1** – Text-to-speech audiobook output
* **v1.2** – Background music mixing & voiceover audio quality — **Current version (released)**
* **v1.3** – Increased pipeline flexibility, driven by app-specific configs
* **v1.4** – Multi-LLM provider support
* **v1.5** – Smart prompt routing and cost-aware provider selection
* **v1.6** – Add a "Voiceover text preparation" and support for phonetic hints 
* **v1.7** – Cloud execution + scheduled delivery via Telegram
* **v2.0** – RAG Implementation + Vector db for universe's context
* **v3.0** – Background music generation
* **v3.0** – Video generation
* **v3.1** – Videos now feature auto-generated subtitles

---

## Non-goals (at this moment)

* Interactive chat interfaces
* Streaming generation
* Multi-user concurrency
* UI beyond CLI
* Monetization or platform integration
