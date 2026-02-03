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
* Result (empty section upon creation, to be populated prior to moving task to COMPLETED_TASKS.py)

Agent is to stop after reading task and request clarification if any of the non-optional items are missing.

## Task: Definition of Done

1. Running the CLI command defined in SPEC.md initiates a successful run
2. `runs/<run_id>/` folder is created, containing:
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

## Task Group: Bug Bash pre-v1.2 public release

### [ ] T0130 – Tokens for TTS are not counted/logged

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

Result: 


### [ ] T0131 – Update docs after changes (README/SPEC/TASKS)

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

Result: 

---

## Roadmap (**do not start** yet unless explictly told)
- **v1.3** – Cloud execution + scheduled delivery (Telegram / email)
- **v1.4** – One-command video generation
- **v1.4.1** – Burned-in subtitles
- **v1.5** – Vector database for large-scale context retrieval and rotation
- **v1.6** – Multi-LLM provider support, routing, and cost-aware selection

## Previous Releases
- **v1.0** – Local, text-only pipeline (multi-app capable)
- **v1.0.1** – Add soft warnings when approaching context limits
- **v1.0.2** – Refactor adding apps, context structure and introduce app-level configs
- **v1.0.3** – Target word count CLI flag added
- **v1.1** – Text-to-speech audiobook output
- **v1.2** – Background music mixing and audio polish — **Current version**

## Backlog (Do not start)

- **Stderr on failure:** Change codebase so the run command is more explicit about errors via stderr on failures (e.g. step failures, validation errors). To be worked on later; do not implement now.
- **Python API:** Add a minimal non-CLI API for running the pipeline programmatically (low priority).
- **Increase CLI output when doing tts chunking**: show total number of segments, 