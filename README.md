# LLM-Storytell

## General info

This README’s primary target audience is **AI agents working on this repository**.
It is also accurate for humans who enjoy clarity.

![LLM-Storytell - Title image](assets/hero-image.png)


The system is pipeline-first and app-configured: a single core pipeline operates over different “apps” (content profiles) that define tone, context, structure, and output expectations.

It is designed to support **multiple content “apps”** (profiles), each with its own:

* Lore and world context
* Tone and narration rules
* Output length and structure
* Audio / voice / background style (v1.1+)

The first app is **grim-narrator** (all the lore content is .gitignored tho). It will not be the last.

---

## Design goals

The README intentionally avoids low-level mechanics; **`SPEC.md` is the source of truth** for execution details.

The system is explicitly designed to:

* Generate long-form content from short prompts
* Be **reproducible and inspectable**
* Be able to work with both extremely limited and over-supplied broader context
* Avoid hidden memory or conversational drift
* Persist *everything* to disk
* Be extended by configuration and content files, not code changes
* Be safe to operate via automated coding agents

Creativity is allowed. Ambiguity is not.

---

## Cursor IDE note (important)

This repository includes a `.cursor/` directory containing **project-level agent rules**.

If you are using Cursor:

* Do **not** delete or modify `.cursor/rules/`
* If human, read `CURSOR_WORKFLOW.md`
* These rules define the required task workflow, validation steps, and scope limits

If you are not using Cursor:

* Treat these rules as authoritative documentation of the intended agent workflow

---

## What this project is (and is not)

### This **is**

* A general-purpose **content generation pipeline**
* A deterministic orchestration of LLM calls
* A system for producing text, audio, and later video
* A framework for multiple content profiles (“apps”)

### This **is not**

* A chat interface
* An interactive storytelling engine
* A real-time or streaming generator
* A hosted service (yet)
* A creative writing assistant

This is infrastructure. Not vibes.

---

## Core concept: apps / profiles

An **app** defines *what kind of content* is being generated.

Each app provides:

* A lore bible
* Context snippets (locations, characters, etc.)
* Tone and narration rules
* Expected output length
* Audio and presentation defaults (future versions)

Apps may range from minimal configurations (e.g. a single lore file and a short prompt producing a one-page story) to extensive setups with large rotating context libraries and long-form outputs.

Example apps:

* `grim-narrator`
  60-minute bleak, depressive, slow-paced stories
* `toddler-bedtime` (future)
  10-minute lighthearted stories, upbeat tone, calm voice
* others later

### MVP scope

* Only **grim-narrator** exists
* Architecture assumes more will be added

---

## Context handling (MVP behavior)

For the active app (e.g. `grim-narrator`):

* **Required:** The app’s **lore bible** (`context/<app>/lore_bible.md`) must exist, and at least one character file in `context/<app>/characters/*.md` must exist. If either is missing, the run fails early with a clear error.
* **Optional:** If `context/<app>/locations/` has `.md` files, exactly one location is included (first alphabetically). If `context/<app>/world/` has `.md` files, all are loaded in alphabetical order and folded into the lore bible with a visible separator; the list is stored in `selected_context.world_files`.
* Selection is **deterministic** (no randomness): location = first alphabetically, characters = first N (up to 3) alphabetically. Selections are logged and persisted in `state.json` for reproducibility.

---

## How it works (intentionally high-level)

1. A short seed prompt is provided via CLI
2. The active app’s rules and context are loaded
3. A fixed multi-stage pipeline runs:
   * outline → draft → critique
4. All intermediate artifacts are persisted
5. A final script is produced
6. Later versions convert this into audio and video

Detailed mechanics live in `SPEC.md`.
README stays readable.

### LLM provider abstraction (v1.0)

All LLM calls go through a small provider interface (`LLMProvider`) instead of using vendor SDKs directly. The default implementation is an OpenAI-backed provider that returns an `LLMResult` object containing:

- Provider and model identifiers
- Prompt / completion / total token counts (when the backend reports them)

Pipeline steps are responsible for taking this metadata and recording token usage into `run.log` and `state.json` via the logging and token-tracking utilities.

### Prompt Templates and Variable Contracts

Each pipeline step uses a prompt template (`.md` files in `prompts/apps/<app_name>/`) that defines the LLM instructions. These templates use Python string formatting with variables provided by the pipeline code.

**Important constraints:**

* **Strict variable validation**: All variables referenced in prompt templates must be provided by the corresponding step code. Missing variables cause immediate failures (no silent fallbacks).
* **Code is authoritative**: Prompt templates must match the variables provided by pipeline steps, not vice versa.
* **Variable contracts**: Each step has a documented contract of required vs optional variables (see `SPEC.md` for details).
* **Fail-fast behavior**: The `prompt_render.py` module validates all variables before rendering, ensuring prompt-code consistency is caught at runtime.

**Known limitations:**

* `00_seed.md` exists but is currently unused (reserved for future seed normalization step).
* Style inputs use `style_rules` (combined from `style/*.md` files), not separate `style_narration`/`style_tone` variables.
* Context variables (`location_context`, `character_context`) may be empty strings if no context files are selected.
* Optional variables are always provided but may be empty strings.

For detailed per-step variable contracts, see `SPEC.md` section "Prompt Variable Contracts".

---

## Repository structure (simplified)

```
LLM-Storytell/
  pyproject.toml
  README.md
  SPEC.md
  CONTRIBUTING.md
  TASKS.md
  COMPLETED_TASKS.md

  config/
    creds.json

  prompts/
    README.md
    shared/
    apps/
      <app_name>/
  context/
    <app_name>/
      characters/
      locations/
      style/
      world/
      lore_bible.md

  runs/
    <immutable run outputs>

  src/
    llm_storytell/
      pipeline/
      steps/
      schemas/
  
  tests/
    fixtures/
```

App-specific structure may evolve and change from app to app. Generated content must never be committed.

---

## Quickstart

### Prerequisites

* Python **3.12**
* `uv`
* OpenAI API key

### Setup

```bash
git clone https://github.com/ayy-em/llm_storytell.git
cd llm_storytell
uv sync
```

Create credentials file:

```json
// config/creds.json
{
  "OPENAI_KEY": "your_api_key_here"
}
```

---

## Running the pipeline (MVP)

```bash
python -m llm_storytell run \
  --app grim-narrator \
  --seed "A low-level worker describes a single ordinary day in a decaying future city."
```

The `--app` argument selects the content profile to use. Only `grim-narrator` app exists in v1.0.

Optional arguments include `--model` (model identifier for all LLM calls in the run; default: `gpt-4.1-mini`; run fails immediately if the provider does not recognize the model), `--beats` / `--sections` (1–20), `--run-id`, and `--config-path`. See `SPEC.md` for full CLI reference.

For the OpenAI provider, `--model` accepts any model ID supported by the OpenAI Chat Completions API (e.g. `gpt-4.1-mini`, `gpt-4.1-nano`, `gpt-4o`, `gpt-4`). See [OpenAI’s models documentation](https://platform.openai.com/docs/models) for the current list.

On success, a new directory appears under `runs/` containing:

* All intermediate artifacts
* `state.json`
* Final script output

Runs are immutable once completed.

---

## Development model

This repository is designed for **agent-driven development**.

Before making changes:

* Read `SPEC.md`
* Read `CONTRIBUTING.md`
* Follow `.cursor/rules/`
* Work one task at a time from `TASKS.md` (completed tasks are moved to `COMPLETED_TASKS.md`)

Agent workflow source of truth: .cursor/rules/00-workflow.md. If any workflow instructions conflict, the Cursor rules win.


If something is unclear, stop.

---

## Roadmap (non-binding, directional)

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

## Usage note

This project is intended for **local, personal experimentation**.

If you use copyrighted universes as inspiration, understand the implications before distributing outputs.

---

If an AI agent is reading this:

Follow the spec.
Follow the tasks.
Write boring code.
