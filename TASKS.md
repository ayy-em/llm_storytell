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

## Definition of Done (v1.0)

* `python -m llm_storytell run --app grim-narrator --seed "..."`
  produces a valid final script
* Run folder contains:
  * logs
  * state
  * artifacts
* Pipeline works for different beat counts
* No grim-narrator assumptions in platform code
* ruff checks are passed
* README.md and SPEC.md are up-to-date and reflect scope, tech stack and other info truthfully.

## v1.0 Release Preparation Tasks

### [ ] R0001 Documentation cleanup for v1.0

## [ ] R0005 Prompt ↔ pipeline consistency audit (pre-v1.0)

**Goal**
Ensure full consistency between available prompt templates, pipeline expectations, code-level prompt rendering, and user-facing documentation before the v1.0 release.

**Context**
The pipeline relies on prompt templates (`00_*.md` → `30_*.md`) that must align exactly with:

* pipeline step definitions
* code-level prompt rendering and variable injection
* available app context files
* documented user expectations

Any mismatch at this stage risks silent failures, confusing errors, or undocumented constraints for end users.

**Deliverables**

* Verification that all required prompt templates for the app exist:

  * `00_seed.md`
  * `10_outline.md`
  * `20_section.md`
  * `21_summarize.md`
  * `30_critic.md`
* Verification that:

  * the pipeline references only existing prompt files
  * prompt filenames match pipeline configuration exactly
* Audit of prompt inputs:

  * inputs expected by each prompt
  * variables passed from code to prompt renderer
  * naming consistency between prompts, pipeline, and code
* Audit of context usage:

  * confirm which context `.md` files are loaded per step
  * confirm prompts reference and use provided context
  * identify unused or undocumented context inputs
* Documentation update:

  * document all prompt-related quirks, assumptions, and constraints that an end user must know
  * clarify required vs optional inputs at the pipeline and step level

**Acceptance criteria**

* Every pipeline step references an existing prompt file
* Every variable referenced in a prompt is provided by code or explicitly documented as optional
* No unused or silently ignored prompt variables remain
* Context files loaded by the pipeline are either:

  * used by prompts, or
  * explicitly documented as optional / future-facing
* README.md clearly documents:

  * required vs optional app inputs
  * prompt expectations and limitations
  * known quirks or non-obvious behaviors
* No code behavior contradicts documented behavior

**Allowed files**

* `prompts/apps/**`
* `config/pipeline.yaml`
* `src/llm-storytell/steps/**`
* `src/llm-storytell/prompt_render.py`
* `src/llm-storytell/context/**`
* `README.md`
* `SPEC.md`

**Commands to run**

* `uv run ruff format .`
* `uv run ruff check .`
* `uv run pytest -q`

**Notes**

* This task is **audit and alignment only**
* Do not add new features or pipeline stages
* Prefer fixing documentation over changing code unless a real mismatch exists
* Any discovered inconsistencies must either be:

  * resolved, or
  * explicitly documented as intentional

### [ ] R0002 Documentation cleanup for v1.0

**Goal**
Make documentation boring, accurate, and aligned with actual v1.0 behavior.

**Context**
The MVP implementation is complete. Documentation must reflect what the system actually does today, not intentions, not future plans, and not outdated assumptions from earlier design phases.

**Deliverables**

* Updated `README.md` covering:

  * Quickstart:

    * minimal project setup
    * required env vars
    * `.gitignored` inputs (apps, lore, prompts, context)
  * How to add a new app
  * Supported CLI arguments
  * Expected outputs and run lifecycle
  * High-level E2E pipeline flow
* Updated `SPEC.md` aligned with implemented behavior:

  * pipeline stages
  * state structure
  * artifact layout
  * validation and failure semantics
* Updated `CONTRIBUTING.md`:

  * current workflow rules
  * required commands
  * test and formatting expectations

**Acceptance criteria**

* All documented commands run successfully when copy-pasted
* No documentation claims features not present in v1.0
* Pipeline description matches actual execution order and artifacts
* Failure modes described match real error behavior
* MVP scope and constraints are explicit

**Allowed files**

* `README.md`
* `SPEC.md`
* `CONTRIBUTING.md`

**Commands to run**

* `uv run ruff format .`
* `uv run ruff check .`
* `uv run pytest -q`

**Notes**

* No new features
* No roadmap speculation
* Prefer deleting misleading text over inventing explanations

---

### [ ] R0003 Test coverage confidence pass

**Goal**
Ensure the critical v1.0 execution path is sufficiently tested.

**Context**
The pipeline now supports outline → section → summarize → critic stages. Tests exist, but coverage must be verified for all state mutations and failure paths.

**Deliverables**

* Identification of untested or weakly tested critical flows
* Additional unit tests where gaps exist
* No refactors unless strictly required to enable testing

**Acceptance criteria**

* Critical path stages are covered:

  * outline
  * section loop
  * summarization
  * critic / finalization
* State mutation is tested to occur only on success
* Failure cases are explicitly tested
* All tests pass without network or API keys

**Allowed files**

* `tests/**`
* Existing step files **only if strictly required for testability**

**Commands to run**

* `uv run ruff format .`
* `uv run ruff check .`
* `uv run pytest -q`

**Notes**

* Coverage percentage is secondary to correctness
* Mock LLM provider must be used
* Do not introduce new dependencies

---

## [ ] R0004 Milestone planning (v1.1 + v1.2)

**Goal**
Refine the post-v1.0 roadmap and translate it into executable tasks.

**Context**
v1.0 scope is frozen. Future milestones must be planned using the same task structure and workflow rules as MVP.

**Input**

* Current `SPEC.md`
* Current `TASKS.md`
* Finalized v1.0 scope

**Deliverables**

* Refined roadmap section for: v1.1 (including scope of v1.0.1)
* New tasks added to `TASKS.md`:

  * consistent format
  * clear acceptance criteria
  * explicit allowed files
  * ordered for execution

**Acceptance criteria**

* Series of tasks is created. Tasks are small, scoped, and executable by an agent, and cover everything from current point in time to complete release of v1.1
* No v1.0 behavior is modified

**Allowed files**

* `TASKS.md`
* `SPEC.md` (roadmap section only)

**Notes**

* Do not implement anything
* This task is planning only
* Keep milestone scope tight and explicit

---

## Roadmap (**do not start** yet unless explictly told)

* **v1.0** – Local, text-only pipeline (multi-app capable)
* **v1.0.1** - Add soft warnings when approaching context limits
* **v1.1** – Text-to-speech audiobook output
* **v1.2** – Background music mixing and audio polish
* **v1.3** – Cloud execution + scheduled delivery (Telegram / email)
* **v1.4** – One-command video generation
* **v1.4.1** – Burned-in subtitles
* **v1.5** – Vector database for large-scale context retrieval and rotation
* **v1.6** – Multi-LLM provider support, routing, and cost-aware selection
