"""Outline generation step for the pipeline.

Generates a high-level narrative structure (outline beats) from a story seed
and app context, validates the output, and persists it to artifacts and state.
"""

import json
import tempfile
from pathlib import Path
from typing import Any

from ..context import ContextLoaderError, build_prompt_context_vars
from ..llm import LLMProvider, LLMProviderError
from ..llm.token_tracking import record_token_usage
from ..logging import RunLogger
from ..prompt_render import MissingVariableError, TemplateNotFoundError, render_prompt
from ..schemas import SchemaValidationError, validate_json_schema


class OutlineStepError(Exception):
    """Raised when outline step execution fails."""

    pass


def _load_state(run_dir: Path) -> dict[str, Any]:
    """Load state.json from run directory.

    Args:
        run_dir: Path to the run directory.

    Returns:
        State dictionary.

    Raises:
        OutlineStepError: If state.json cannot be loaded.
    """
    state_path = run_dir / "state.json"
    if not state_path.exists():
        raise OutlineStepError(f"State file not found: {state_path}")

    try:
        with state_path.open(encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise OutlineStepError(f"Invalid JSON in state.json: {e}") from e
    except OSError as e:
        raise OutlineStepError(f"Error reading state.json: {e}") from e


def _load_inputs(run_dir: Path) -> dict[str, Any]:
    """Load inputs.json from run directory.

    Args:
        run_dir: Path to the run directory.

    Returns:
        Inputs dictionary.

    Raises:
        OutlineStepError: If inputs.json cannot be loaded.
    """
    inputs_path = run_dir / "inputs.json"
    if not inputs_path.exists():
        raise OutlineStepError(f"Inputs file not found: {inputs_path}")

    try:
        with inputs_path.open(encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise OutlineStepError(f"Invalid JSON in inputs.json: {e}") from e
    except OSError as e:
        raise OutlineStepError(f"Error reading inputs.json: {e}") from e


def _update_state(
    run_dir: Path, outline_data: dict[str, Any], token_usage: dict[str, Any]
) -> None:
    """Update state.json with outline and token usage.

    Uses atomic write (temp file + rename) to avoid partial state.

    Args:
        run_dir: Path to the run directory.
        outline_data: The validated outline data to store.
        token_usage: Token usage dictionary to append.

    Raises:
        OutlineStepError: If state update fails.
    """
    state_path = run_dir / "state.json"

    # Load current state
    try:
        with state_path.open(encoding="utf-8") as f:
            state = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise OutlineStepError(f"Error reading state for update: {e}") from e

    # Update state
    state["outline"] = outline_data.get("beats", [])
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
        raise OutlineStepError(f"Error writing updated state: {e}") from e


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
        state = _load_state(run_dir)
        inputs = _load_inputs(run_dir)

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

        prompt_vars = {
            "seed": seed,
            "lore_bible": context_vars["lore_bible"],
            "style_rules": context_vars["style_rules"],
            "location_context": context_vars["location_context"],
            "character_context": context_vars["character_context"],
            "beats_count": beats_count,
        }

        try:
            rendered_prompt = render_prompt(prompt_path, prompt_vars)
        except TemplateNotFoundError as e:
            raise OutlineStepError(f"Prompt template not found: {e}") from e
        except MissingVariableError as e:
            raise OutlineStepError(f"Missing variables in prompt template: {e}") from e

        # Call LLM provider
        try:
            result = llm_provider.generate(
                rendered_prompt,
                step="outline",
                temperature=0.7,
            )
        except LLMProviderError as e:
            raise OutlineStepError(f"LLM provider error: {e}") from e

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
        _update_state(run_dir, outline_data, token_usage_dict)

    except OutlineStepError:
        raise
    except Exception as e:
        raise OutlineStepError(f"Unexpected error in outline step: {e}") from e
