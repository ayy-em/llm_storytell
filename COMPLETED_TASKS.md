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

### [x] T0004 LLM provider abstraction (OpenAI only) (2026-01-27)

**Goal**
Abstract LLM access behind a provider interface.

**Deliverables**

* `LLMProvider` interface
* OpenAI implementation only
* Retry logic
* Provider metadata returned with responses

**Acceptance criteria**

* No pipeline step imports OpenAI SDK directly
* Provider can be swapped without changing step code

**Allowed files**

* `src/llm-storytell/llm/**`
* `tests/test_llm_provider.py`

*Result*: Implemented `LLMResult`, `LLMProvider` base class, and `OpenAIProvider` in `src/llm-storytell/llm/__init__.py` with retry logic and provider/model/token metadata in `LLMResult`. Added `tests/test_llm_provider.py` covering the interface, OpenAI happy-path behaviour, retry handling, and token usage extraction (including derived totals and missing usage). All checks pass: `uv run ruff format .`, `uv run ruff check .`, `uv run pytest -q`.

---

### [x] T0005 Pipeline definition loader (2026-01-27)

**Goal**
Load and validate `config/pipeline.yaml`.

**Deliverables**

* YAML parser
* Required field validation
* Step ordering preserved

**Acceptance criteria**

* Invalid pipeline configs fail early
* Parsed structure usable by orchestrator

**Allowed files**

* `src/llm-storytell/pipeline/**`
* `tests/test_pipeline_loader.py`

*Result*: Created `src/llm-storytell/pipeline/loader.py` with comprehensive YAML parsing and validation. Implemented data models (PipelineConfig, PipelineStep, LLMConfig, LoopConfig, OutputConfig, etc.) using dataclasses matching the approved YAML structure. Added PyYAML dependency to `pyproject.toml` and documented in `docs/decisions/0001-tech-stack.md`. Created 22 unit tests covering valid configs, error cases, step ordering, loops, multiple outputs, and validation. All checks pass: `uv run ruff format .`, `uv run ruff check .`, `uv run pytest -q` (70 passed total).

---

### [x] T0010 Context loader (app-aware, randomized) (2026-01-27)

**Goal**
Load and select context files for a run.

**Deliverables**

* Always load:

  * lore bible
  * style rules
* Randomly select:

  * 1 location
  * 2–3 characters
* Persist selections to state
* Log selections

**Acceptance criteria**

* Context selection varies across runs
* Same run artifacts always reflect same selection

**Allowed files**

* `src/llm-storytell/context/**`
* `tests/test_context_loader.py`

*Result*: Created `src/llm-storytell/context/loader.py` with `ContextLoader` class and `ContextSelection` dataclass. Implemented always-loaded files (lore_bible.md, style/*.md), randomized selection of 1 location and 2-3 characters using run_id as deterministic seed. Added `log_context_selection()` method to `RunLogger`. Paths normalized to forward slashes for cross-platform compatibility. Handles missing directories gracefully, warns but doesn't fail if fewer than 2 characters available. Created 19 comprehensive unit tests covering all scenarios including minimal apps, large context libraries, reproducibility, and Unicode content. All checks pass: `uv run ruff format .`, `uv run ruff check .`, `uv run pytest -q` (89 passed total).

---

