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

### [x] T0021 Draft loop + summarization (2026-01-27)

**Goal**
Generate sections iteratively with continuity control.

**Deliverables**

* Section generation loop
* Per-section summarization
* Rolling summary + continuity ledger
* Artifacts written per section

**Acceptance criteria**

* Works for 1–20 sections
* State updated only after successful steps

**Allowed files**

* `src/llm-storytell/steps/section.py`
* `src/llm-storytell/steps/summarize.py`
* `src/llm-storytell/continuity.py`
* `tests/test_section_loop.py`

*Result*: Created `continuity.py` with rolling summary building and continuity ledger management (configurable token/word estimation constants). Created `section.py` with `execute_section_step()` that generates sections from outline beats, parses markdown with YAML frontmatter, validates against schema, and writes artifacts. Created `summarize.py` with `execute_summarize_step()` that takes explicit section_index, reads section artifacts directly, generates summaries, and merges continuity updates. Both steps update state atomically and only after successful completion. Created comprehensive test suite `test_section_loop.py` with 14 tests covering continuity functions, section generation, summarization, integration loop, and error handling. All checks pass: `uv run ruff format .` (4 files reformatted), `uv run ruff check .` (all checks passed), `uv run pytest -q` (139 passed).

---

### [x] T0022 Critic / fixer stage (2026-01-27)

**Goal**
Consolidate and correct the full draft.

**Deliverables**

* Critic prompt
* Final script
* Editor report (schema-validated)

**Acceptance criteria**

* Final script exists
* Report is machine-readable

**Allowed files**

* `src/llm-storytell/steps/critic.py`
* `tests/test_critic_step.py`

*Result*: Created `critic.py` with `execute_critic_step()` that loads all section artifacts deterministically, strips YAML frontmatter strictly, combines sections into full draft, calls LLM with critic prompt, and validates LLM response structure strictly (top-level object with required keys `final_script` and `editor_report`, no extra keys). Validates `editor_report` against `critic_report.schema.json`. Writes `final_script.md` and `editor_report.json` to artifacts. Updates state with normalized paths (`final_script_path` and `editor_report_path`). Fails fast on missing sections, gaps in numbering (with precise error listing missing indices), and malformed frontmatter. Created comprehensive test suite `test_critic_step.py` with 22 tests covering successful execution, section loading/combining, context loading, frontmatter stripping, error handling (missing sections, gaps, malformed frontmatter, invalid LLM responses, schema validation), and logging. All checks pass: `uv run ruff format .` (2 files reformatted), `uv run ruff check .` (all checks passed), `uv run pytest -q` (161 passed).

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

### [x] T0011 Prompt renderer (2026-01-27)

**Goal**
Render prompt templates deterministically.

**Deliverables**

* Template renderer
* Strict missing-variable errors
* No silent fallbacks

**Acceptance criteria**

* Rendering is reproducible
* Errors point to missing inputs

**Allowed files**

* `src/llm-storytell/prompt_render.py`
* `tests/test_prompt_render.py`

*Result*: Created `src/llm-storytell/prompt_render.py` with `render_prompt()` function that reads template files and renders them using Python's `str.format()`. Implemented strict variable validation that extracts all placeholders and raises `MissingVariableError` if any are missing. Created custom exception classes: `PromptRenderError` (base), `MissingVariableError`, and `TemplateNotFoundError`. All errors include actionable messages with template path and missing variable names. Handles Unicode content, format specifiers, escaped braces, and multiline templates. Created 20 comprehensive unit tests covering successful rendering, missing variables (single and multiple), file not found, format errors, placeholder extraction, and deterministic behavior. All checks pass: `uv run ruff format .`, `uv run ruff check .`, `uv run pytest -q` (109 passed total).

---

### [x] T0020 Outline stage (2026-01-27)

**Goal**
Generate outline beats (N = 1–20).

**Deliverables**

* Load app-specific outline prompt
* LLM call
* Schema validation
* Persist outline

**Acceptance criteria**

* Outline length respects CLI/app config
* Invalid output fails fast

**Allowed files**

* `src/llm-storytell/steps/outline.py`
* `prompts/apps/grim-narrator/**`
* `tests/test_outline_step.py`

*Result*: Created `src/llm-storytell/steps/outline.py` with `execute_outline_step()` function that loads context files, renders the outline prompt template, calls LLM provider, validates JSON response against schema, validates beat count matches requested count (1-20), and persists outline to artifacts and state. Added `jsonschema` dependency (>=4.0.0) to `pyproject.toml` and documented in `docs/decisions/0001-tech-stack.md`. Created `src/llm-storytell/schemas/__init__.py` with `validate_json_schema()` utility function. Created `prompts/apps/grim-narrator/10_outline.md` prompt template with placeholders for seed, lore_bible, style_rules, location_context, character_context, and beats_count. Implemented atomic writes for artifacts and state updates. Created 16 comprehensive unit tests covering successful execution, context loading, error handling (missing files, invalid JSON, schema validation failures, wrong beat count), and logging. All checks pass: `uv run ruff format .`, `uv run ruff check .`, `uv run pytest -q` (125 passed total).

---

### [ ] T0030 CLI integration + E2E smoke test

**Goal**
Prove the pipeline works end-to-end.

**Deliverables**

* CLI flags:

  * `--app`
  * `--seed`
  * `--beats`
  * `--run-id`
* Fully mocked E2E test

**Acceptance criteria**

* One command produces:

  * final script
  * logs
  * state
* No network or API key required for test

**Allowed files**

* `src/llm-storytell/cli.py`
* `tests/test_e2e.py`

*Result*: 
* All CLI flags implemented: --app, --seed, --beats, --run-id
* Fully mocked E2E test (no network/API keys required)
* Context selection is deterministic and logged
* Error handling with clear messages
* State updates only after successful steps

---

### [x] R0005 Prompt ↔ pipeline consistency audit (pre-v1.0) (2026-01-29)

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

*Result*: Updated all prompt templates (`10_outline.md`, `20_section.md`, `30_critic.md`) to match code-provided variables. Removed references to non-existent variables (`seed_intent`, `world_history`, `world_states`, `style_narration`, `style_tone`). Standardized on `style_rules` (combined from style/*.md files). Added `seed` variable to section.py and critic.py step implementations (was missing). Documented `00_seed.md` as unused/reserved for future seed normalization step. Added comprehensive "Prompt Variable Contracts" section to SPEC.md documenting per-step required vs optional variables, variable sources, naming consistency, and validation behavior. Created `tests/test_prompt_variable_contracts.py` to validate prompt templates only reference allowed variables (filters out JSON examples). Updated README.md with "Prompt Templates and Variable Contracts" section documenting strict variable validation, code-authoritative approach, and known limitations. All tests pass (169 total). Commands run: `uv run ruff format .` (32 files left unchanged), `uv run ruff check .` (all checks passed), `uv run pytest -q` (169 passed).
