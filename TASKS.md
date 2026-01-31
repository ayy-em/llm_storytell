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

## Task's: Definition of Done

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

## [ ] T006 v1.0.2 .gitignore apps/ except example_app

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

---

## [ ] T007 v1.0.2 Update README and SPEC for new app structure and CLI

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

---

## [ ] T008 v1.0.3 Target word count CLI

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
* `tests/**` (do not modify)
* `README.md`
* `SPEC.md`

**Commands to run**
* `uv run ruff format .`
* `uv run ruff check .`
* `uv run pytest -q`

---

## Roadmap (**do not start** yet unless explictly told)

- **v1.0.1** - Add soft warnings when approaching context limits
- **v1.0.2** - Refactor adding apps, context structure and introduce app-level configs
  - Revamp the way the pipeline handles app data to satisfy these bullet points
  - all app-specific data should now live exclusively within `apps/<app_name>/` folder 
  - Each `apps/<app_name>/` directory looks as follows:
  ``` 
  llm_storytell/
    apps/
      <app_name>/
        prompts/
          **.md
        assets/
          bg_music.wav
        context/
          world/
            **.md
          characters/
            **.md
          style/
            **.md
          locations/
            **.md
          lore_bible.md
        app_config.yaml
  ```
  - `prompts/apps/grim-narrator/` is to be removed, all apps should default to using `prompts/app-defaults/**.md` prompts instead
  - Number of words per section should no longer be hardcoded in `20_section.md` prompt at the very end. Instead, this should be app config-defined section_length variable with a pipeline-default value equal to "400-600". 
  - Add CLI run command flag to override section_length, it should take an int, and add a range of [input*0.8, input*1.2] as a section_length value to be passed to pipeline
  - apps-specific `app_config.yaml` should set the app's pipeline characteristics: 
    - LLM provider and model preferences 
    - default number of beats 
    - default words per section 
    - and how many .md files of context should be passed into the pipeline from each of the subfolders in `apps/<app_name>/context/` (e.g. 1 character + 1 location) 
  - each of the app-specific config values should have a default defined in `apps/default_config.yaml` so that the app is valid even if it doesn't have a config
  - only required app file is `apps/<app_name>/context/lore_bible.md`
  - gitgnore apps dir, except for a new example_app folder with an example config and required context files
  - update readme and spec to reflect new structures and functionalities
- **v1.0.3** - Target word count CLI flag added
 - --word-count CLI command flag added, denoting total target 
 - Users can now do `uv run llm_storytell.py --app <app_name> --word-count 3000
 - given word-count and section_length, calculate number of sections/beats required, round to closest integer to get beat_count, then divide word-count by beat_count to get a new number section_length value should then be set to
 - Acceptance criteria: generated stories fall within 10% interval of target word count
- **v1.1** – Text-to-speech audiobook output
- **v1.2** – Background music mixing and audio polish
- **v1.3** – Cloud execution + scheduled delivery (Telegram / email)
- **v1.4** – One-command video generation
- **v1.4.1** – Burned-in subtitles
- **v1.5** – Vector database for large-scale context retrieval and rotation
- **v1.6** – Multi-LLM provider support, routing, and cost-aware selection

## Previous Releases
- **v1.0** – Local, text-only pipeline (multi-app capable) - **Current version**
