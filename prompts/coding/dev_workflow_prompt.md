You are operating in the repository using the agent workflow rules in `.cursor/rules/00-workflow.md`.

1) Read `SPEC.md`, `CONTRIBUTING.md` and all the ruleset .md files in `.cursor/rules/**.md` before starting.
2) Read `TASKS.md` and select the **first unchecked** task in this file. Do not work on any other task.
3) Pre-flight:
   - Review all relevant existing files and list what is already implemented vs missing for the task.
   - Propose a solution design (5–10 bullet points).
   - List the exact files you intend to modify (must all be within task's “Allowed files”).
   - Always request approval before implementation. If no approval is granted, iterate based on feedback. 
4) After approval, implement exactly what was approved, touching no other file.
5) Add unit tests for every new behaviour.
6) Run:
   - `uv run ruff format .`
   - `uv run ruff check .`
   - `uv run pytest -q`
7) Fix the code (only fix existing tests if explicitly approved) and rerun until all pass.
8) Once all tests and ruff checks succeed, consider the task complete. 
9) Update `TASKS.md`: Mark the completed task `[x]` and append a short **Result** note at the bottom of task section (what changed + commands run). 
10) Move the section containing info on the completed task to `COMPLETED_TASKS.md`.
11) Share a summary of changes made, files affected, and propose a commit message: `TXXXX: <short description>`.
12) Stop. Do not start the next task.
