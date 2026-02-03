# Previously Completed Tasks Log

A new section under level 3 heading and completion datetime is added to this file each time a task is completed and the info about it is removed from `TASKS.md`.

## Post-v1.2

### [x] T0131 – Update docs after changes (README/SPEC/TASKS) (2026-02-03)

**Goal**
Bring docs in sync after the bug fixes, refactor, and cleanup changes land.

**Acceptance criteria**
- README.md and SPEC.md reflect the final pipeline structure and behavior.
- TASKS.md is updated to remove completed tasks and record results.
- No doc drift remains for CLI flags, run layout, or pipeline steps.
- Docs should claim v1.2 is the current version and a release that's already happened

**Allowed files**
- README.md
- SPEC.md
- TASKS.md

**Commands to run**
- `uv run ruff format .`
- `uv run ruff check .`
- `uv run pytest -q`

**Result**
SPEC.md: Pipeline Configuration now states step order is implemented in the pipeline runner (`pipeline/runner.py`), invoked from cli.py. Added "TTS usage and cost (v1.2)" under Logging (per-segment input_characters in state, run completion summary and estimated cost in run.log/CLI). state.json section notes that tts_token_usage entries include input_characters. Roadmap v1.2 marked "(released)". README.md: Added sentence that run completion shows combined Chat + TTS usage and estimated cost in CLI and run.log; roadmap v1.2 marked "(released)". TASKS.md: T0131 marked [x], Result added, task section moved to COMPLETED_TASKS.md. Commands run: `uv run ruff format .`, `uv run ruff check .`, `uv run pytest -q`.

---

### [x] T0130 – Tokens for TTS are not counted/logged (2026-02-03)

**Goal**
Fix the bug: token usage count maintained in run.log file does not include the amount of tokens spent on TTS calls, and the associated costs.

**How to do it**
Whenever a call to OpenAI's TTS API is made, the pipeline needs to record the number of characters sent in the prompt. That number is then recorded in run logs and output to CLI, along with the estimated cost of the request. The cost is calculated based on tts-provider and tts-model used, as per a static JSON mapping.

**Cost calculation base**
For OpenAI provider, cost for each model is:
- tts-1: $15,00 per 1000000 characters
- tts-1-hd: $30,00 per 1000000 characters
- gpt-4o-mini-tts: $15,50 per 1000000 characters

**Acceptance criteria**
- Each TTS provider call gets its character count logged in run.log 
- Each TTS provider call results in CLI print statement noting the total amount of billed characters, along with a cumulative total for TTS
- Upon run completion, the run.log & CLI outputs give a total cost estimate split by service, e.g. "Chat Tokens: 56008 input, 14896 output, 70904 total. TTS: 1090123 characters requested", then on new line "Estimated cost: $0,219 Chat + $16,35 TTS = $16,569 total".

**Allowed files**
- ...

**Commands to run**
- `uv run ruff format .`
- `uv run ruff check .`
- `uv run pytest -q`

**Result**
Added TTS character tracking and cost: `llm/pricing.py` — `TTS_COST_PER_1M_CHARS` (tts-1, tts-1-hd, gpt-4o-mini-tts) and `estimate_tts_cost(tts_usage)`; `logging.py` — `log_tts_character_usage()`; `steps/llm_tts.py` — record `input_characters` per segment, log each call, print per-segment "[llm_storytell] TTS segment N: X characters (cumulative: Y)"; `pipeline/runner.py` — load `tts_token_usage`, print and log combined "Chat Tokens: ... TTS: ... characters requested" and "Estimated cost: $X Chat + $Y TTS = $Z total". State `tts_token_usage` entries now include `input_characters`. Tests: `test_llm_pricing.py` (estimate_tts_cost), `test_logging.py` (log_tts_character_usage), `test_llm_tts_step.py` (input_characters in state, TTS character line in run.log; test_artifacts_created_and_state_updated updated for multi-segment chunking). Commands run: `uv run ruff format .`, `uv run ruff check .`, `uv run pytest -q` (321 passed for T0130-related; 4 pre-existing failures: test_audio_prep_step volume envelope, test_llm_tts_step chunk constant tests).

---

### [x] T0129 – Test coverage review + real E2E runs (2026-02-01)

**Goal**
Assess test coverage for edge cases and run real (non-test) E2E executions to validate the full pipeline.

**Acceptance criteria**
- Documented list of missing edge-case coverage and added tests for critical gaps.
- At least one real CLI run completes successfully end-to-end (no test mocks), with artifacts in `runs/<run_id>/`.
- E2E run results recorded in task Result notes (command + run_id + outcome).

**Notes**
- Review existing code base, test coverage, code consistencies and prepare assessment, do not introduce changes and do not run the pipeline.
- When ready, share results and suggest user manually runs the CLI command.
- If command fails, iterate with changes till issue is fixed and prompt user to rerun the command

**Allowed files**
- src/llm_storytell/**
- tests/**
- TASKS.md

**Commands to run**
- `uv run ruff format .`
- `uv run ruff check .`
- `uv run pytest -q`

**Result**
Assessment documented missing edge-case coverage (run-id collision, llm_io layout, max 20 beats, real E2E). Added tests: `test_e2e_fails_when_run_id_already_exists`; llm_io layout assertions in `test_e2e_full_pipeline` (outline, section_00–02, summarize_00–02, critic have prompt.txt, meta.json, non-empty response.txt); `test_e2e_full_pipeline_twenty_beats` (pipeline with 20 beats); `test_e2e_with_tts_succeeds` (pipeline succeeds with --tts using mocked LLM, MockTTSProvider, and mocked ffmpeg/ffprobe). Pipeline now covered for both --no-tts and --tts modes. Added `MockTTSProvider`, `TTSResult`/`TTSProvider` imports; `temp_app_structure` fixture now includes `assets/default-bg-music.wav` for TTS E2E. Commands run: `uv run ruff format .`, `uv run ruff check .`, `uv run pytest -q` (316 passed). Real E2E: user to run e.g. `python -m llm_storytell run --app example_app --seed "A short test." --beats 2 --no-tts` (and optionally with `--tts` if API/ffmpeg available) and record command + run_id + outcome in notes.

---

## v1.0 to v1.2

### [x] T0128 – Codebase cleanup: remove unused code, resolve inconsistencies, de-duplicate logic (2026-02-01)

**Goal**
Review the codebase for unused code paths/files and eliminate inconsistencies and duplicate logic, especially in state IO and pipeline steps.

**Acceptance criteria**
- Remove or consolidate unused modules/functions; no orphaned code remains.
- Duplicate logic (e.g., repeated state/inputs loading and atomic writes) is centralized.
- Inconsistent behaviors across steps are resolved and covered by tests.
- No change in external behavior unless documented in SPEC.

**Allowed files**
- src/llm_storytell/**
- tests/**

**Commands to run**
- `uv run ruff format .`
- `uv run ruff check .`
- `uv run pytest -q`

**Result**
Centralized run-dir IO in `pipeline/state.py`: added `StateIOError`, `load_state(run_dir)`, `load_inputs(run_dir)`, and `update_state_atomic(run_dir, updater)`. Refactored `update_state_selected_context` to use `update_state_atomic`. Steps (outline, section, critic, summarize, llm_tts, audio_prep) now use these helpers via lazy imports to avoid circular import; each step re-raises `StateIOError` as its step-specific error. Removed duplicate `_load_state`, `_load_inputs`, and `_update_state` from steps. Runner uses `load_state(run_dir)` for outline-beats and token/cost summary. New tests in `tests/test_pipeline_state.py` for load_state, load_inputs, update_state_atomic, and StateIOError. Updated tests: test_audio_prep_step (message match), test_outline_step (inputs missing message), test_pipeline_state (inputs missing message). Commands run: `uv run ruff format .`, `uv run ruff check .`, `uv run pytest -q` (313 passed).

---

### [x] T0127 – Refactor pipeline structure (runner + providers + state IO) (2026-02-01)

**Goal**
Move orchestration and provider creation out of `cli.py` into the proposed pipeline modules, keeping behavior identical.

**Acceptance criteria**
- New pipeline modules exist in pipeline/ directory (`pipeline/runner.py`, `pipeline/resolve.py`, `pipeline/providers.py`, `pipeline/context.py`, `pipeline/state.py` and others, if necessary).
- Each pipeline component is single-purpose and both app- and llm provider-agnostic
- All flags, arguments and other data passed along with the CLI command are sent to the pipeline components
- `cli.py` only parses args, resolves run settings, and calls the pipeline runner.
- Pipeline steps continue to execute in the same order with identical outputs and logging.
- All unit tests and E2E tests pass without changes to CLI behavior.

**Allowed files**
- src/llm_storytell/cli.py
- src/llm_storytell/pipeline/**
- src/llm_storytell/run_dir.py
- src/llm_storytell/logging.py
- src/llm_storytell/config/**
- tests/**
- You are allowed to create new files during this task

**Commands to run**
- `uv run ruff format .`
- `uv run ruff check .`
- `uv run pytest -q`

**Result**
New pipeline modules: `pipeline/state.py` (update_state_selected_context), `pipeline/providers.py` (create_llm_provider, create_tts_provider; raise ProviderError, no sys.exit), `pipeline/resolve.py` (RunSettings, resolve_run_settings, _section_length_midpoint), `pipeline/context.py` (load_and_persist_context), `pipeline/runner.py` (run_pipeline(settings)). cli.py slimmed to create_parser, resolve_app_or_exit, main (parse → validate → resolve app/config → resolve_run_settings → run_pipeline). pipeline/__init__.py exports RunSettings, resolve_run_settings, run_pipeline, update_state_selected_context. Tests: test_cli.py patches llm_storytell.cli.run_pipeline and asserts on settings; test_cli_word_count imports _section_length_midpoint from pipeline.resolve; test_e2e.py patches llm_storytell.pipeline.runner.create_llm_provider; test_pipeline_resolve.py added for resolve_run_settings. Commands run: uv run ruff format ., uv run ruff check ., uv run pytest -q (304 passed).

---

### [x] T0126 – Fix pipeline/CLI bugs (model defaults, context warning, atomic state, beats consistency) (2026-02-01)

**Goal**
Resolve known pipeline/CLI bugs and align contracts across run init, prompt usage, and runtime behavior.

**Acceptance criteria**
- When CLI flags are absent, defaults resolve in this order: CLI → app_config defaults for `model`, `llm_provider`, `tts_provider`.
- Context-size warning uses the resolved model (pass model into ContextLoader.load_context).
- `_update_state_selected_context` uses atomic write (temp file + rename) and never leaves partial `state.json`.
- `initialize_run`/inputs/outline/runner agree on beats being a required int (or consistently optional); no None leaks through.
- Existing tests updated or added to cover the fixed paths.

**Allowed files**
- src/llm_storytell/cli.py
- src/llm_storytell/run_dir.py
- src/llm_storytell/context/loader.py
- src/llm_storytell/steps/outline.py
- src/llm_storytell/config/app_config.py
- tests/**

**Result**
Model default: CLI now uses `app_config.model` when `--model` is omitted (CLI → app_config). Context-size warning: `loader.load_context(run_dir.name, model=model)` so the same resolved model used for the LLM provider is passed for the warning threshold. `_update_state_selected_context`: atomic write via temp file in run_dir + rename; no partial state.json. Beats: `initialize_run(..., beats: int)` and `_create_inputs_json(..., beats: int)`; CLI already sets `beats = app_config.beats` when None so beats is always int. Tests: default model from app_config (test_e2e_model_default_from_app_config_when_no_model_flag), atomic state (test_update_state_selected_context_atomic_write), beats required and stored as int (test_beats_required_and_stored_as_int, test_beats_required_raises_when_omitted); all `initialize_run` call sites updated to pass `beats`. Commands run: uv run ruff format ., uv run ruff check ., uv run pytest -q (294 passed).

---

### [x] T0125 – Documentation updates for audio pipeline (2026-02-01)

**Goal**
Bring documentation in sync with reality, introduce consistency between core docs in this repo, and ensure current code base reflects what documentation promises.

**Acceptance criteria**
- README.md documents: --tts / --no-tts, provider/voice overrides, ffmpeg requirement, where narration output lives
- SPEC.md fully reflects the current code: new pipeline steps, artifact layout (tts/, voiceover/, final narration), failure + warning behavior
- 0001-tech-stack.md mentions all third party tools/extensions/sdks/packages used
- TASKS.md has no outstanding tasks in v1.0, v1.1 and v1.2 scope + roadmap & previous releases updated to reflect v1.2 being the current version
- Whenever "current version" is mentioned in the docs, it references v1.2

**Allowed files**
- README.md, SPEC.md, CONTRIBUTING.md, TASKS.md, docs/decisions/0001-tech-stack.md, prompts/README.md

**Result**
README.md: added ffmpeg to Prerequisites; documented intended run layout when TTS enabled (tts/, voiceover/, artifacts/narration-<app>.<ext>); clarified --tts/--no-tts and provider/voice overrides in CLI table; repository structure and roadmap updated (v1.2 current). SPEC.md: pipeline configuration now lists TTS step and audio-prep step when TTS enabled; Run Artifacts extended with tts/, voiceover/, narration-<app>.<ext>; state.json doc includes tts_config, tts_token_usage, final_script_path, editor_report_path; failure semantics added for TTS (LLMTTSStepError) and audio-prep (AudioPrepStepError, ffmpeg required); ffmpeg note in TTS paragraph; roadmap v1.2 current. docs/decisions/0001-tech-stack.md: added openai package (LLM + TTS) and ffmpeg (external binary for audio-prep). TASKS.md: T0125 removed; Previous Releases updated with v1.1, v1.2 (current); no outstanding v1.0/v1.1/v1.2 tasks. Commands run: uv run ruff format ., uv run ruff check ., uv run pytest -q.

---

### [x] T0124 – Implement audio-prep step (stitching + background music) (2026-01-31)

**Goal**
Produce a single narrated audio file with background music and volume automation.

**Inputs**
0 < N ≤ 22 audio segments from llm-tts.

**Acceptance criteria**
- Steps:
  1. Stitch segments into one voiceover track.
  2. Calculate voiceover duration.
  3. Load background music: apps/<app_name>/assets/bg-music.* if exists, else assets/default-bg-music.wav.
  4. Loop bg music with 2s crossfade to duration + 6s.
  5. Apply bg volume envelope: 0–1.5s 75%, 1.5–3s fade to 10%, 10% during narration, after narration fade to 70% over 2s.
  6. Mix voiceover + bg music.
- Output: stitched voiceover to runs/<run_id>/voiceover/; final to runs/<run_id>/artifacts/narration-<app_name>.<ext>.
- Implementation uses ffmpeg via subprocess (PATH assumed).
- Tests mock subprocess and verify command construction and timing.

**Allowed files**
- src/llm_storytell/steps/audio_prep.py
- src/llm_storytell/utils/** (if strictly necessary)
- tests/test_audio_prep_step.py

**Result**
Implemented src/llm_storytell/steps/audio_prep.py: execute_audio_prep_step(run_dir, base_dir, logger, app_name=None); segment discovery from tts/outputs (1–22 segments, extension from first file); stitch via ffmpeg concat; ffprobe duration; bg resolution (apps/<app>/assets/bg-music.* else assets/default-bg-music.wav); loop with 2s crossfade (or simple loop when bg ≤2s); volume envelope (0.75→0.1→0.1→0.7); mix to artifacts/narration-<app>.<ext>. Tests in test_audio_prep_step.py: _get_app_name, _discover_segments, _resolve_bg_music, execute_audio_prep_step with mocked subprocess (stitch/amix commands, envelope expression, output paths, ffprobe/ffmpeg failure). Commands run: uv run ruff format ., uv run ruff check ., uv run pytest -q (291 passed).

---

### [x] T0123 – Implement llm-tts pipeline step (chunking + synthesis) (2026-01-31)

**Goal**
Add a pipeline step that converts the final story text into multiple narrated audio segments.

**Input**
Final story artifact (.md, plain text).

**Acceptance criteria**
* Chunking logic: target range 700–1000 words; cut at first newline after 700 words; if none found by 1000, succeed and log warning; enforce 1 ≤ segments ≤ 22.
* Artifacts: runs/<run_id>/tts/prompts/segment_XX.txt, runs/<run_id>/tts/outputs/segment_XX.<audio_ext>; segments sent sequentially to provider.
* Logging: segment progress, warnings on imperfect splits, cumulative token usage (response_prompt_tokens, response_completion_tokens, tts_prompt_tokens, total_text_tokens, total_tts_tokens, total_tokens); state JSON records text vs TTS token usage separately (tts_token_usage[]).
* Tests: chunking edge cases, warning path, max segment enforcement, artifact creation.

**Allowed files**
* src/llm_storytell/steps/llm_tts.py
* src/llm_storytell/pipeline/**
* src/llm_storytell/logging.py
* tests/test_llm_tts_step.py

**Result**
Implemented src/llm_storytell/steps/llm_tts.py: _chunk_text (700–1000 words, cut at first newline after 700; if no newline by 1000 cut at 1000 and set imperfect; merge to ≤22 segments), _load_final_script (from state.final_script_path or artifacts/final_script.md), execute_llm_tts_step (chunk, write tts/prompts/segment_NN.txt, call TTS per segment, write tts/outputs/segment_NN.<ext>, append tts_token_usage to state, log progress and log_tts_cumulative). Added RunLogger.log_tts_cumulative in logging.py. Tests in test_llm_tts_step.py: _chunk_text (empty, short, under 700, newline cuts, no newline by 1000, >22 merged, 22 allowed), execute_llm_tts_step (missing script raises, artifacts and state updated, uses state final_script_path, TTS error raises, warning on imperfect, cumulative in log). Backlog task added to TASKS.md for stderr-on-failure (do not start). Commands run: uv run ruff format ., uv run ruff check ., uv run pytest -q (271 passed).

---

### [x] T0122 – Add TTS provider abstraction + OpenAI implementation (2026-01-31)

**Goal**
Introduce a provider-based TTS client system, starting with OpenAI.

**Acceptance criteria**
* New folder: src/llm_storytell/tts_providers/
* openai_tts.py implements: text → audio synthesis; accepts model, voice, and tts-arguments; returns audio bytes + token usage metadata (best-effort).
* No pipeline step imports provider SDKs directly.
* Provider interface is minimal and explicit.
* Tests mock OpenAI calls and verify: correct parameter passing, error propagation, token usage extraction.

**Allowed files**
* src/llm_storytell/tts_providers/**
* src/llm_storytell/config/**
* tests/test_openai_tts.py

**Result**
Added src/llm_storytell/tts_providers/ with __init__.py (TTSResult, TTSProviderError, TTSProvider ABC) and openai_tts.py (OpenAITTSProvider with injectable client callable; synthesize returns TTSResult with audio bytes and optional usage; supports prompt_tokens/input_tokens, completion_tokens/output_tokens, total_tokens). Tests in test_openai_tts.py: TTSResult, TTSProvider.synthesize NotImplementedError, OpenAITTSProvider param passing, model/voice override, tts_arguments, bytes-only return, error propagation, usage extraction (prompt/completion/total and input/output keys). Commands run: uv run ruff format ., uv run ruff check ., uv run pytest -q (258 passed).

---

### [x] T0121 – CLI flags for TTS control and overrides (2026-01-31)

**Goal**
Expose TTS execution and override controls via CLI.

**Acceptance criteria**
* CLI supports: --tts / --no-tts (default: --tts), --tts-provider, --tts-voice.
* Resolution order: CLI flags → app_config.yaml → defaults (OpenAI / gpt-4o-mini-tts / Onyx).
* If --no-tts is set, pipeline ends after critic step.
* Pipeline step registration respects the flag (TTS step not run when disabled; placeholder for T0123 when enabled).
* Tests cover: default behavior, override precedence, pipeline skipping logic.
* All flags documented in SPEC.md and README.md.

**Allowed files**
* src/llm_storytell/cli.py
* src/llm_storytell/pipeline/**
* tests/test_cli.py
* tests/test_e2e.py
* SPEC.md
* README.md

**Result**
Added --tts, --no-tts, --tts-provider, --tts-voice to run subparser. Resolved tts_enabled (default True; --no-tts wins over --tts), tts_provider and tts_voice (CLI → app_config → defaults). _run_pipeline accepts tts_enabled and resolved_tts_config; initialize_run receives resolved_tts_config only when tts_enabled (state has no tts_config when --no-tts). Pipeline ends after critic when --no-tts; placeholder for TTS step when enabled. New tests/test_cli.py: parser flags, default enabled, --no-tts disables, provider/voice override, --no-tts wins. test_e2e: test_e2e_no_tts_pipeline_ends_after_critic; test_e2e_full_pipeline asserts state has tts_config. SPEC.md and README.md updated with TTS flags and resolution order. Commands run: uv run ruff format ., uv run ruff check ., uv run pytest -q (246 passed).

---

### [x] T0120 – Extend app config to support TTS + audio settings (2026-01-31)

**Goal**
Add first-class support for TTS and audio-related configuration in app_config.yaml, with deterministic loading and runtime overrides.

**Acceptance criteria**
* app_config.yaml supports the following optional keys: tts-provider (default: openai), tts-model (default: gpt-4o-mini-tts), tts-voice (default: Onyx), tts-arguments (dict, optional), bg-music (string path, optional).
* Missing keys do not fail the run.
* Resolved values (after defaults) are persisted into state.json for reproducibility.
* CLI overrides (later task) take precedence over config.
* Tests cover: full config, partial config, empty config.

**Allowed files**
* src/llm_storytell/config/**
* src/llm_storytell/run_dir.py
* tests/test_config_loading.py

**Result**
AppConfig extended with tts_provider, tts_model, tts_voice, tts_arguments, bg_music (optional, with built-in defaults). YAML keys supported as tts-provider, tts-model, tts-voice, tts-arguments, bg-music. AppConfig.resolved_tts_config() returns JSON-serializable dict for state. run_dir._create_initial_state and initialize_run accept optional resolved_tts_config and persist to state.json when provided. New tests in test_config_loading.py: full/partial/empty TTS config, state persistence, resolved_tts_config serializability. Commands run: uv run ruff format ., uv run ruff check ., uv run pytest -q (240 passed).

---

### [x] T008 v1.0.3 Target word count CLI (2026-01-31)

**Goal**
Add `--word-count N` CLI flag for target total word count. Given word-count and section_length, compute beat_count (round to nearest integer) and per-section length; pass to pipeline. Generated stories should fall within 10% of target word count.

**Acceptance criteria**
* CLI accepts `--word-count N` (integer) where 15000 > N > 100. Fails loudly when N not in range.
* The flag and its purpose are reflected in SPEC.md and README.md
* Pipeline first derives beat_count and section_length for the run, then successfully runs with these input parameters.
* If both --beats and --word-count are provided, the following constraits are checked first (fail loudly with CLI output explaining reason):
  - word-count / beats > 100
  - word-count / beats < 1000
* Acceptance criterion for the feature: generated stories fall within 10% interval of target word count (document in SPEC; tests or manual verification as appropriate).

**Allowed files**
* `src/llm_storytell/cli.py`
* `src/llm_storytell/` (orchestration / run init as needed)
* `tests/**` (do not modify, only add new test)
* `README.md`
* `SPEC.md`

**Commands to run**
* `uv run ruff format .`
* `uv run ruff check .`
* `uv run pytest -q`

**Result**
CLI: added `--word-count N` (100 < N < 15000); validation with clear stderr messages. When only `--word-count` is set, baseline section length from `--section-length` or app config midpoint; beat_count = round(word_count/baseline) clamped to 1–20; section_length derived as [per_section*0.8, per_section*1.2]. When both `--beats` and `--word-count` are set, validate word_count/beats in (100, 1000) then derive section_length. run_dir: optional `word_count` added to `_create_inputs_json` and `initialize_run`; persisted in inputs.json when provided. SPEC and README: `--word-count` added to CLI table; SPEC documents derivation and ~10% target. New tests: test_run_init (inputs.json includes word_count when provided), test_e2e (word_count range validation, beats+word_count ratio validation, derivation and persistence), test_cli_word_count (_section_length_midpoint). Commands run: `uv run ruff format .`, `uv run ruff check .`, `uv run pytest -q` (232 passed).

---

### [x] T007 v1.0.2 Update README and SPEC for new app structure and CLI (2026-01-31)

**Goal**
Update README and SPEC to describe the `apps/` layout (introduced in T002), `app_config.yaml`, `apps/default_config.yaml`, section_length (T004), and `--section-length` CLI flag. Update "How to add a new app" to use apps/ and default_config.

**Acceptance criteria**
* README and SPEC describe `apps/<app_name>/` structure (context, prompts, app_config.yaml).
* CLI documentation includes `--section-length` (from T004).
* "How to add a new app" reflects apps/ and that only lore_bible.md is required when using default_config.

**Allowed files**
* `README.md`
* `SPEC.md`

**Commands to run**
* `uv run ruff format .`
* `uv run ruff check .`
* `uv run pytest -q`

**Result**
SPEC: Repository Structure updated to `apps/<app_name>/` (context, optional prompts, app_config.yaml) and `prompts/app-defaults/`. CLI section replaced with a single markdown table (flag | values allowed | description) including `--app`, `--seed`, `--beats`, `--sections`, `--run-id`, `--config-path`, `--model`, `--section-length`. Context Loading paths changed from `context/<app>/` to `apps/<app_name>/context/`. README: Context handling, Prompt templates, Repository structure, .gitignore, and "How to add a new app" updated to apps/ and default_config; Supported CLI arguments reformatted to same three-column table. No code or test changes. Commands run: `uv run ruff format .`, `uv run ruff check .`, `uv run pytest -q` (223 passed).

---

### [x] T006 v1.0.2 .gitignore apps/ except example_app (2026-01-31)

**Goal**
Update `.gitignore` so `apps/` is ignored except for a committed `apps/example_app/` (or equivalent). 
Add `apps/example_app/` with minimal required context and optional app_config.yaml

**Acceptance criteria**
* `.gitignore` excludes `apps/` but not `apps/example_app/` (or the chosen name).
* `apps/example_app/` exists in repo with at least `context/lore_bible.md` and optional `app_config.yaml` so new users can run with `--app example_app`.

**Allowed files**
* `.gitignore`
* `apps/example_app/**` (new directory and files)
* `README.md` (optional: pointer to example_app)

**Commands to run**
* `uv run ruff format .`
* `uv run ruff check .`
* `uv run pytest -q`

**Result**
Updated `.gitignore`: replaced `apps/` with `apps/*` and `!apps/example_app/*` with `!apps/example_app/` so Git tracks only `apps/example_app/` and `apps/default_config.yaml`; rest of `apps/` remains ignored. Ensured `apps/example_app/` has `context/lore_bible.md`, `context/characters/example_character.md` (minimal required for run), and optional `app_config.yaml` (comment only). Added README pointer under Example apps and updated MVP scope to mention example_app and that other apps are gitignored. No new tests (allowed files did not include tests/; no new code behaviour). Commands run: `uv run ruff format .`, `uv run ruff check .`, `uv run pytest -q` (223 passed).

---

### [x] T005 v1.0.2 Context selection limits from app config (2026-01-31)

**Goal**
Wire the context loader to use app config limits (already in `AppConfig`: `max_characters`, `max_locations`, `include_world` per T002) when selecting files, instead of hardcoded constants.

**Acceptance criteria**
* Context loader receives and uses app config limits (max character files, max location files, whether to include world) when selecting files; defaults come from `apps/default_config.yaml` via existing `load_app_config()`.
* Deterministic selection order (e.g. alphabetical) is unchanged; only counts/limits are configurable.

**Notes**
* T002 already added `max_characters`, `max_locations`, `include_world` to `apps/default_config.yaml` and `AppConfig`; this task wires the context loader to use them (e.g. pass `AppConfig` or limits into `ContextLoader` and replace hardcoded `MAX_CHARACTERS` etc.).

**Allowed files**
* `config/`
* `src/llm_storytell/config/`
* `src/llm_storytell/context/loader.py`
* `src/llm_storytell/cli.py`
* `tests/**`

**Commands to run**
* `uv run ruff format .`
* `uv run ruff check .`
* `uv run pytest -q`

**Result**
ContextLoader now accepts optional `app_config: AppConfig | None`; when provided, uses `max_characters`, `max_locations`, and `include_world` for selection. Replaced hardcoded `MAX_CHARACTERS` with `MAX_CHARACTERS_DEFAULT`; selection uses `_max_characters`, `_max_locations`, `_include_world` (from app_config or defaults). World is folded into lore only when `_include_world` is True; location is omitted when `_max_locations == 0`. CLI: load_app_config already called in main(); added `app_config` parameter to `_run_pipeline` and pass it into ContextLoader. Tests: new `TestContextLoaderAppConfigLimits` (max_characters=2, max_locations=0, include_world=False, no app_config defaults). Commands run: `uv run ruff format .`, `uv run ruff check .`, `uv run pytest -q` (223 passed).

---

### [x] T004 v1.0.2 section_length from app config and CLI override (2026-01-31)

**Goal**
Use `section_length` from app config (already in `apps/default_config.yaml` and `AppConfig` per T002) in the section prompt. Remove hardcoded word count from `20_section.md`. Add CLI `--section-length N` override; pipeline receives range `[N*0.8, N*1.2]` as section_length value for that run.

**Acceptance criteria**
* `20_section.md` receives a `section_length` variable (e.g. range string); no hardcoded word count in the prompt body.
* Section step and prompt render pass `section_length` from app config (or CLI-derived range when `--section-length N` is set) into the section prompt.
* CLI accepts `--section-length N` (integer); when set, pipeline uses range `[N*0.8, N*1.2]` for that run instead of app config value.

**Notes**
* T002 already added `section_length` to `apps/default_config.yaml` and `AppConfig`; this task wires it into the section prompt and adds the CLI override.

**Allowed files**
* `config/`
* `prompts/app-defaults/20_section.md`
* `src/llm_storytell/config/`
* `src/llm_storytell/steps/section.py`
* `src/llm_storytell/prompt_render.py`
* `src/llm_storytell/cli.py`
* `tests/**`

**Commands to run**
* `uv run ruff format .`
* `uv run ruff check .`
* `uv run pytest -q`

**Result**
Replaced hardcoded "400–800 words" in `prompts/app-defaults/20_section.md` with `{section_length} words` and documented section_length in inputs. Added `section_length: str` to `execute_section_step()` and to prompt_vars. CLI: added `--section-length N`; when set, section_length = f"{int(N*0.8)}-{int(N*1.2)}", else app_config.section_length; passed to _run_pipeline and to each execute_section_step. Prompt variable contract: added section_length to SECTION_REQUIRED. Tests: test_section_loop all execute_section_step calls pass section_length; new test_section_prompt_includes_section_length; temp_prompts_dir fixture section template includes {section_length}; test_e2e_section_length_cli_override asserts --section-length 500 yields "400-600" in section prompt. Commands run: `uv run ruff format .`, `uv run ruff check .`, `uv run pytest -q` (219 passed).

---

### [x] T003 v1.0.2 Move app data under apps/<app_name>/, use app-defaults prompts (2026-01-31)

**Goal**
Move app context and prompts under `apps/<app_name>/`. Use `prompts/app-defaults/` when an app does not provide its own prompts. Remove or deprecate `prompts/apps/grim-narrator` in favor of app-defaults. Remove legacy resolution so only `apps/<app_name>/` is used.

**Acceptance criteria**
* Context is loaded from `apps/<app_name>/context/` (lore_bible, characters, locations, world, style).
* Prompts are loaded from `apps/<app_name>/prompts/` if present, else `prompts/app-defaults/`.
* `prompts/apps/grim-narrator/` is removed; grim-narrator (or example app) uses app-defaults.
* App resolver no longer falls back to `context/<app>/` or `prompts/apps/<app>/`; resolution uses only `apps/<app_name>/` (T002 added apps-first resolution; this task removes the legacy fallback and migrates existing app data).

**Allowed files**
* `prompts/`
* `src/llm_storytell/config/`
* `src/llm_storytell/context/`
* `src/llm_storytell/pipeline/`
* `src/llm_storytell/prompt_render.py`
* `src/llm_storytell/cli.py`
* `tests/**`
* `apps/**`

**Notes**
* T002 already added apps-first resolution and app-defaults fallback; this task removes legacy paths and migrates grim-narrator under apps/.

**Result**
App resolver now uses only `apps/<app_name>/`: context from `apps/<app_name>/context/`, prompts from `apps/<app_name>/prompts/` if present else `prompts/app-defaults/`. Removed legacy fallback to `context/<app>/` and `prompts/apps/<app>/`. Deleted `prompts/apps/grim-narrator/` (all prompt files). Created `apps/grim-narrator/context/lore_bible.md` and `apps/grim-narrator/context/characters/protagonist.md` so grim-narrator runs with app-defaults. Updated CLI `--app` help to require `apps/<app>/context/`. Tests: app resolution apps-only (removed legacy-only tests; nonexistent app raises with apps/ message); e2e fixtures use `apps/<app>/context/` and copied `prompts/app-defaults/`; failure tests use `apps/test-app/context/` paths; MockLLMProvider parses "Beats count:\s*N" for app-defaults outline prompt; lore_bible missing test expects SystemExit(1). Prompt variable and template-fix tests use `prompts/app-defaults/`. Commands run: `uv run ruff format .`, `uv run ruff check .`, `uv run pytest -q` (217 passed).

---

### [x] T002 v1.0.2 Introduce apps directory structure and config (2026-01-31)

**Goal**
Introduce `apps/` as the root for app data. Add `apps/default_config.yaml` with default values and support `app_config.yaml` per app. Pipeline resolves app from `apps/<app_name>/`; only required app file is `apps/<app_name>/context/lore_bible.md`.

**Acceptance criteria**
* `apps/default_config.yaml` exists with defaults for beats, section_length, context limits, LLM provider/model.
* App config loader reads `apps/<app_name>/app_config.yaml` and merges with defaults.
* App resolution uses `apps/<app_name>/` for context path; app is valid if only `apps/<app_name>/context/lore_bible.md` exists (no prompts/ required for default prompts).
* Existing runs and CLI `--app` continue to work; migration of existing app data under `apps/` is a separate task.

**Allowed files**
* `config/`
* `src/llm_storytell/config/`
* `src/llm_storytell/context/`
* `src/llm_storytell/cli.py`
* `tests/**`
* `docs/decisions/0001-tech-stack.md` (only if new dependency added)

**Commands to run**
* `uv run ruff format .`
* `uv run ruff check .`
* `uv run pytest -q`

**Notes**
* Do not move existing `context/` or `prompts/apps/` in this task; only add new apps layout and config loading. Migration is T003.

**Result**
Added `apps/default_config.yaml` with defaults (beats, section_length, max_characters, max_locations, include_world, llm_provider, model). Created `src/llm_storytell/config/app_config.py` with `AppConfig` dataclass and `load_app_config()` (defaults from apps/default_config.yaml, optional app overrides from apps/<app_name>/app_config.yaml; built-in defaults when file missing for legacy/e2e). Updated `app_resolver.py`: resolution prefers `apps/<app_name>/context/lore_bible.md` (prompts from apps/<app>/prompts/ or prompts/app-defaults/), falls back to legacy context/ + prompts/apps/; `AppPaths` now includes `app_root`. CLI loads app config after resolve and uses `app_config.beats` when `--beats` not provided. New tests: app resolution from apps/ (lore_bible only, with prompts dir, apps preferred over legacy); app config (defaults only, merge overrides, missing default uses builtin, invalid YAML raises, app_root, empty default raises, AppConfig frozen). Commands run: `uv run ruff format .`, `uv run ruff check .`, `uv run pytest -q` (220 passed).

---

### [x] T001 v1.0.1 Soft warnings when approaching context limits (2026-01-31)

**Goal**
Add soft warnings when combined context (lore, style, location, characters) approaches a defined token or character threshold. No change to selection or pipeline success/failure.

**Acceptance criteria**
* Threshold(s) for combined context are defined (token count and/or character count).
* When combined context approaches threshold, a warning is logged to run.log.
* Context selection and pipeline behavior are unchanged; run does not fail due to the warning.

**Allowed files**
* `SPEC.md`
* `src/llm_storytell/context/loader.py`
* `src/llm_storytell/logging.py`
* `tests/**`

**Commands to run**
* `uv run ruff format .`
* `uv run ruff check .`
* `uv run pytest -q`

**Result**
Pipeline-level default character threshold set to 15 000; per-model overrides via `CONTEXT_CHAR_WARNING_THRESHOLD_BY_MODEL` (dict model → threshold). Added `RunLogger.warning()`; context loader computes combined context size and logs one WARNING to run.log when ≥ threshold (optional `model` param for lookup). SPEC updated with "Context size warning (v1.0.1)" subsection. New tests: RunLogger.warning writes [WARNING]; no warning below threshold; warning at/above default threshold; no crash when logger is None; model-specific threshold used when model in dict; default used when model not in dict. Commands run: `uv run ruff format .`, `uv run ruff check .`, `PYTHONPATH=. uv run pytest -q` (210 passed).

---

### [x] R0004 Milestone planning pre-v1.1 (2026-01-31)

**Goal**
Refine the roadmap for v1.0.1 + v1.0.2 + v1.0.3 and translate it into a series of individual tasks in a given format, ready to be worked on by a software developer AI agent.

**Context**
v1.0 scope is frozen. Future milestones must be planned using the task format found in `TASKS.md` file.

**Inputs**
- Current `SPEC.md`
- Current `README.md`
- Current `TASKS.md`

**Deliverables**

- Refined roadmap section for all items in scope of v1.0.1 + v1.0.2 + v1.0.3
- New tasks added to `TASKS.md`:
  - Using template format
  - Clear acceptance criteria
  - Explicit allowed files
  - Tasks ordered for execution

**Acceptance criteria**

- Series of tasks is created. 
- Tasks are small, explicitly scoped, and executable by an agent,
- Tasks follow format rules
- Combined, these tasks achieve all functionality defined for v1.0.1 + v1.0.2 + v1.0.3 in the roadmap
- No v1.0 behavior is modified

**Allowed files**

* `README.md`
* `TASKS.md`
* `SPEC.md`

**Notes**

* Do not implement anything
* This task is planning only
* Keep milestone scope tight and explicit

**Result**
Refined roadmap in SPEC (subsection "Roadmap (v1.0.1 – v1.0.3) refined scope"); added v1.0.2 and v1.0.3 to README roadmap list; added tasks T001–T008 to TASKS.md in template format, ordered for execution. Planning only; no ruff/pytest required for doc-only edits.

---

## Pre-v1.0

### [x] R0003 Test coverage confidence pass (2026-01-31)

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

**Result**
Identified gap: no tests asserted that state is unchanged when a step fails. Added four unit tests (tests only): (1) `test_outline_step.py`: `test_on_provider_error_state_not_updated` — on outline LLM error, state outline and token_usage remain empty; (2) `test_section_loop.py`: `test_on_section_provider_error_state_not_updated` — on section LLM error, state sections and token_usage unchanged; (3) `test_section_loop.py`: `test_on_summarize_provider_error_state_not_updated` — on summarize LLM error, state summaries, continuity_ledger, token_usage unchanged; (4) `test_critic_step.py`: `test_on_provider_error_state_not_updated` — on critic LLM error, state has no final_script_path/editor_report_path and token_usage not appended. All use existing fixtures and mocks; no network or API keys. Commands run: `uv run ruff format .`, `uv run ruff check .`, `PYTHONPATH=. uv run pytest -q` (204 passed).

---

### [x] R0002 Documentation cleanup for v1.0 (2026-01-31)

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

**Result**
README.md: Quickstart now states credentials are file-based (`config/creds.json`), added minimal .gitignore list; run command uses `uv run python -m llm_storytell run ...`; added "Supported CLI arguments" table and "How to add a new app" section; expected outputs list run.log, inputs.json, state.json, artifacts/, llm_io/ and artifact names; pipeline flow updated to "outline → (for each beat: section then summarize) → critic"; repo structure updated with config/pipeline.yaml, model.yaml, runs/<run_id>/ contents. SPEC.md: Pipeline Configuration now states step order is fixed in orchestrator (cli.py), pipeline.yaml may be empty; Run Artifacts updated with llm_io/<stage_name>/ and 30_critic_raw_response.txt; removed stray copy-paste line; Logging "randomized selections" → "deterministic; no randomness"; added "Failure semantics" (missing context, step failure, validation failure). CONTRIBUTING.md: Added "Required commands" subsection (uv run ruff format ., uv run ruff check ., uv run pytest -q) and referenced it in Definition of Done. Commands run: `uv run ruff format .`, `uv run ruff check .`, `PYTHONPATH=. uv run pytest -q` (200 passed).

---

### [x] R0001-1 Scope increase for v1.0: modify model selection logic (2026-01-30)

**Goals**
1. Change default model for OpenAI provider prompts to "gpt-4.1-mini"
2. Add support for parsing optional CLI "--model" flag in "llm_storytell run ..." command and using that model in all calls for that run (fail immediately if provider API does not identify requested model)
3. Document the new functionality in relevant docs (README/SPEC)

**Inputs**
CLI command (macOS): `./.venv/bin/python -m llm_storytell run --app grim-narrator --model gpt-4.1.nano --seed "A story of how suffering is a grim reality at lower society levels in the future."`

**Allowed files**
README.md, SPEC.md, CONTRIBUTING.md, src/llm_storytell/cli.py, src/llm_storytell/steps/*, src/llm_storytell/pipeline/*, src/llm_storytell/llm/*; tests expanded for --model and invalid-model behaviour.

**Result**
- **cli.py**: Added optional `--model`; default model changed from `gpt-4` to `gpt-4.1-mini`. `_run_pipeline` now takes `model` and passes it to `_create_llm_provider_from_config(default_model=model)` so the same provider (and thus the same model) is used for every LLM call in the run.
- **llm/__init__.py**: When the client raises an exception whose message indicates model not recognized (e.g. "does not exist", "not found", "invalid"), `OpenAIProvider.generate` raises `LLMProviderError` immediately without retrying.
- **SPEC.md**: Documented `--model` under Optional arguments (default gpt-4.1-mini; run fails immediately if provider does not identify the model).
- **README.md**: Documented optional `--model` and default in the "Running the pipeline" section.
- **Tests**: `test_llm_provider.py`: added `TestOpenAIProviderModelNotRecognized.test_model_not_recognized_fails_immediately_without_retry` (client raises "does not exist" → one call, no retry, clear error). `test_e2e.py`: added `test_e2e_model_flag_passed_to_provider_and_used_for_all_calls` (--model gpt-4.1-nano → provider created with default_model="gpt-4.1-nano"); `test_e2e_default_model_when_no_model_flag` (no --model → default_model="gpt-4.1-mini").
- Commands run: `uv run ruff format .`, `uv run ruff check .`, `PYTHONPATH=. uv run pytest -q` (190 passed).

---

### [x] R0001-BB-03 Bug Bash: E2E Production test (2026-01-30)

TASK: Fix-the-run loop (no-refactor, artifact-driven)

**Goal**: Given ONE exact CLI command, execute it until it succeeds. On each failure: gather evidence, diagnose, apply smallest fix, rerun.

**CLI command (macOS)**: `./.venv/bin/python -m llm_storytell run --app grim-narrator --beats 2 --seed "A story of how suffering is a grim reality at lower society levels in the future."`

**Result**: One failure: outline stage failed because `prompts/apps/grim-narrator/10_outline.md` contained a JSON example with unescaped `{`/`}`; the formatter treated `{ "beats"}` as a placeholder and raised UnsupportedPlaceholderError. Fix: escaped all braces in the JSON example block to `{{`/`}}`. Added success/failure logging in outline step (print on prompt render success; catch UnsupportedPlaceholderError and print before re-raise). No new test added—`tests/test_template_fix.py` already renders the outline template and would have caught this. Commands run: `uv run ruff format .`, `uv run ruff check .`, `uv run pytest --ignore=tests/test_e2e.py -q` (179 passed). E2E run succeeded; final run dir: `runs/run-20260130-174742`.

---

### [x] R0001-BB-01a (Follow-up) Unify llm_io persistence across stages (2026-01-30)

**Goal**: Extend `steps/llm_io.py` so all stages use the same mechanism for prompt.txt, response.txt (only when non-empty), meta.json, and raw_response.json; then refactor critic to use it and remove critic-only _write_critic_llm_io.

**Allowed files**: `src/llm_storytell/steps/llm_io.py`, `src/llm_storytell/steps/critic.py`, and any other step/orchestration files that call save_llm_io; `tests/test_critic_step.py`, `tests/test_outline_step.py`, `tests/test_section_loop.py`, and any tests that assert on llm_io layout.

**Acceptance**: Same behavior as R0001-BB-01 (no placeholder response.txt, meta/raw in llm_io); single save_llm_io API used by all stages; `uv run pytest -q` green.

**Result**: Extended `save_llm_io(run_dir, stage_name, prompt, response=None, *, meta=None, raw_response=None)` in `llm_io.py`: writes prompt.txt always; response.txt only when response is non-empty (backwards compatible); meta.json when meta provided (minimal shape: status, provider, model; error only when status "error"); raw_response.json when raw_response provided (sensitive keys redacted). Removed `_write_critic_llm_io` and `_CRITIC_REDACT_KEYS` from critic; critic uses only `save_llm_io`. Outline, section, summarize: pre-call and error paths write meta (pending/error), no response.txt; success path writes prompt, response, meta, raw_response. On error, meta with error info is written and not swallowed. Tests: success path (prompt.txt + response.txt) for outline/section/summarize; error path (no response.txt, meta status=error); backwards compat (non-empty response writes response.txt; None/empty do not). Test imports fixed to use `src.llm_storytell.llm` so mock’s LLMProviderError is caught by steps. Commands run: `uv run ruff format .`, `uv run ruff check .`, `PYTHONPATH=<project_root> uv run pytest -q` (187 passed).

---

### [x] R0001-BB-01 Bug Bash: Empty critic response.txt (2026-01-29)

Task: Fix critic response.txt empty-placeholder + treat empty LLM content as hard provider error + persist raw IO consistently

**Result (reworked to allowed files only)**: Critic no longer writes placeholder response.txt; pre-call persists prompt.txt + meta.json (pending) via critic-only helper _write_critic_llm_io in critic.py (no changes to steps/llm_io.py). Provider raises LLMProviderError on content None, "", or whitespace-only (llm/__init__.py). CLI passes raw content (no or ""). On success critic uses save_llm_io for prompt+response then _write_critic_llm_io for meta + raw_response.json; on error writes meta status=error and raw_response only. artifacts/30_critic_raw_response.txt kept. Tests: provider None/empty/whitespace (test_llm_provider); critic no response.txt pre-call + meta status=error (test_critic_step); fixture two-block format; E2E mock two-block. Collection error and outline/logging test assertions fixed so uv run pytest -q passes (181 passed). Follow-up: task to extend llm_io.py for meta/raw_response and align all stages can be added if desired.

---

### [x] T0111 Task: Enforce MVP context contract across code + prompts + docs (2026-01-29)

**Goal**
Implement and enforce this contract for all apps (starting with grim-narrator):
1) Required on every run step:
   - context/<app>/lore_bible.md must exist and be loaded for every step.
   - At least 1 character file in context/<app>/characters/*.md must exist and be included for every step.
2) Optional:
   - Location is NOT required. If context/<app>/locations/ exists and has .md files, include exactly 1 location (deterministic selection) on every step; otherwise location_context must be "".
   - World is NOT required. If context/<app>/world/ exists and has .md files, include ALL world files (MVP) by folding them into lore_bible (or otherwise making them available) on every step; if absent, still generate output.

**Scope / Constraints**
- Keep backward compatibility: missing optional folders must not stop output.
- Deterministic selection: do not use randomness. Pick location/characters in a stable way (e.g. alphabetical order, first N).
- Centralize context loading: do NOT let each step load context differently. Ensure all steps use the same loader/logic.
- Ensure prompt rendering does not treat JSON braces as placeholders: placeholders must be strictly {identifier} only.

**Result**: Centralized context in `ContextLoader` (required: lore_bible + ≥1 character; optional: 1 location, world/*.md folded into lore_bible with separator). CLI uses loader and fails fast on ContextLoaderError. Steps use shared `build_prompt_context_vars(context_dir, state)`. Deterministic selection: location = first alphabetically, characters = first 3 alphabetically, world = all alphabetically. State persists `selected_context.location`, `characters`, `world_files`. Prompt render restricts placeholders to `{identifier}` only. SPEC.md and README.md updated. Tests: context loader (required/optional, deterministic, world fold), placeholder (JSON no fake vars), e2e (fail when required missing, succeed when optional missing). Commands run: `uv run ruff format .`, `uv run ruff check .`, `uv run pytest -q` (177 passed).

---

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
