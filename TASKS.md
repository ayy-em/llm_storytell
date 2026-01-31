# TASKS.md

This file is the active execution queue of tasks for AI agents. 

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
- `uv run ruff format .`
- `uv run ruff check .`
- `uv run pytest -q`
* New dependencies are **not allowed** unless explicitly requested by the task or approved upon request.
- If added, justify in `docs/decisions/0001-tech-stack.md`.
* Touch **only** the files listed in “Allowed files”.
* Persist outputs strictly under `runs/<run_id>/...` as per `SPEC.md`.
* Only remove tasks from this file after completing the following:
- Mark the completed task `[x]`
- Append a short **Result** note (what changed + commands run)
- Move the completed task's section to `COMPLETED_TASKS.md`

### Post-implementation spec/doc drift detection 
* After a task is accepted, briefly evaluate whether the change introduces:
- a new concept
- a new constraint
- a new required user-facing behavior
* If so, propose (do not implement) bullet-pointed and concise updates to:
- README.md
- SPEC.md
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

## Task: Definition of Done

1. Running the CLI command defined in SPEC.md successfully 
2. Run folder is created upon success, containing:
  - artifacts/ 
  - llm_io/
  - inputs.json
  - state.json
  - run.log
3. No credentials, API keys, tokens and other sensitive info outside of files in `.gitignore`.
4. No app-specific assumptions in platform code.
5. All ruff checks are passed.
6. All tests pass (`uv run pytest -q`).
7. README.md and SPEC.md are up-to-date and accurately reflect actual scope, technical solution design and other project information.
8. No finished tasks are found in TASKS.md file.


## Tasks for v1.2 (including v1.1) release
### [ ] T0121 – CLI flags for TTS control and overrides

Goal: Expose TTS execution and override controls via CLI.

Acceptance criteria
- CLI supports the following flags:
  - --tts / --no-tts (default: --tts)
  - --tts-provider
  - --tts-voice
- Resolution order:
	1.	CLI flags
	2.	app_config.yaml
	3.	defaults (OpenAI / gpt-4o-mini-tts / Onyx)
- If --no-tts is set, pipeline ends after critic step.
- Pipeline step registration respects the flag.
- Tests cover:
  - default behavior
  - override precedence
  - pipeline skipping logic
- All flags are documented in SPEC.md and README.md

Allowed files (Hard constraint)
- src/llm_storytell/cli.py
- src/llm_storytell/pipeline/**
- tests/test_cli.py
- tests/test_e2e.py
- SPEC.md 
- README.md

Commands to run
- uv run ruff format .
- uv run ruff check .
- uv run pytest -q

Result: 

### [ ] T0122 – Add TTS provider abstraction + OpenAI implementation

Goal: Introduce a provider-based TTS client system, starting with OpenAI.

Acceptance criteria
- New folder: src/llm_storytell/tts_providers/
- openai_tts.py implements:
- text → audio synthesis
- accepts model, voice, and tts-arguments
- returns audio bytes + token usage metadata (best-effort)
- No pipeline step imports provider SDKs directly.
- Provider interface is minimal and explicit.
- Tests mock OpenAI calls and verify:
- correct parameter passing
- error propagation
- token usage extraction

Allowed files (Hard constraint)
- src/llm_storytell/tts_providers/**
- src/llm_storytell/config/**
- tests/test_openai_tts.py

Commands to run:
- uv run ruff format .
- uv run ruff check .
- uv run pytest -q

Result:

### [ ] T0123 – Implement llm-tts pipeline step (chunking + synthesis)

Goal: Add a pipeline step that converts the final story text into multiple narrated audio segments.

Input: final story artifact (.md, plain text).

Acceptance criteria:
- Chunking logic:
  - target range: 700–1000 words
  - cut at first newline after 700 words
  - if none found by 1000:
    - succeed
    - log warning to run log + terminal
    - enforce 1 ≤ segments ≤ 22
- Artifacts written:
  - runs/<run_id>/tts/prompts/segment_XX.txt
  - runs/<run_id>/tts/outputs/segment_XX.<audio_ext>
  - Segments sent sequentially to provider.
- Logging includes:
  - segment progress
  - warnings on imperfect splits
  - cumulative token usage:
      response_prompt_tokens
      response_completion_tokens
      tts_prompt_tokens
      total_text_tokens
      total_tts_tokens
      total_tokens
  - State JSON records text vs TTS token usage separately.
- Tests must cover:
  - chunking edge cases
  - warning path
  - max segment enforcement
  - artifact creation

Allowed files (Hard constraint)
- src/llm_storytell/steps/llm_tts.py
- src/llm_storytell/pipeline/**
- src/llm_storytell/logging.py
- tests/test_llm_tts_step.py

Commands to run
- uv run ruff format .
- uv run ruff check .
- uv run pytest -q

Result: 

### [ ] T0124 – Implement audio-prep step (stitching + background music)

Goal: Produce a single narrated audio file with background music and volume automation.

Inputs: 0 < N ≤ 22 audio segments from llm-tts.

Acceptance criteria
- Steps:
	1.	Stitch segments into one voiceover track.
	2.	Calculate voiceover duration.
	3.	Load background music:
    - apps/<app_name>/assets/bg-music.* if exists
    - else assets/default-bg-music.wav
	4.	Loop bg music with 2s crossfade to duration + 6s.
	5.	Apply bg volume envelope:
    - 0–1.5s: 75%
    - 1.5–3.0s: fade to 10%
    - stay at 10% during narration
    - after narration end: fade to 70% over 2s
	6.	Mix voiceover + bg music.
- Output:
  - stitched voiceover saved to runs/<run_id>/voiceover/
  - final output saved to `runs/<run_id>/artifacts/narration-<app_name>.<ext>`
- Implementation uses ffmpeg via subprocess (PATH assumed).
- Tests mock subprocess calls and verify command construction and timing math.

Allowed files (Hard constraint)
- src/llm_storytell/steps/audio_prep.py
- src/llm_storytell/utils/** (if strictly necessary)
- tests/test_audio_prep_step.py

Commands to run
- uv run ruff format .
- uv run ruff check .
- uv run pytest -q

Result: 

### [ ] T0125 – Documentation updates for audio pipeline

Goal: Bring documentation in sync with reality so future-you doesn’t curse present-you.

Acceptance criteria
- README.md documents:
  - --tts / --no-tts
  - provider/voice overrides
  - ffmpeg requirement
  - where narration output lives
- SPEC.md updated with:
  - new pipeline steps
  - artifact layout (tts/, voiceover/, final narration)
  - failure + warning behavior
- 0001-tech-stack.md mentions ffmpeg usage (no new deps added).

Allowed files (Hard constraint)
- README.md
- SPEC.md
- docs/decisions/0001-tech-stack.md

Commands to run
- uv run ruff format .
- uv run ruff check .
- uv run pytest -q

Result: 

## Roadmap (**do not start** yet unless explictly told)

- **v1.0.1** - Add soft warnings when approaching context limits
- **v1.0.2** - Refactor adding apps, context structure and introduce app-level configs
- **v1.0.3** - Target word count CLI flag added
- **v1.1** – Text-to-speech audiobook output
- **v1.2** – Background music mixing and audio polish
- **v1.3** – Cloud execution + scheduled delivery (Telegram / email)
- **v1.4** – One-command video generation
- **v1.4.1** – Burned-in subtitles
- **v1.5** – Vector database for large-scale context retrieval and rotation
- **v1.6** – Multi-LLM provider support, routing, and cost-aware selection

## Previous Releases
- **v1.0** – Local, text-only pipeline (multi-app capable) - **Current version**
