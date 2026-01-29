You are operating in the repository using the agent workflow rules in `.cursor/rules/*00-workflow.md*`.

1) Read `TASKS.md`, `SPEC.md`, and `CONTRIBUTING.md`. Also always read all the ruleset .md files in `.cursor/rules/**.md` before starting any task.
2) Select the **first unchecked** task in `TASKS.md` only. Do not work on any other task.
3) Pre-flight:
   - List relevant existing files and what is already implemented vs missing for the task.
   - Propose a solution design (5–15 bullets).
   - List the exact files you will modify (must be within “Allowed files”).
   - Wait for approval before implementation.

After approval:
4) Implement exactly what was approved.
5) Add/adjust unit tests as required.
6) Run:
   - `uv run ruff format .`
   - `uv run ruff check .`
   - `uv run pytest -q`
   Fix and rerun until all pass.

Finish:
7) Update `TASKS.md`: mark the task `[x]` and add a short **Result** note (what changed + commands run). Then move the section containing info on the completed task to `COMPLETED_TASKS.md`.
8) Prepare a single commit for this task only. Commit message: `TXXXX: <short task description>`.
9) Stop. Do not start the next task.
