## v1.0 release prep

**v1.0 Release Prep Goal:** Prepare the repository for v1.0.0 release by ensuring parity between code, tests, and documentation.


### Task R0001 — Release verification & parity audit

**Goal:** confirm code, tests, docs match reality.

**Agent instructions (essence):**

* Run lint + tests.
* Identify mismatches between:

  * README ↔ actual CLI behavior
  * SPEC ↔ implemented pipeline
  * CONTRIBUTING ↔ real workflow
* Do **not invent features**.
* Fix docs only where they lie.
* Output:

  * list of fixes made
  * remaining known limitations (explicit)

* Acceptance criteria: 
- ruff checks complete
- All tests pass
- All dependencies used are reflected in pyproject.toml and requirements.txt
- .gitignore is checked for sensitive data and for crucial non-content non-secret files ignored by accident 

---

### Task R0002 — Documentation cleanup for v1.0

**Goal:** make docs boring and accurate.

**Scope:**

* README.md, including sections containing:
    * Quickstart - project set up & minimal set of .gitignored files (lore, prompts, etc.) and env vars required for the thing to run
    * "How to add a new app" section
    * CLI args supported
    * Expected outputs + how the run's lifecycle is logged
    * what the moving parts of the pipeline are E2E
* SPEC.md
* CONTRIBUTING.md

**Rules:**

* No new features
* No roadmap speculation
* Clarify:

  * how to run
  * what artifacts are produced
  * failure modes
  * MVP constraints

---

### Task R0003 — Test coverage confidence pass

**Goal:** ensure critical path is tested.

**Scope:**

* Identify untested critical flows (outline → section → summarize → final)
* Add tests only where gaps exist
* No refactors unless strictly necessary

---

### Task R0004 — Milestone planning (v1.1 + v1.2)

**Goal:** turn roadmap into actionable tasks.

**Input:**

* Current SPEC.md
* Current TASKS.md
* v1.0 scope (now frozen)

**Output:**

* Refined roadmap section
* New tasks in TASKS.md:

  * same format as MVP
  * acceptance criteria
  * allowed files
  * ordered for execution
