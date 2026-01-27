# Previously Completed Tasks Log

A new section under level 3 heading and completion datetime is added to this file each time a task is completed and the info about it is removed from `TASKS.md`.

## Tasks

### [x] T0001 Runtime config + app resolution (2026-01-27)

**Goal**
Implement app discovery and validation.

**Context**
The pipeline must support multiple apps from day one, even if only one exists.

**Deliverables**

* Resolve `--app <name>` to:

  * `context/<app>/`
  * `prompts/apps/<app>/`
* Fail clearly if app does not exist
* Expose resolved paths to pipeline runtime

**Acceptance criteria**

* Running with invalid app name fails with actionable error
* Valid app is resolved without hardcoding `grim-narrator`

**Allowed files**

* `src/llm-storytell/cli.py`
* `src/llm-storytell/config/**`
* `tests/test_app_resolution.py`

*Result*: Created `config/app_resolver.py` with `AppPaths` dataclass and `resolve_app()` function. Created `cli.py` with argparse-based CLI. Added 10 unit tests covering valid/invalid app resolution. Updated `.gitignore` to track `prompts/apps/` structure while ignoring `.md` files. Added pytest to dev dependencies. All checks pass: `uv run ruff format .`, `uv run ruff check .`, `uv run pytest -q` (10 passed).

---

### [x] T0002 Run initialization + state bootstrap (2026-01-27)

**Goal**
Create and initialize a run in a deterministic, inspectable way.

**Deliverables**

* Create `runs/<run_id>/`
* Write:

  * `inputs.json`
  * `state.json`
  * `run.log`
* Log:

  * app name
  * seed
  * resolved context paths

**Acceptance criteria**

* Run folder created exactly once
* Failed runs do not leave partial state

**Allowed files**

* `src/llm-storytell/run_dir.py`
* `src/llm-storytell/logging.py`
* `tests/test_run_init.py`

*Result*: Created `run_dir.py` with `initialize_run()` function (atomic creation via temp directory + rename), `logging.py` with `RunLogger` class. Writes `inputs.json`, `state.json`, `run.log`, and `artifacts/` directory. 28 tests pass. Commands: `uv run ruff format .`, `uv run ruff check .`, `uv run pytest -q`.

---

### [x] T0003 Universal logging + token accounting (2026-01-27)

**Goal**
Implement platform-level logging and token usage tracking.

**Deliverables**

* Run-scoped logger writing to `run.log`
* Structured log events for:

  * stage start/end
  * artifact writes
  * validation failures
* Token usage tracking per LLM call:

  * provider
  * model
  * prompt tokens
  * completion tokens
* Persist token usage into `state.json`

**Acceptance criteria**

* Logs exist for every run
* No secrets logged
* Token usage visible even in mocked tests

**Allowed files**

* `src/llm-storytell/logging.py`
* `src/llm-storytell/llm/**`
* `tests/test_logging.py`

*Result*: Extended `RunLogger` in `logging.py` with methods: `log_stage_start()`, `log_stage_end()`, `log_artifact_write()`, `log_validation_failure()`, `log_token_usage()`. Created `src/llm-storytell/llm/token_tracking.py` with `TokenUsage` dataclass and `record_token_usage()` function that logs to `run.log` and returns dict for `state.json`. Created `tests/test_logging.py` with 12 tests covering all new functionality, including mocked token usage scenarios and secret protection. All tests pass (40 total). Commands run: `uv run ruff format .`, `uv run ruff check .`, `uv run pytest -q`.

---