
**THIS IS A TEMPLATE TO REUSE, DO NOT LOOK IN THIS FILE**
## v1.0 Release Preparation Tasks

## v1.0 Release Preparation Tasks

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