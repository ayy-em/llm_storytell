"""Outline generation step for the pipeline.

Generates a high-level narrative structure (outline beats) from a story seed
and app context, validates the output, and persists it to artifacts and state.
"""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llm_storytell.context import ContextLoaderError, build_prompt_context_vars
from llm_storytell.llm import LLMProvider, LLMProviderError
from llm_storytell.llm.token_tracking import record_token_usage
from llm_storytell.logging import RunLogger
from llm_storytell.prompt_render import (
    MissingVariableError,
    TemplateNotFoundError,
    UnsupportedPlaceholderError,
    render_prompt,
)
from llm_storytell.schemas import SchemaValidationError, validate_json_schema
from llm_storytell.steps.llm_io import save_llm_io


class OutlineStepError(Exception):
    """Raised when outline step execution fails."""

    pass


def execute_outline_step(
    run_dir: Path,
    context_dir: Path,
    prompts_dir: Path,
    llm_provider: LLMProvider,
    logger: RunLogger,
    schema_base: Path | None = None,
) -> None:
    """Execute the outline generation step.

    Loads context, renders prompt, calls LLM, validates output, and persists
    results to artifacts and state.

    Args:
        run_dir: Path to the run directory.
        context_dir: Path to the app's context directory.
        prompts_dir: Path to the app's prompts directory.
        llm_provider: LLM provider instance.
        logger: Run logger instance.
        schema_base: Base path for schema resolution. If None, uses
            src/llm_storytell/schemas relative to run_dir.

    Raises:
        OutlineStepError: If any step fails.
    """
    try:
        # Load state and inputs
        from llm_storytell.pipeline.state import (
            StateIOError,
            load_inputs,
            load_state,
            update_state_atomic,
        )

        try:
            state = load_state(run_dir)
            inputs = load_inputs(run_dir)
        except StateIOError as e:
            raise OutlineStepError(str(e)) from e

        seed = state.get("seed")
        if not seed:
            raise OutlineStepError("Seed not found in state.json")

        beats_count = inputs.get("beats")
        if beats_count is None:
            raise OutlineStepError("Beats count not found in inputs.json")
        if not isinstance(beats_count, int) or beats_count < 1 or beats_count > 20:
            raise OutlineStepError(f"Invalid beats count: {beats_count} (must be 1-20)")

        # Load context files (shared contract: lore_bible, style, location, characters)
        try:
            context_vars = build_prompt_context_vars(context_dir, state)
        except ContextLoaderError as e:
            raise OutlineStepError(f"Context loading failed: {e}") from e

        # Load and render prompt template
        prompt_path = prompts_dir / "10_outline.md"
        if not prompt_path.exists():
            raise OutlineStepError(f"Prompt template not found: {prompt_path}")

        language = state.get("language", "en")
        prompt_vars = {
            "seed": seed,
            "lore_bible": context_vars["lore_bible"],
            "style_rules": context_vars["style_rules"],
            "location_context": context_vars["location_context"],
            "character_context": context_vars["character_context"],
            "beats_count": beats_count,
            "language": language,
        }

        try:
            rendered_prompt = render_prompt(prompt_path, prompt_vars)
            print("[outline] Prompt rendered successfully")
        except TemplateNotFoundError as e:
            raise OutlineStepError(f"Prompt template not found: {e}") from e
        except MissingVariableError as e:
            raise OutlineStepError(f"Missing variables in prompt template: {e}") from e
        except UnsupportedPlaceholderError as e:
            print(f"[outline] Prompt render failed (unsupported placeholder): {e}")
            raise OutlineStepError(
                f"Invalid placeholder in prompt template: {e}"
            ) from e

        # Save LLM I/O for debugging (pre-call: prompt + meta, no response.txt)
        stage_name = "outline"
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
                step="outline",
                temperature=0.7,
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
            raise OutlineStepError(f"LLM provider error: {e}") from e

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
            f"Outline step LLM response: length={len(result.content)} chars, "
            f"first 200 chars: {result.content[:200]!r}"
        )

        # Parse JSON response
        # Try direct JSON parse first
        content_to_parse = result.content.strip()

        # If wrapped in markdown code block, extract JSON
        if content_to_parse.startswith("```"):
            # Try to extract JSON from markdown code block
            lines = content_to_parse.split("\n")
            # Find first line with ```json or ``` and last ```
            start_idx = None
            end_idx = None
            for i, line in enumerate(lines):
                if line.strip().startswith("```"):
                    if start_idx is None:
                        start_idx = i + 1
                    else:
                        end_idx = i
                        break
            if start_idx is not None and end_idx is not None:
                content_to_parse = "\n".join(lines[start_idx:end_idx]).strip()
                logger.info("Extracted JSON from markdown code block")

        try:
            outline_data = json.loads(content_to_parse)
        except json.JSONDecodeError as e:
            # Log the raw content for debugging
            logger.error(
                f"Failed to parse JSON from LLM response. "
                f"Response length: {len(result.content)} chars. "
                f"First 500 chars: {result.content[:500]}"
            )
            raise OutlineStepError(f"Invalid JSON in LLM response: {e}") from e

        # Pre-validate: check all beats have required fields before schema validation
        beats = outline_data.get("beats", [])
        if not isinstance(beats, list):
            raise OutlineStepError(
                f"Outline 'beats' must be an array, got {type(beats).__name__}"
            )

        for idx, beat in enumerate(beats):
            if not isinstance(beat, dict):
                raise OutlineStepError(
                    f"Beat at index {idx} must be an object, got {type(beat).__name__}"
                )
            missing_fields = []
            if "beat_id" not in beat:
                missing_fields.append("beat_id")
            if "title" not in beat:
                missing_fields.append("title")
            if "summary" not in beat:
                missing_fields.append("summary")
            if missing_fields:
                logger.error(
                    f"Beat at index {idx} missing required fields: {missing_fields}. "
                    f"Beat content: {json.dumps(beat, indent=2)}"
                )
                raise OutlineStepError(
                    f"Beat at index {idx} missing required fields: {missing_fields}"
                )

        # Validate against schema
        if schema_base is None:
            # Default to src/llm_storytell/schemas relative to project root
            # Find project root by looking for SPEC.md or pyproject.toml
            current = Path.cwd()
            project_root = None
            for parent in [current] + list(current.parents):
                if (parent / "SPEC.md").exists() or (
                    parent / "pyproject.toml"
                ).exists():
                    project_root = parent
                    break
            if project_root is None:
                # Fallback: assume we're in src/llm_storytell/steps
                # and go up to project root
                project_root = Path(__file__).parent.parent.parent.parent
            schema_base_path = project_root / "src" / "llm_storytell" / "schemas"
        else:
            schema_base_path = Path(schema_base)

        schema_path = schema_base_path / "outline.schema.json"
        try:
            validate_json_schema(outline_data, schema_path, logger)
        except SchemaValidationError as e:
            raise OutlineStepError(f"Schema validation failed: {e}") from e

        # Validate beat count matches requested count
        beats = outline_data.get("beats", [])
        if len(beats) != beats_count:
            error_msg = (
                f"Outline has {len(beats)} beats, but {beats_count} were requested"
            )
            logger.log_validation_failure(step="outline", error=error_msg)
            raise OutlineStepError(error_msg)

        # Write artifact
        artifacts_dir = run_dir / "artifacts"
        artifacts_dir.mkdir(exist_ok=True)
        artifact_path = artifacts_dir / "10_outline.json"

        # Atomic write
        temp_file = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=artifacts_dir,
                delete=False,
                suffix=".tmp",
            ) as f:
                temp_file = Path(f.name)
                json.dump(outline_data, f, indent=2, ensure_ascii=False)

            temp_file.replace(artifact_path)
            temp_file = None

            # Log artifact creation
            size_bytes = artifact_path.stat().st_size
            logger.log_artifact_write(Path("artifacts") / "10_outline.json", size_bytes)
        except OSError as e:
            if temp_file and temp_file.exists():
                temp_file.unlink()
            raise OutlineStepError(f"Error writing outline artifact: {e}") from e

        # Record token usage
        token_usage_dict = record_token_usage(
            logger=logger,
            step="outline",
            provider=result.provider,
            model=result.model,
            prompt_tokens=result.prompt_tokens or 0,
            completion_tokens=result.completion_tokens or 0,
            total_tokens=result.total_tokens,
        )

        # Update state
        def updater(s: dict[str, Any]) -> None:
            s["outline"] = outline_data.get("beats", [])
            s["token_usage"].append(token_usage_dict)

        try:
            update_state_atomic(run_dir, updater)
        except StateIOError as e:
            raise OutlineStepError(str(e)) from e

    except OutlineStepError:
        raise
    except Exception as e:
        raise OutlineStepError(f"Unexpected error in outline step: {e}") from e
