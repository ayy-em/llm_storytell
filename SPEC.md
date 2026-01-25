# Technical Specification

## Overview

This project implements a **deterministic, file-driven content generation pipeline** that produces long-form narrative text and, in later versions, narrated audio. The system is designed to be:

* Fully runnable **locally**
* Reproducible (given identical inputs)
* Extensible via configuration and prompt files
* Orchestrated via a single CLI entry point
* Schemas are authoritative: outputs should always adhere to (and be validated against) schemas in src/llm-storytell/schemas/*

The pipeline is intentionally **sequential**, not conversational. All long-term memory is explicit and persisted to disk. All run outputs are to be treated as immutable after completion.

---

## MVP / v1.0 – Text Generation Only

### High-level scope

At MVP stage:

* A **single content creation pipeline** exists
* The pipeline is executed via a **CLI command**
* The CLI accepts a **short textual seed** (2–3 sentences) describing the story concept
* The orchestrator executes a fixed sequence of generation steps
* All intermediate and final artifacts are persisted under a run-specific directory

No audio generation, embeddings, or external storage are included in v1.0.

---

## CLI Interface

### Command

```bash
python -m llm-storytell run --seed "<story description>"
```

### Required arguments

* `--seed`
  A short natural-language description (2–3 sentences) describing:

  * The general setting
  * The point of view
  * The type of story to be generated

### Optional arguments (v1.0 defaults)

* `--sections` (default: 12, min: 10, max: 14)
* `--run-id` (optional override, default id convention is `run-0001-DD.MM.YY-HH.ss`)
* `--config-path` (default: `config/`)

---

## Pipeline Stages (v1.0)

### Stage 1: Outline Pass

**Purpose**
Generate a high-level narrative structure that constrains all later steps.

**Inputs**

* `seed` (from CLI)
* `style_rules` (from config)
* `lore_bible` (static universal context)

**Process**

* Generate **10–14 outline beats**
* Each beat represents a high-level narrative unit corresponding to one section

**Outputs**

* `outline[]`
  An ordered list of beats, each containing:

  * `beat_id`
  * `title`
  * `summary` (2–4 sentences, no prose)
  * `intended_tone` (optional label)

**Persistence**

* Written to:
  `runs/<run_id>/10_outline.json`
* Added to `state.json` under `outline`

---

### Stage 2: Draft Pass (Iterative, Section-Based)

This stage runs **once per outline beat**.

#### Inputs per section

For section *N*:

* `outline[N]`
* `rolling_summary`

  * Aggregated summaries of prior sections
  * Target size: **400–900 tokens**
* `continuity_ledger`
* `style_rules`
* Retrieved lore snippets relevant to the current beat (static lookup in v1.0)

#### Section generation output

For each section:

* `section_content` (Markdown)
* `section_metadata` (machine-readable block):

  * `section_id`
  * `new_entities`
  * `new_locations`
  * `timeline_updates`
  * `unresolved_threads`
  * `local_summary` (200–400 tokens)

Persisted as:

* `runs/<run_id>/20_section_<NN>.md`

---

### Post-section Summarization Step

Immediately after each section generation.

**Purpose**

* Prevent context drift
* Extract structured continuity information
* Produce compact summaries for downstream steps

**Inputs**

* Generated section content
* Prior continuity ledger

**Outputs**

* `section_summary`
* `continuity_updates`
* `open_threads`

**State updates**

* Append to `summaries[]`
* Merge into `continuity_ledger`

---

### Continuity Passer (Internal Mechanism)

Before generating the next section, the orchestrator prepares inputs:

* `rolling_summary`

  * Concatenation of the last *N* section summaries
  * Hard token cap enforced
* Updated `continuity_ledger`
* Next outline beat
* Relevant lore snippets

This is not a model call. It is deterministic orchestration logic.

---

### Stage 3: Critic / Fixer / Editor Pass

**Purpose**
Consolidate all sections into a single coherent document and apply corrective transformations.

**Inputs**

* All section contents
* Final continuity ledger
* Style rules

**Checks performed**

* Contradiction detection (names, locations, timeline)
* Overused phrase detection and reduction
* Narration consistency (POV, tense)
* Tone adherence

**Outputs**

* `final_script.md` (single document)
* `editor_report.json` containing:

  * Issues detected
  * Changes applied
  * Remaining warnings (if any)

---

## State Management

Throughout the pipeline, the orchestrator maintains a persistent `state.json`.

### `state.json` structure

```json
{
  "seed": "...",
  "style_rules": {...},
  "outline": [...],
  "sections": [...],
  "summaries": [...],
  "continuity_ledger": {...},
  "retrieved_lore": [...]
}
```

**Rules**

* Each step reads from `state.json`
* Each step writes new artifacts to disk
* `state.json` is updated only after successful step completion
* Failed steps do not mutate state

---

## Pipeline Configuration

The pipeline is defined declaratively in `config/pipeline.yaml`.

### Conceptual structure

```yaml
- step_id: 10_outline
  prompt: prompts/10_outline.md
  input_schema: OutlineRequest
  output: 10_outline.json
  validators:
    - json_schema
    - max_items: 14

- step_id: 20_section
  loop:
    from: 1
    to: sections
  prompt: prompts/20_section.md
  outputs:
    - section_markdown
    - section_summary
```

The orchestrator executes steps strictly in order.

---

## Run Artifacts

Each pipeline execution creates a new directory:

```
runs/<timestamp>/
  inputs.json
  state.json
  10_outline.json
  20_section_01.md
  20_section_02.md
  ...
  outputs/
    final_script.md
    editor_report.json
```

Runs are immutable once completed.

---

## v1.1 – Text-to-Speech (TTS)

### Additions

A narration stage is appended after `final_script.md` generation.

#### Narration Script Pass

**Purpose**
Prepare text explicitly for TTS.

**Transformations**

* Normalize punctuation
* Insert pauses via paragraph breaks
* Rare ellipses for major transitions
* Optional pronunciation hints via phonetic parentheses

**Output**

* `narration_script.md`

---

### TTS Generation

**Process**

* Split narration script into chunks representing **2–5 minutes of speech**
* Generate audio per chunk
* Retry-safe chunk handling

**Outputs**

* Individual WAV files per chunk
* Concatenated narration audio:

  * `run_id_story_audio.wav`
  * `run_id_story_script.txt`

---

## v1.2 – Background Music & Polish

### Background Music Layering

**Inputs**

* `narration_full.wav`
* `assets/bg-music.mp3`

**Process**

* Loop background music to narration length
* Mix at low volume beneath narration
* Apply light ducking when speech is present
* Normalize final loudness

**Output**

* `run_id_final_audio.mp3`
* `run_id_final_script.txt`

---

## Non-goals (Explicit)

The following are **out of scope** for v1.x:

* Multi-user orchestration
* Cloud execution
* Streaming generation
* Automatic embeddings / vector stores
* UI beyond CLI
* Monetization or platform integration

---

## Definition of Done (v1.0)

* CLI command produces a complete `final_script.md`
* All steps are reproducible from `inputs.json`
* No hidden state outside `runs/`
* Pipeline failures are detectable and resumable
* No manual intervention required once invoked
