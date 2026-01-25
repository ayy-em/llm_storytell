# Contributing Guidelines

This repository is designed to be worked on by **automated coding agents** under human supervision.
Follow these rules exactly. If something is unclear, do not guess. Ask for clarification or fail loudly.

The primary goal is **correctness, reproducibility, and determinism**, not cleverness.

---

## Code Style Basics

* The project uses **Python 3.12**
* Package management is done via **uv**
* Linting and formatting are enforced via **ruff**
* All code must pass linting and formatting checks before being considered complete

### Formatting and linting rules

* Do not manually format code. Run the formatter.
* Do not disable lint rules unless explicitly instructed.
* Do not introduce alternative formatters or linters.

If ruff reports an error, it must be fixed. Explanations are not fixes.

---

## Dependencies

* Every new dependency **must be justified** in:

  ```
  docs/decisions/0001-tech-stack.md
  ```
* Justification must include:

  * What problem the dependency solves
  * Why the standard library is insufficient
  * Why an existing dependency cannot be reused
* Do **not** add dependencies “for convenience”
* Do **not** add optional dependencies without explicit instruction

If a dependency is not approved, remove it.

---

## Project Structure Rules

* Do not change the directory structure unless explicitly instructed
* Do not introduce new top-level directories
* All generated artifacts must go under:

  ```
  runs/<run_id>/
  ```
* All run artifacts are to be treated as immutable once the run is finished
* All configuration must live under:

  ```
  config/
  ```
* All prompt templates must live under:

  ```
  prompts/
  ```

Hardcoded paths outside these conventions are not allowed.

---

## State and Determinism

* All pipeline state must be explicit and persisted to disk
* The orchestrator must not rely on in-memory-only state
* Given the same inputs, the pipeline must produce the same outputs (excluding timestamps)

Do not introduce hidden state, global variables, or implicit caches.

---

## Tests

### General rules

* Every new feature **must include tests**
* Bug fixes **must include a regression test**
* Tests must be runnable via a single command:

  ```bash
  make test
  ```

  or equivalent

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

## Pipeline and Prompts

* Prompt templates are **contracts**, not suggestions
* Do not change prompt output formats unless:
  * The specification has changed
  * All downstream consumers are updated
* Every prompt must clearly specify:
  * Required inputs
  * Required outputs
  * Output format (Markdown, JSON, etc.)

If a prompt output is ambiguous, fix the prompt, not the parser. Output schemas defined in src/llm-storytell/* are authoritative.

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

## Commits (if applicable)

If committing changes:

* Each commit should correspond to **one task**
* Commit messages should be descriptive and boring
* Do not bundle multiple unrelated changes into one commit

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

If any of the above is not true, the task is not done.

---

## Final Note

If you are unsure:

* Do less
* Ask questions
* Prefer explicitness over elegance

The orchestrator exists to be predictable, not impressive.