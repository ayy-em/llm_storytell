---
alwaysApply: true
---

# Cursor Agent Workflow Rules (Repo-level)

These rules apply to any automated coding agent operating in this repository.

## Required reading (before doing anything)
- Read: `TASKS.md`, `SPEC.md`, `CONTRIBUTING.md`
- Also read any task-specific files referenced by the chosen task (e.g. schemas, prompts, configs).

## Task selection
- Select the **first unchecked** task in `TASKS.md` only.
- Do not work on any other task.
- Do not “prepare” future tasks.

## Pre-flight (mandatory before editing files)
- Identify what already exists for this task (list relevant files and what is present/missing).
- Propose a solution design (5–15 bullets).
- Explicitly list:
  - Files you will change
  - Files you will not change
- Wait for approval before implementing.

## Implementation constraints
- Touch **only** the files listed under “Allowed files” for the task.
- Do not introduce new dependencies unless the task explicitly requests it.
  - If a dependency is added, update `docs/decisions/0001-tech-stack.md`.

## Verification (mandatory)
After implementation, run:
- `uv run ruff format .`
- `uv run ruff check .`
- `uv run pytest -q`

If any command fails:
- Fix the issue
- Rerun until all are green

## Task completion
- In `TASKS.md`: mark completed task [x] and add "Result" note, then remove the task from `TASKS.md`
- Append to `COMPLETED_TASKS.md`: paste the completed task (including Result note), ideally including completion date in task's header; optionally include commit hash

## Version control (per task)
- After checks are green, prepare a **single commit** for this task only.
- Commit message format: `TXXXX: <short task description>`
- Do not push unless explicitly instructed.

## Docs/SPEC drift detection
- After the task is accepted, briefly assess whether the change introduces:
  - new concepts, constraints, or user-facing behavior
- If yes: propose minimal updates to `README.md` and/or `SPEC.md`
- Do not edit documentation unless explicitly instructed.
