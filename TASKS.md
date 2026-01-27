# TASKS

* This file is the active execution queue of tasks for AI agents.
* Completed tasks must be moved to COMPLETED_TASKS.md.
* Completed tasks should not be present in this file.

The goal of **v1.0** is a **local, deterministic, multi-app-ready content generation pipeline** that can successfully run the `grim-narrator` app end-to-end and produce a final script.

---

## Global rules (apply to every task)

### Fundamental
* Read .cursor/rules/00-workflow.md
* Read TASKS.md, read global rules and select the first unchecked task
* Consult SPEC.md sections relevant to the task 

### Main workflow rules
* Do not expand scope beyond the task.
* Before implementation: propose a short solution design (5–15 bullets).
* Implementation must include unit tests (or explicit justification why not).
* All changes must pass:
  * `uv run ruff format .`
  * `uv run ruff check .`
  * `uv run pytest -q`
* New dependencies are **not allowed** unless explicitly requested by the task.
  * If added, justify in `docs/decisions/0001-tech-stack.md`.
* Touch **only** the files listed in “Allowed files”.
* Persist outputs strictly under `runs/<run_id>/...` as per `SPEC.md`.
* Do not delete tasks.
  * Mark them `[x]`
  * Append a short **Result** note (what changed + commands run)

### Post-implementation spec/doc drift detection 
* After a task is accepted, briefly evaluate whether the change introduces:
  * a new concept
  * a new constraint
  * a new required user-facing behavior
* If so, propose (do not implement) updates to:
  * README.md
  * SPEC.md
* Proposals must be bullet-pointed and minimal.
* If new third-party dependencies were added, document the decision-making process by creating a new .md file in `docs/decisions/`
* Do not modify documentation unless explicitly instructed.

### Version Control
* After completing a task, checking for spec/doc drift is peformed and all linter checks and tests pass, prepare changes for a single commit.
* The commit must include only files touched by the task.
* Commit message format: `TXXXX: <short task description>`
* Do not push unless explicitly instructed.

### End
* Stop after completing one task.

## Task format

Each task includes:

* Goal
* Context
* Deliverables
* Acceptance criteria
* Allowed files (hard constraint)
* Commands to run
* Notes (optional)

---

## v1.0 – Context & prompt handling

---

### [ ] T0011 Prompt renderer

**Goal**
Render prompt templates deterministically.

**Deliverables**

* Template renderer
* Strict missing-variable errors
* No silent fallbacks

**Acceptance criteria**

* Rendering is reproducible
* Errors point to missing inputs

**Allowed files**

* `src/llm-storytell/prompt_render.py`
* `tests/test_prompt_render.py`

*Result*:

---

## v1.0 – Pipeline stages (grim-narrator app)

### [ ] T0020 Outline stage

**Goal**
Generate outline beats (N = 1–20).

**Deliverables**

* Load app-specific outline prompt
* LLM call
* Schema validation
* Persist outline

**Acceptance criteria**

* Outline length respects CLI/app config
* Invalid output fails fast

**Allowed files**

* `src/llm-storytell/steps/outline.py`
* `prompts/apps/grim-narrator/**`
* `tests/test_outline_step.py`

*Result*:

---

### [ ] T0021 Draft loop + summarization

**Goal**
Generate sections iteratively with continuity control.

**Deliverables**

* Section generation loop
* Per-section summarization
* Rolling summary + continuity ledger
* Artifacts written per section

**Acceptance criteria**

* Works for 1–20 sections
* State updated only after successful steps

**Allowed files**

* `src/llm-storytell/steps/section.py`
* `src/llm-storytell/steps/summarize.py`
* `src/llm-storytell/continuity.py`
* `tests/test_section_loop.py`

*Result*:

---

### [ ] T0022 Critic / fixer stage

**Goal**
Consolidate and correct the full draft.

**Deliverables**

* Critic prompt
* Final script
* Editor report (schema-validated)

**Acceptance criteria**

* Final script exists
* Report is machine-readable

**Allowed files**

* `src/llm-storytell/steps/critic.py`
* `tests/test_critic_step.py`

*Result*:

---

## v1.0 – CLI & verification

### [ ] T0030 CLI integration + E2E smoke test

**Goal**
Prove the pipeline works end-to-end.

**Deliverables**

* CLI flags:

  * `--app`
  * `--seed`
  * `--beats`
  * `--run-id`
* Fully mocked E2E test

**Acceptance criteria**

* One command produces:

  * final script
  * logs
  * state
* No network or API key required for test

**Allowed files**

* `src/llm-storytell/cli.py`
* `tests/test_e2e.py`

*Result*:

---

## Post-v1.0 backlog (do not start yet)

### [ ] T0100 CI pipeline

### [ ] T0200 TTS pipeline

### [ ] T0300 Video generation

### [ ] T0400 Vector DB integration

### [ ] T0500 Multi-provider routing

---

## Definition of Done (v1.0)

* `python -m llm-storytell run --app grim-narrator --seed "..."`
  produces a valid final script
* Run folder contains:
  * logs
  * state
  * artifacts
* Pipeline works for different beat counts
* No grim-narrator assumptions in platform code
* ruff checks are passed
* README.md and SPEC.md are up-to-date and reflect scope, tech stack and other info truthfully.
