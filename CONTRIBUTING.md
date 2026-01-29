# Contributing Guidelines

This repository is designed to be worked on by **automated coding agents** under human supervision.
Follow these rules exactly. If something is unclear, do not guess. Ask for clarification or fail loudly.

The primary goal is **correctness, reproducibility, and determinism**, not cleverness.

---

## Source of truth

- `SPEC.md` is the authoritative description of pipeline behavior.
- `README.md` is the authoritative user-facing overview and usage guide.
- `TASKS.md` is the authoritative execution queue.
- `.cursor/rules/*` defines the required agent workflow for this repository.

If an implementation conflicts with `SPEC.md`, the implementation is wrong.

---

## Code Style Basics

- The project uses **Python 3.12**
- Package management is done via **uv**
- Linting and formatting are enforced via **ruff**
- Automated contributors must respect repository-level agent rules (e.g. `.cursor/rules/`).

### Formatting and linting rules

- Do not manually format code. Run the formatter.
- Do not disable lint rules unless explicitly instructed.
- Do not introduce alternative formatters or linters.

If ruff reports an error, it must be fixed. Explanations are not fixes.

---

## Dependencies

- Every new dependency **must be justified** in `docs/decisions/0001-tech-stack.md`
- Justification must include:
  - What problem the dependency solves
  - Why the standard library is insufficient
  - Why an existing dependency cannot be reused

- Do **not** add dependencies “for convenience”
- Do **not** add optional dependencies without explicit instruction

If a dependency is not approved, remove it.

---

## Project Structure Rules

- Do not change the directory structure unless explicitly instructed
- Do not introduce new top-level directories unless told to do so
- All generated artifacts must go under `runs/<run_id>/`
- All run artifacts are to be treated as immutable once the run is finished
- All configuration must live under `config/`, all API keys, secrets and tokens in `config/creds.json`
- All prompt templates must live under `prompts/`
- Hardcoded paths outside these conventions are not allowed.

---

## Schemas and contracts

- Structured outputs must validate against schemas in `src/llm_storytell/schemas/`.
- Prompts are contracts: do not change output formats unless:
  - `SPEC.md` changes, and
  - downstream consumers and tests are updated.

If a prompt output is ambiguous, fix the prompt, not the parser.

---

## State and Determinism

- All pipeline state must be explicit and persisted to disk
- The orchestrator must not rely on in-memory-only state
- Given the same inputs, the pipeline must produce the same outputs (excluding timestamps)

Do not introduce hidden state, global variables, or implicit caches.

---

### What to test

At minimum, tests should cover:

* Prompt rendering logic
* Pipeline step execution order
* State file updates
* Validation failures
* CLI argument parsing

If something can fail, there should be a test proving it fails correctly.

---

## Scope Control

When working on a task:

* Touch **only** the files required for that task
* Do not refactor unrelated code
* Do not “clean up” things unless explicitly asked
* Do not expand the feature set beyond what is specified

If you think something “should” be changed, write it down instead of changing it.

---

## Version control

### One task = one commit

* Each completed task must result in **exactly one commit**.

* The commit must include only files relevant to the task.

* Commit message format:

  ```
  TXXXX: <short task description>
  ```

* Do not push unless explicitly instructed by the repo owner.

---

## Documentation updates (proposal-first)

After a task is accepted:

* Assess whether the change introduces new concepts, constraints, or user-facing behavior.
* If yes, **propose** minimal updates to `README.md` and/or `SPEC.md`.
* Do not edit documentation unless explicitly instructed.

---

## Error Handling

* Fail fast and loudly
* Do not swallow exceptions
* Errors must include:

  * Step ID
  * File or artifact involved
  * Clear reason for failure

Silent failure is considered a bug.

---

## What Not to Do

Do **not**:

* Invent new architecture
* Add abstractions “for the future”
* Introduce asynchronous execution unless instructed
* Replace deterministic logic with probabilistic logic
* Optimize prematurely
* Anthropomorphize the pipeline

This is not a playground. It is a controlled system.

---

## Definition of “Done” for a Task

A task is considered complete only if:

* The implementation matches the specification
* All tests pass
* No new linting errors are introduced
* The change does not break existing pipeline steps
* The code can be run from a clean checkout without manual intervention
* Rules defined at repository level (e.g. `/.cursor/rules`) are respected
* The completed task is marked [x] in TASKS.md with a Result note, then moved to COMPLETED_TASKS.md.

If any of the above is not true, the task is not done.

---

## Final Note

If you are unsure:

* Do less
* Ask questions
* Prefer explicitness over elegance

The orchestrator exists to be predictable, not impressive.