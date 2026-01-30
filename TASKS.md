# TASKS

This file is the active execution queue of tasks for AI agents. The goal of **v1.0** is a **local, deterministic, multi-app-ready content generation pipeline** that can successfully run the `grim-narrator` app end-to-end and produce a final script.

## Global rules (apply to every task)

### Fundamental
* Read .cursor/rules/00-workflow.md - this is the authoritative source for workflow description
* Read TASKS.md, read global rules and select the first unchecked task
* Consult SPEC.md sections relevant to the task 
* Always activate virtual environment before running any commands or scripts

### Main workflow rules
* Do not expand scope beyond the task.
* Before implementation: propose a short solution design (5–15 bullets).
* Implementation must include unit tests (or explicit justification why not).
* All changes must pass:
  * `uv run ruff format .`
  * `uv run ruff check .`
  * `uv run pytest -q`
* New dependencies are **not allowed** unless explicitly requested by the task or approved upon request.
  * If added, justify in `docs/decisions/0001-tech-stack.md`.
* Touch **only** the files listed in “Allowed files”.
* Persist outputs strictly under `runs/<run_id>/...` as per `SPEC.md`.
* Only remove tasks from this file after completing the following:
  * Mark the completed task `[x]`
  * Append a short **Result** note (what changed + commands run)
  * Move the completed task's section to `COMPLETED_TASKS.md`

### Post-implementation spec/doc drift detection 
* After a task is accepted, briefly evaluate whether the change introduces:
  * a new concept
  * a new constraint
  * a new required user-facing behavior
* If so, propose (do not implement) bullet-pointed and concise updates to:
  * README.md
  * SPEC.md
* If new dependencies were added, document it in `docs/decisions/0001-tech-stack.md`.
* Do not modify documentation unless explicitly instructed.
* After solution for a task is approved, mark the task as [x] done in `TASKS.md`, and move the whole completed task's section to `COMPLETED_TASKS.md`.

### Version Control
* After completing a task, checking for spec/doc drift is peformed and all linter checks and tests pass, prepare changes for a single commit. 
* Propose a commit message, but do not commit or push.

### End
* Stop after completing one task.

## Task format

Each task includes:

* Goal
* Acceptance criteria
* Allowed files (Hard constraint)
* Commands to run
* Notes (Optional)
* Output requests (Optional)

Agent is to stop after reading task and request clarification if any of the non-optional items are missing.

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
* All tests pass
* README.md and SPEC.md are up-to-date and reflect scope, tech stack and other info truthfully.


## v1.0 Release Preparation Tasks

### [ ] R0001-BB-02 QA Assist: CLI argument to start at critic using a provided prompt.txt file

Task: Implement optional CLI flag `--start-at-critic <path/to/prompt_file.txt>` to run only the critic stage using a provided prompt, skipping all prior stages to save cost and speed up iteration.

Reason: You want to hammer the critic step with real API calls without regenerating outline/sections/summaries every run. Example prompt format is in the attached file.  ￼

⸻

**Goal:**
Make the pipeline support this flow:
- Run `uv run llm-storytell run ... --start-at-critic /path/to/prompt.txt`
The system then:
- Reads the file contents verbatim
- Invokes only the critic LLM call + parsing + artifact writing
- Persists the usual llm_io/critic/* artifacts
- Produces the normal critic outputs (final_script.md, editor_report.json, etc.)
- Does not run or require earlier stages

⸻

Allowed files (touch only these unless you hit a hard blocker)
1. src/llm_storytell/cli.py (add CLI flag + wiring)
2. src/llm_storytell/steps/critic.py (allow passing an override prompt string, if needed)
3. src/llm_storytell/pipeline.py (or whichever module orchestrates stages; only if required to skip stages cleanly)
4. tests/test_cli.py (or nearest existing CLI tests file)
5. tests/test_critic.py (if needed for integration-level behavior)

Explicitly NOT allowed
- Changes to any prompt templates (prompts/**)
- SPEC.md, README.md, CONTRIBUTING.md (unless acceptance criteria requires doc update; propose but don’t do here)
- Any unrelated step files
- Anything in runs/ folder
- Any “helpful” refactors

⸻

Workflow constraints (must follow)
	1.	Read first: SPEC.md, CONTRIBUTING.md, TASKS.md.
	2.	Before editing any file, include a “Proposed Changes (exact)” section with:
- exact files + functions to change
- exact CLI behavior (including edge cases)
- how outputs will be written (paths)
- how this interacts with existing run_dir/state/artifacts
	3.	Then implement exactly what you proposed (no scope creep).
	4.	Run:
- uv run ruff format .
- uv run ruff check .
- uv run pytest -q
	5.	Update TASKS.md: mark complete, add a Result summary, move to COMPLETED_TASKS.md.

⸻

Detailed requirements

A) New CLI flag + validation

Add a CLI option:
- --start-at-critic <prompt_path>
where <prompt_path> points to a text file containing the full critic prompt to send as-is.

Validation rules:
- If the file does not exist → fail with a clear error.
- If file is unreadable → fail with a clear error.
- If file contents are empty/whitespace → fail with a clear error.
- The flag is optional. Default behavior unchanged.

B) Stage skipping behavior

When --start-at-critic is provided:
- Do not run outline, section_*, summarize_*, etc.
- Run only the critic stage, using:
- rendered_prompt = file_contents (no templating, no rewriting)
- Ensure the critic stage still:
- writes the usual artifacts (final script + editor report)
- writes the llm_io/critic/* logs as per the previous task’s conventions

C) Output locations and consistency

Under the run directory, the critic step must still produce:
- runs/<run_id>/llm_io/critic/prompt.txt (should equal the file contents exactly, byte-for-byte except line endings if unavoidable)
- runs/<run_id>/llm_io/critic/response.txt (only if non-empty)
- runs/<run_id>/llm_io/critic/meta.json (always)
- runs/<run_id>/llm_io/critic/raw_response.json (best-effort)

And the normal critic outputs in artifacts/ (whatever your pipeline uses today, unchanged).

D) State + provenance (minimal, but required)

When starting at critic:
- Ensure the run state clearly indicates that earlier stages were skipped.
- Add a small provenance field somewhere already standard (state JSON, meta.json, etc.), e.g.:
- {"start_mode": "critic_from_file", "critic_prompt_path": "<path>"}

No new complex state system. Keep it tiny.

E) No hidden magic
- Do not infer or recompute inputs (seed, lore_bible, etc.).
- Do not attempt to parse the prompt file and “rebuild” a structured input object.
- The whole point is: send the exact prompt text.

⸻

Tests (required)

Add/modify tests to cover:
	1.	CLI validation
- nonexistent file path → exits non-zero with clear error
- empty file → exits non-zero with clear error
	2.	Behavior
- when --start-at-critic is set, the pipeline calls only the critic stage runner (mock/stub earlier stages and assert not called)
- critic receives prompt text matching file content
	3.	Artifacts
- llm_io/critic/prompt.txt is written and matches expected content
- run does not require outputs from previous stages

No network calls. Use deterministic fakes/mocks for the LLM provider.

⸻

Acceptance criteria (definition of done)
- --start-at-critic <path> exists and is documented in CLI --help output (auto).
- With the flag:
- earlier stages are skipped
- critic runs using file contents as prompt
- artifacts are produced normally
- llm_io/critic/prompt.txt matches the input file content
- Without the flag: pipeline behavior unchanged.
- Tests added and passing.
- uv run ruff format ., uv run ruff check ., uv run pytest -q all green.
- TASKS.md updated: task marked completed, Result section filled, moved to COMPLETED_TASKS.md.

⸻

Notes / guardrails
- Do not touch prompt templates.
- Do not create new “partial pipeline” frameworks. This is a single pragmatic switch.
- Do not store absolute paths in artifacts unless already standard (prefer storing the provided string and, if needed, also a normalized path).

⸻

Include in final output
- Bullet list of exact changes
- Paths of new/affected artifacts
- Example usage command
- Tests added

Result: … (to be filled by agent after implementation)

### [ ] R0001-BB-03 Bug Bash: E2E Production test
TASK: Fix-the-run loop (no-refactor, artifact-driven)

Goal:
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


### [ ] R0001-1 Scope increase for v1.0: modify model selection logic

Goals: 
1. Change default model for OpenAI provider prompts to "gpt-4.1-mini"
2. Add support for parsing optional CLI "--model" flag in "llm_storytell run ..." command and using that model in all calls for that run (fail immediately if provider API does not identify requested model)
3. Document the new functionality in relevant docs (README/SPEC)

Inputs: 
CLI command ``./.venv/bin/python -m llm_storytell run --app grim-narrator --model gpt-4.1.nano --seed "A story of how suffering is a grim reality at lower society levels in the future."`` (macOS version of command) 

Allowed files:
* `README.md`
* `SPEC.md`
* `CONTRIBUTING.md`
* `src/llm_storytell/cli.py`
* `src/llm_storytell/steps/*`
* `src/llm_storytell/pipeline/*`
* `src/llm_storytell/llm/*`

Acceptance criteria:
- The CLI command results in a successful run using gpt-4.1-nano model instead of default one.
- Provide the final successful run directory path.
- Provide a brief list of fixes made (bullets) and the test(s) added.
- Points where each error previously happened are now logged upon success/failure
- Marked this task as done in TASKS.md and moved the section to COMPLETED_TASKS.md
- A commit is prepared with the task's solution

### [ ] R0002 Documentation cleanup for v1.0

**Goal**
Make documentation boring, accurate, and aligned with actual v1.0 behavior.

**Context**
The MVP implementation is complete. Documentation must reflect what the system actually does today, not intentions, not future plans, and not outdated assumptions from earlier design phases.

**Deliverables**

* Review `README.md` - it should cover these items (do not change if already present and accurate):
  * Quickstart:
    * Minimal project setup using uv
    * Required env vars and/or credentials in `creds.json`
    * Minimal set of required files in .gitignore (app files, context .md files, etc)
  * Section - "How to add a new app"
  * Section - "Supported CLI arguments"
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
