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
* Always activate virtual environment before running any 

### Main workflow rules
* Do not expand scope beyond the task.
* Before implementation: propose a short solution design (5–15 bullets).
* Implementation must include unit tests (or explicit justification why not).
* Always make sure to activate the virtual environment before running any command or file
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

* Running the command (based on current OS) produces a valid final script:
  * Windows: `.\.venv\Scripts\python.exe -m llm_storytell run --app grim-narrator --seed "A story of how suffering is a grim reality at lower society levels in the future."`
  * macOS: ``./.venv/bin/python -m llm_storytell run --app grim-narrator --seed "A story of how suffering is a grim reality at lower society levels in the future."``
* Run folder contains:
  * logs
  * state
  * artifacts
* Pipeline works for different beat counts
* No grim-narrator assumptions in platform code
* ruff checks are passed
* README.md and SPEC.md are up-to-date and reflect scope, tech stack and other info truthfully.


## v1.0 Release Preparation Tasks

### [ ] R0001-BB Bug Bash: E2E Production test
TASK: Fix-the-run loop (no-refactor, artifact-driven)

Goal
Given ONE exact CLI command, repeatedly execute it until it succeeds.
On each failure:
- Read console output.
- Inspect the NEWLY CREATED run artifacts in runs/<latest>/ (run.log, inputs.json, state.json, any schema/validation outputs).
- Diagnose root cause.
- Apply the smallest targeted fix to make the next run pass.
- Repeat.

CRITICAL RULES (non-negotiable)
1) Use the CLI command EXACTLY as provided. Do not change flags/args unless the command itself is invalid.
2) DO NOT edit anything inside any existing runs/run-*/ directory. Runs are immutable evidence.
3) DO NOT refactor unrelated code. No renames, no reorganizing modules, no “cleanup”.
4) One iteration = one minimal fix + tests + rerun.
5) If a fix touches more than ~3 files or >150 LOC, it’s probably scope creep. Stop and find a smaller fix.
6) Only fix what is necessary to get THIS command to succeed. No speculative improvements.
7) Preserve backward compatibility unless the failure explicitly requires breaking change (rare).
8) After each failure, summarize:
   - Failure stage
   - Exact error message
   - Evidence from run.log/state.json
   - Proposed minimal fix
   - Why this fix is minimal

Inputs
CLI command to run (copy/paste exactly, based on current OS):
  * Windows: `.\.venv\Scripts\python.exe -m llm_storytell run --app grim-narrator --seed "A story of how suffering is a grim reality at lower society levels in the future."`
  * macOS: ``./.venv/bin/python -m llm_storytell run --app grim-narrator --seed "A story of how suffering is a grim reality at lower society levels in the future."``

**Iteration protocol** (repeat until success)
Step 0: Preconditions
- Confirm .venv is active (or use uv run if repo uses uv).
- Run formatting/lint/tests only when code changes.

Step 1: Execute
- Run the CLI command.
- If it succeeds: STOP. Report success and the run dir path.

Step 2: Gather evidence (failure only)
- Capture console output (full error).
- Identify the run directory created (most recent runs/run-*/ by timestamp).
- Read:
  - runs/<latest>/run.log
  - runs/<latest>/state.json
  - runs/<latest>/inputs.json
  - any additional emitted validation artifacts (schemas, reports)
- Do NOT modify anything in `runs/` folder.

Step 3: Diagnose (failure only)
- State the failing stage (e.g., schema validation / outline / section / critic).
- Extract the minimal root cause (missing var, invalid schema, bad placeholder parsing, bad context selection, etc).
- Identify the exact code location likely responsible (file + function) with reasoning tied to evidence.

Step 4: Minimal fix plan (failure only)
- Propose the smallest change that could plausibly fix the error.
- Prefer: adjust a single validation rule / pass a missing variable / correct a schema / escape braces in a prompt.
- Avoid: architecture changes, new modules, big rewrites.

Step 5: Implement minimal fix
- Edit only necessary files.
- Add/adjust the smallest test that would have caught this failure (if practical).
- Run:
  - uv run ruff format .
  - uv run ruff check .
  - uv run pytest -q
  (or repo’s equivalent)
- If tests fail: fix tests/code, keep changes minimal.

Step 6: Rerun
- Re-run the exact CLI command.
- Loop back to Step 2 on failure.

Guardrails against infinite loops / repo wreckage
- Maintain a running “Change Log” with:
  - Iteration number
  - Files touched
  - Why touched
  - How it relates to the observed failure
- If the same failure repeats twice:
  - Add one targeted debug log OR one targeted assertion (not both) to pinpoint the missing invariant.
  - Rerun.
- If a fix requires major refactor, STOP and propose a separate refactor task instead.

Acceptance criteria:
- The CLI run succeeds.
- Provide the final successful run directory path.
- Provide a brief list of fixes made (bullets) and the test(s) added.
- Points where each error previously happened are now logged upon success/failure
- Update TASKS.md for the active task only (mark complete when success achieved).
- One commit for the task (if your workflow requires it).


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
