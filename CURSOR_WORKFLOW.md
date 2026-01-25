# How to orchestrate agentic workflow in Cursor without chaos

The "cycle" workflow we aim for is: 
- Agent picks up the first unchecked task in TASKS.md 
- Agent proposes solution design
- You provide feedback on the proposal and suggest changes
- Agent iterates till solution design is accepted  
- Agent then delivers a solution, ensuring it passes `make check`
- You provide feedback on the solution and instructions to adjust the final solution 
- Agent adjusts based on your feedback till you accept it 
- Agent marks accepted task in `TASKS.md `
- Agent ensures any relevant docs, `README.md`, `SPEC.md` and `docs/decisions/` log files are updated 
- (Optional) You add more tasks to `TASKS.md `

The cycle repeats after this step.

How to enforece this:

- Cursor-specific rules for agents are defined in `.cursor/rules/*`
- Use standard kickoff prompt, copy-pasting it every cycle, like:
> Read TASKS.md and select the first unchecked task. 
> 
> Do not work on any other task. First, propose a solution design (5–15 bullets) referencing SPEC/CONTRIBUTING. 
>
> Wait for approval.
>
>After approval: implement, add tests, run ruff format, ruff check, pytest. 
>
>Update TASKS.md marking the task done with a Result note. 
>
>Stop.
- Alternatively, use this if there were already previous attempts at the task and/or some parts of it already implemented:
>Read TASKS.md, pick the first unchecked task only. 
>
>Before touching any files:
> - Check what already exists for that task (list the relevant files and what’s present/missing).
> - Propose a solution design (5–15 bullets).
> - Explicitly state what you will not change.
> - Wait for approval.
>
>After approval: implement only what’s missing, add/adjust tests, run:
> - `uv run ruff format .`
> - `uv run ruff check .`
> - `uv run pytest -q` 
>
>Update TASKS.md: mark [x] and add a Result note (what changed + commands run). 
>
>Stop.

- Your feedback should be binary and short. Example: "Approved, implement", or "No, change X to Y, then implement".
- Maintain and explicitly define "Allowed files" for each task
- Run in small diffs. One task = one commit. Reject big plans.
- Require agents to paste outputs from terminal. No output = no merge.