# TASKS

This file is the execution queue for automated coding agents.

## Global rules (apply to every task)
- Do not expand scope beyond the task.
- Before implementation: propose a short solution design (5–15 bullets).
- Implementation must include unit tests (or explicit justification why not).
- All changes must pass:
  - `uv run ruff check .`
  - `uv run ruff format .`
  - `uv run pytest -q`
- New dependencies are not allowed unless explicitly requested by the task.
  - If added, justify in `docs/decisions/0001-tech-stack.md`.
- Touch only the files listed in “Allowed files”.
- Persist outputs strictly under `runs/<run_id>/...` as per `SPEC.md`.
- Do not delete tasks. Mark them complete (`[x]`) and append a short Result note.

---

## Task format

Each task includes:
- Goal
- Context
- Deliverables
- Acceptance criteria
- Allowed files (hard constraint)
- Commands to run
- Notes (optional)

---

## Backlog

### [ ] T001 Repo bootstrap and tooling
**Goal**
Create the minimal runnable Python project with linting/testing wired.

**Context**
The orchestrator and pipeline code will be added in later tasks.

**Deliverables**
- `pyproject.toml` configured for Python 3.12, ruff, pytest
- `src/llm-storytell/__init__.py` and minimal package structure
- `Makefile` (or `scripts/`) with:
  - `make test`
  - `make lint`
  - `make fmt`
- A placeholder smoke test (`tests/test_smoke.py`) that imports the package

**Acceptance criteria**
- `uv sync` works on a clean clone
- `make test`, `make lint`, `make fmt` all succeed

**Allowed files**
- `pyproject.toml`
- `Makefile` (or `scripts/*`)
- `src/llm-storytell/**`
- `tests/**`

**Commands**
- `uv sync`
- `make fmt && make lint && make test`

_Result_: (fill when complete)

---

### [ ] T002 Config + credentials loader
**Goal**
Implement config loading and credential reading from `config/creds.json`.

**Deliverables**
- A function to load creds and return the OpenAI key
- Clear error messages when missing/invalid
- Tests for:
  - valid creds file
  - missing file
  - missing OPENAI_KEY

**Acceptance criteria**
- Tests cover happy path + failure modes
- No secrets logged

**Allowed files**
- `src/llm-storytell/config/**`
- `tests/test_config.py`
- `config/creds.json` should NOT be committed

**Commands**
- `make test`

_Result_: 

---

### [ ] T003 OpenAI client wrapper
**Goal**
Create a minimal OpenAI API wrapper used by pipeline steps.

**Deliverables**
- `LLMClient` with a single method, e.g. `generate(prompt: str) -> str`
- Request/response logging into the active run directory (redacting secrets)
- Retry behavior (simple: N retries with backoff)
- Tests that mock network calls (no live API calls in tests)

**Acceptance criteria**
- Can call `LLMClient.generate()` from a smoke script
- Tests do not require network or API key

**Allowed files**
- `src/llm-storytell/llm_client.py`
- `src/llm-storytell/logging.py` (if needed)
- `tests/test_llm_client.py`

**Commands**
- `make test`

_Result_:

---

### [ ] T004 Run directory + artifact IO
**Goal**
Create run folder structure and helpers for writing artifacts.

**Deliverables**
- Utility to create `runs/<run_id>/` folder using timestamp default
- Write `inputs.json` and initialize `state.json`
- Helper functions for:
  - write text file
  - write json file
  - read json file

**Acceptance criteria**
- Given a seed string, creates a run directory with expected files
- Unit tests cover paths and file contents

**Allowed files**
- `src/llm-storytell/io.py`
- `src/llm-storytell/run_dir.py`
- `tests/test_run_dir.py`

_Result_:

---

### [ ] T005 Prompt renderer
**Goal**
Render prompt templates with placeholders from state.

**Deliverables**
- Template rendering (simple and deterministic)
- Strict error on missing placeholders
- Tests for:
  - correct rendering
  - missing variable failure

**Acceptance criteria**
- Renderer produces stable output
- Errors are clear and actionable

**Allowed files**
- `src/llm-storytell/prompt_render.py`
- `tests/test_prompt_render.py`

_Result_:

---

### [ ] T006 Pipeline YAML parser + step runner skeleton
**Goal**
Parse `config/pipeline.yaml` and execute steps in order (no LLM yet).

**Deliverables**
- Load pipeline YAML
- Validate required keys (step_id, prompt, outputs, etc.)
- Skeleton runner that iterates steps and writes placeholder artifacts

**Acceptance criteria**
- Running `python -m llm-storytell run --seed "..."` creates run dir + state + placeholder artifacts
- Unit tests for parser validation

**Allowed files**
- `src/llm-storytell/pipeline/**`
- `tests/test_pipeline_parser.py`

_Result_:

---

### [ ] T007 Implement Stage 1: Outline step
**Goal**
Implement outline pass per `SPEC.md`.

**Deliverables**
- Prompt template `prompts/10_outline.md`
- Runner integrates LLM call
- Output JSON saved as `10_outline.json`
- Schema validation (10–14 items)
- Tests with mocked LLM output

**Acceptance criteria**
- Outline stored in `state.json`
- Validation fails correctly on malformed output

**Allowed files**
- `prompts/10_outline.md`
- `src/llm-storytell/steps/outline.py`
- `tests/test_outline_step.py`

_Result_:

---

### [ ] T008 Implement Draft loop: Section generation + summarizer
**Goal**
Implement iterative section generation and summarization per `SPEC.md`.

**Deliverables**
- `prompts/20_section.md`
- `prompts/21_summarize_section.md`
- Loop runner for N sections
- Rolling summary builder + continuity ledger merge logic
- Artifacts per section written to disk
- Tests covering:
  - summary stitching respects token caps
  - continuity ledger merge rules
  - loop produces expected number of artifacts

**Acceptance criteria**
- Generates `20_section_01.md` .. `20_section_NN.md`
- Updates `state.json` correctly after each section
- Failures do not partially corrupt state

**Allowed files**
- `prompts/20_section.md`
- `prompts/21_summarize_section.md`
- `src/llm-storytell/steps/section.py`
- `src/llm-storytell/steps/summarize.py`
- `src/llm-storytell/continuity.py`
- `tests/test_section_loop.py`

_Result_:

---

### [ ] T009 Implement Critic/Fixer consolidation pass
**Goal**
Consolidate all sections and produce `final_script.md` and `editor_report.json`.

**Deliverables**
- `prompts/30_critic.md`
- Consolidation logic
- Report schema and validation
- Tests with mocked critic output

**Acceptance criteria**
- `final_script.md` exists and contains all sections in order
- `editor_report.json` exists and is machine-readable

**Allowed files**
- `prompts/30_critic.md`
- `src/llm-storytell/steps/critic.py`
- `tests/test_critic_step.py`

_Result_:

---

### [ ] T010 CLI polish + end-to-end smoke test
**Goal**
Finalize CLI and add an end-to-end run test using fully mocked LLM.

**Deliverables**
- CLI flags (`--sections`, `--run-id`, `--config-path`)
- End-to-end test that executes the CLI with mocked LLM and asserts artifacts

**Acceptance criteria**
- One command produces a complete run with `final_script.md`
- Test runs without network or API key

**Allowed files**
- `src/llm-storytell/cli.py`
- `tests/test_e2e.py`

_Result_:
