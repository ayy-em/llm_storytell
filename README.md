# LLM-Storytell

This README's primary target audience is AI agents. But it's also all factually true!

![LLM-Storytell - Title image](assets/hero-image.png)


`LLM-Storytell` is a **deterministic, file-driven content generation system** that produces long-form narrative stories and, in later versions, narrated audio (“mini-audiobooks”).

The system is designed to:

* Generate ~60-minute stories from a short textual seed
* Operate entirely via a local CLI
* Persist all intermediate artifacts to disk
* Avoid implicit memory, hidden state, or conversational drift
* Be extended by configuration and prompt files rather than code changes

This repository prioritizes **reproducibility and control** over creativity or interactivity.

## Note: Cursor IDE

This repository includes a `.cursor/` directory with project-level rules
used by Cursor’s Agent mode.

If you are using Cursor:
- Do not delete or modify `.cursor/rules/`
- These rules define the required task workflow, scope control, and validation steps

If you are not using Cursor:
- Treat the rules as documentation of the intended agent workflow

---

## What this is (and is not)

**This is:**

* A pipeline orchestrator for long-form story generation
* A structured sequence of LLM calls with explicit state management
* A system intended to be extended by adding prompts, lore files, and config

**This is not:**

* A chat interface
* An interactive storytelling system
* A streaming or real-time generator
* A cloud service
* A “creative writing assistant”

If you are looking for vibes, look elsewhere. This is a conveyor belt.

---

## How it works (high level)

At a high level, the pipeline does the following:

1. Accepts a **short story seed** (2–3 sentences)
2. Generates a **fixed outline** (10–14 narrative beats)
3. Iteratively expands each beat into a full section
4. Maintains continuity via explicit summaries and ledgers
5. Consolidates all sections into a final script
6. (Later versions) Converts the script into narrated audio

All intermediate outputs are written to disk and tracked in a growing `state.json` file.

Nothing is remembered unless it is written down.

---

## Pipeline stages (v1.0)

1. **Outline pass**

   * Produces 10–14 high-level narrative beats
   * Establishes structure for the entire story

2. **Draft pass (iterative)**

   * Expands each outline beat into a full section
   * Uses:

     * A rolling summary of prior sections
     * A continuity ledger (names, places, facts)
     * Static lore context
   * After each section:

     * A summarization step extracts structured updates

3. **Critic / Fixer / Editor pass**

   * Consolidates all sections
   * Detects contradictions and inconsistencies
   * Reduces overused phrasing
   * Enforces tone and narration rules
   * Outputs a single final script

See `SPEC.md` for the full technical specification.

---

## Repository structure

```
LLM-Storytell/
  README.md
  SPEC.md
  CONTRIBUTING.md
  pyproject.toml

  config/
    pipeline.yaml
    model.yaml

  prompts/
    00_seed.md
    10_outline.md
    20_section.md
    30_critic.md

  lore/
    bible.md
    snippets/

  runs/
    <timestamped runs appear here>

  src/
    orchestrator/
      runner.py
      llm_client.py
      validators.py
      ...
```

* **`prompts/`** contains all LLM prompt templates
* **`lore/`** contains universe context and canon rules
* **`runs/`** contains immutable execution artifacts
* **`src/`** contains the orchestration logic only

Generated content must never be committed.

---

## Quickstart

### Prerequisites

* Python **3.12**
* `uv` installed
* An OpenAI API key

### Setup

1. Clone the repository

   ```bash
   git clone <repo-url>
   cd LLM-Storytell
   ```

2. Install dependencies

   ```bash
   uv sync
   ```

3. Create credentials file

   Create `config/creds.json` with the following structure:

   ```json
   {
     "OPENAI_KEY": "your_api_key_here"
   }
   ```

---

## Running the pipeline

Run the pipeline via the CLI:

```bash
python -m grimnarrator run \
  --seed "A low-level worker describes a single ordinary day in a decaying future city."
```

On success, a new directory will appear under `runs/` containing:

* All intermediate artifacts
* `state.json`
* The final generated script

Example:

```
runs/2026-01-24_231045/
  inputs.json
  state.json
  10_outline.json
  20_section_01.md
  ...
  final_script.md
```

---

## Configuration

* Pipeline structure is defined in `config/pipeline.yaml`
* Model selection and parameters live in `config/model.yaml`
* Lore and universe constraints live under `lore/`

You should be able to extend or modify behavior without touching orchestration code.

---

## Development and contributions

This repository is designed primarily for **automated coding agents** working under human supervision.

Before making changes:

* Read `SPEC.md`
* Read `CONTRIBUTING.md`
* Do not infer missing requirements
* Do not expand scope unless instructed

If something is ambiguous, stop and ask.

---

## Roadmap (brief)

* **v1.0**: Text-only pipeline
* **v1.1**: Text-to-speech narration
* **v1.2**: Background music mixing and polish

No commitments beyond that.

---

## License / usage note

This project is intended for **local, personal experimentation**.
If you use copyrighted universes as inspiration, ensure you understand the implications before distributing generated content.

---

If an AI agent is reading this:
Follow the spec. Write boring code. Don’t get clever.
