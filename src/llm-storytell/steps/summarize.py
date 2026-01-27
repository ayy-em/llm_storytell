"""Summarization step for the pipeline.

Summarizes a generated section and extracts continuity updates for
maintaining narrative consistency across sections.
"""

import json
import tempfile
from pathlib import Path
from typing import Any

from ..continuity import merge_continuity_updates
from ..llm import LLMProvider, LLMProviderError
from ..llm.token_tracking import record_token_usage
from ..logging import RunLogger
from ..prompt_render import MissingVariableError, TemplateNotFoundError, render_prompt
from ..schemas import SchemaValidationError, validate_json_schema


class SummarizeStepError(Exception):
    """Raised when summarize step execution fails."""

    pass


def _load_state(run_dir: Path) -> dict[str, Any]:
    """Load state.json from run directory.

    Args:
        run_dir: Path to the run directory.

    Returns:
        State dictionary.

    Raises:
        SummarizeStepError: If state.json cannot be loaded.
    """
    state_path = run_dir / "state.json"
    if not state_path.exists():
        raise SummarizeStepError(f"State file not found: {state_path}")

    try:
        with state_path.open(encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise SummarizeStepError(f"Invalid JSON in state.json: {e}") from e
    except OSError as e:
        raise SummarizeStepError(f"Error reading state.json: {e}") from e


def _load_section_artifact(run_dir: Path, section_index: int) -> str:
    """Load section artifact file for a given section index.

    Args:
        run_dir: Path to the run directory.
        section_index: Zero-based index of the section (0 for first section).

    Returns:
        Section content as string.

    Raises:
        SummarizeStepError: If artifact file cannot be loaded.
    """
    # Section ID is 1-based for filename
    section_id = section_index + 1
    artifact_filename = f"20_section_{section_id:02d}.md"
    artifact_path = run_dir / "artifacts" / artifact_filename

    if not artifact_path.exists():
        raise SummarizeStepError(
            f"Section artifact not found: {artifact_path} "
            f"(section_index={section_index})"
        )

    try:
        return artifact_path.read_text(encoding="utf-8")
    except OSError as e:
        raise SummarizeStepError(f"Error reading section artifact: {e}") from e


def _update_state(
    run_dir: Path,
    summary_data: dict[str, Any],
    continuity_ledger: dict[str, str],
    token_usage: dict[str, Any],
) -> None:
    """Update state.json with summary, continuity ledger, and token usage.

    Uses atomic write (temp file + rename) to avoid partial state.

    Args:
        run_dir: Path to the run directory.
        summary_data: The validated summary data to append.
        continuity_ledger: Updated continuity ledger to merge.
        token_usage: Token usage dictionary to append.

    Raises:
        SummarizeStepError: If state update fails.
    """
    state_path = run_dir / "state.json"

    # Load current state
    try:
        with state_path.open(encoding="utf-8") as f:
            state = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise SummarizeStepError(f"Error reading state for update: {e}") from e

    # Update state: append summary, merge continuity ledger, append token usage
    if "summaries" not in state:
        state["summaries"] = []
    state["summaries"].append(summary_data)
    state["continuity_ledger"] = continuity_ledger
    state["token_usage"].append(token_usage)

    # Atomic write
    temp_file = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=run_dir,
            delete=False,
            suffix=".tmp",
        ) as f:
            temp_file = Path(f.name)
            json.dump(state, f, indent=2, ensure_ascii=False)

        # Atomic rename
        temp_file.replace(state_path)
        temp_file = None
    except OSError as e:
        if temp_file and temp_file.exists():
            temp_file.unlink()
        raise SummarizeStepError(f"Error writing updated state: {e}") from e


def execute_summarize_step(
    run_dir: Path,
    prompts_dir: Path,
    llm_provider: LLMProvider,
    logger: RunLogger,
    section_index: int,
    schema_base: Path | None = None,
) -> None:
    """Execute the summarization step for a single section.

    Summarizes a section and extracts continuity updates, updating the
    rolling summary and continuity ledger.

    Args:
        run_dir: Path to the run directory.
        prompts_dir: Path to the app's prompts directory.
        llm_provider: LLM provider instance.
        logger: Run logger instance.
        section_index: Zero-based index of the section to summarize
            (0 for first section, 1 for second, etc.).
        schema_base: Base path for schema resolution. If None, uses
            src/llm-storytell/schemas relative to run_dir.

    Raises:
        SummarizeStepError: If any step fails.
    """
    logger.log_stage_start(f"summarize_{section_index:02d}")

    try:
        # Load state
        state = _load_state(run_dir)

        # Load section artifact directly
        section_content = _load_section_artifact(run_dir, section_index)

        # Section ID is 1-based
        section_id = section_index + 1

        # Load and render prompt template
        prompt_path = prompts_dir / "21_summarize.md"
        if not prompt_path.exists():
            raise SummarizeStepError(f"Prompt template not found: {prompt_path}")

        prompt_vars = {
            "section_id": section_id,
            "section_content": section_content,
        }

        try:
            rendered_prompt = render_prompt(prompt_path, prompt_vars)
        except TemplateNotFoundError as e:
            raise SummarizeStepError(f"Prompt template not found: {e}") from e
        except MissingVariableError as e:
            raise SummarizeStepError(
                f"Missing variables in prompt template: {e}"
            ) from e

        # Call LLM provider
        try:
            result = llm_provider.generate(
                rendered_prompt,
                step=f"summarize_{section_index:02d}",
                temperature=0.5,  # Lower temperature for summarization
            )
        except LLMProviderError as e:
            raise SummarizeStepError(f"LLM provider error: {e}") from e

        # Parse JSON response
        try:
            summary_data = json.loads(result.content)
        except json.JSONDecodeError as e:
            raise SummarizeStepError(f"Invalid JSON in LLM response: {e}") from e

        # Ensure section_id matches
        summary_data["section_id"] = section_id

        # Validate against schema
        if schema_base is None:
            # Default to src/llm-storytell/schemas relative to project root
            current = Path.cwd()
            project_root = None
            for parent in [current] + list(current.parents):
                if (parent / "SPEC.md").exists() or (
                    parent / "pyproject.toml"
                ).exists():
                    project_root = parent
                    break
            if project_root is None:
                project_root = Path(__file__).parent.parent.parent.parent
            schema_base_path = project_root / "src" / "llm-storytell" / "schemas"
        else:
            schema_base_path = Path(schema_base)

        schema_path = schema_base_path / "summary.schema.json"
        try:
            validate_json_schema(summary_data, schema_path, logger)
        except SchemaValidationError as e:
            raise SummarizeStepError(f"Schema validation failed: {e}") from e

        # Merge continuity updates into ledger
        current_ledger = state.get("continuity_ledger", {})
        continuity_updates = summary_data.get("continuity_updates", {})
        if not isinstance(continuity_updates, dict):
            raise SummarizeStepError(
                "continuity_updates must be a dictionary in summary data"
            )
        updated_ledger = merge_continuity_updates(current_ledger, continuity_updates)

        # Record token usage
        token_usage_dict = record_token_usage(
            logger=logger,
            step=f"summarize_{section_index:02d}",
            provider=result.provider,
            model=result.model,
            prompt_tokens=result.prompt_tokens or 0,
            completion_tokens=result.completion_tokens or 0,
            total_tokens=result.total_tokens,
        )

        # Update state
        _update_state(run_dir, summary_data, updated_ledger, token_usage_dict)

        logger.log_stage_end(f"summarize_{section_index:02d}", success=True)

    except SummarizeStepError:
        logger.log_stage_end(f"summarize_{section_index:02d}", success=False)
        raise
    except Exception as e:
        logger.log_stage_end(f"summarize_{section_index:02d}", success=False)
        raise SummarizeStepError(f"Unexpected error in summarize step: {e}") from e
