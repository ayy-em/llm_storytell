"""Summarization step for the pipeline.

Summarizes a generated section and extracts continuity updates for
maintaining narrative consistency across sections.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llm_storytell.continuity import merge_continuity_updates
from llm_storytell.llm import LLMProvider, LLMProviderError
from llm_storytell.llm.token_tracking import record_token_usage
from llm_storytell.logging import RunLogger
from llm_storytell.prompt_render import (
    MissingVariableError,
    TemplateNotFoundError,
    render_prompt,
)
from llm_storytell.schemas import SchemaValidationError, validate_json_schema
from llm_storytell.steps.llm_io import save_llm_io


class SummarizeStepError(Exception):
    """Raised when summarize step execution fails."""

    pass


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
            src/llm_storytell/schemas relative to run_dir.

    Raises:
        SummarizeStepError: If any step fails.
    """
    try:
        # Load state
        from llm_storytell.pipeline.state import (
            StateIOError,
            load_state,
            update_state_atomic,
        )

        try:
            state = load_state(run_dir)
        except StateIOError as e:
            raise SummarizeStepError(str(e)) from e

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

        # Save LLM I/O for debugging (pre-call: prompt + meta, no response.txt)
        stage_name = f"summarize_{section_index:02d}"
        effective_model = getattr(llm_provider, "_default_model", "unknown")
        try:
            save_llm_io(
                run_dir,
                stage_name,
                rendered_prompt,
                None,
                meta={
                    "status": "pending",
                    "provider": llm_provider.provider_name,
                    "model": effective_model,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
        except OSError as e:
            logger.warning(f"Failed to save prompt for {stage_name}: {e}")

        # Call LLM provider
        try:
            result = llm_provider.generate(
                rendered_prompt,
                step=f"summarize_{section_index:02d}",
                temperature=0.5,  # Lower temperature for summarization
            )
        except LLMProviderError as e:
            # On error: meta with error info, no response.txt (do not swallow write failures)
            save_llm_io(
                run_dir,
                stage_name,
                rendered_prompt,
                None,
                meta={
                    "status": "error",
                    "provider": llm_provider.provider_name,
                    "model": effective_model,
                    "error": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
            raise SummarizeStepError(f"LLM provider error: {e}") from e

        # Save LLM response (success: prompt, response, meta, raw_response)
        try:
            save_llm_io(
                run_dir,
                stage_name,
                rendered_prompt,
                result.content,
                meta={
                    "status": "success",
                    "provider": result.provider,
                    "model": result.model,
                    "prompt_tokens": result.prompt_tokens,
                    "completion_tokens": result.completion_tokens,
                    "total_tokens": result.total_tokens,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                raw_response=result.raw_response,
            )
        except OSError as e:
            logger.warning(f"Failed to save response for {stage_name}: {e}")

        # Log response diagnostics
        logger.info(
            f"Summarize {section_index} step LLM response: length={len(result.content)} chars, "
            f"first 200 chars: {result.content[:200]!r}"
        )

        # Parse JSON response
        try:
            summary_data = json.loads(result.content)
        except json.JSONDecodeError as e:
            raise SummarizeStepError(f"Invalid JSON in LLM response: {e}") from e

        # Ensure section_id matches
        summary_data["section_id"] = section_id

        # Validate against schema
        if schema_base is None:
            # Default to src/llm_storytell/schemas relative to project root
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
            schema_base_path = project_root / "src" / "llm_storytell" / "schemas"
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
        def updater(s: dict[str, Any]) -> None:
            if "summaries" not in s:
                s["summaries"] = []
            s["summaries"].append(summary_data)
            s["continuity_ledger"] = updated_ledger
            s["token_usage"].append(token_usage_dict)

        try:
            update_state_atomic(run_dir, updater)
        except StateIOError as e:
            raise SummarizeStepError(str(e)) from e

    except SummarizeStepError:
        raise
    except Exception as e:
        raise SummarizeStepError(f"Unexpected error in summarize step: {e}") from e
