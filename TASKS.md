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
* If new third-party dependencies were added, document the decision-making process by creating a new .md file in `docs/decisions/`.
* Do not modify documentation unless explicitly instructed.
* After solution for a task is approved, mark the task as [x] done in `TASKS.md`, and move the whole completed task's section to `COMPLETED_TASKS.md`.

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

## Post-v1.0 backlog (**do not start** yet)

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
