"""Section generation step for the pipeline.

Generates a single narrative section from an outline beat, using rolling
summary and continuity ledger to maintain narrative consistency.
"""

import json
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from src.llm_storytell.continuity import build_rolling_summary, get_continuity_context
from src.llm_storytell.context import ContextLoaderError, build_prompt_context_vars
from src.llm_storytell.llm import LLMProvider, LLMProviderError
from src.llm_storytell.llm.token_tracking import record_token_usage
from src.llm_storytell.logging import RunLogger
from src.llm_storytell.prompt_render import (
    MissingVariableError,
    TemplateNotFoundError,
    render_prompt,
)
from src.llm_storytell.schemas import SchemaValidationError, validate_json_schema
from src.llm_storytell.steps.llm_io import save_llm_io


class SectionStepError(Exception):
    """Raised when section step execution fails."""

    pass


def _load_state(run_dir: Path) -> dict[str, Any]:
    """Load state.json from run directory.

    Args:
        run_dir: Path to the run directory.

    Returns:
        State dictionary.

    Raises:
        SectionStepError: If state.json cannot be loaded.
    """
    state_path = run_dir / "state.json"
    if not state_path.exists():
        raise SectionStepError(f"State file not found: {state_path}")

    try:
        with state_path.open(encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise SectionStepError(f"Invalid JSON in state.json: {e}") from e
    except OSError as e:
        raise SectionStepError(f"Error reading state.json: {e}") from e


def _parse_markdown_with_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Parse markdown content with YAML frontmatter.

    Extracts YAML frontmatter (between --- markers) and the remaining
    markdown content.

    Args:
        content: Full markdown content with frontmatter.

    Returns:
        Tuple of (frontmatter_dict, markdown_body).

    Raises:
        SectionStepError: If frontmatter cannot be parsed.
    """
    # Match YAML frontmatter between --- markers
    frontmatter_pattern = r"^---\s*\n(.*?)\n---\s*\n(.*)$"
    match = re.match(frontmatter_pattern, content, re.DOTALL)

    if not match:
        raise SectionStepError(
            "Section content missing YAML frontmatter (expected --- markers)"
        )

    frontmatter_text = match.group(1)
    markdown_body = match.group(2)

    try:
        frontmatter = yaml.safe_load(frontmatter_text)
        if not isinstance(frontmatter, dict):
            raise SectionStepError("Frontmatter must be a YAML dictionary")
        return frontmatter, markdown_body
    except yaml.YAMLError as e:
        raise SectionStepError(f"Invalid YAML in frontmatter: {e}") from e


def _update_state(
    run_dir: Path,
    section_metadata: dict[str, Any],
    token_usage: dict[str, Any],
) -> None:
    """Update state.json with section metadata and token usage.

    Uses atomic write (temp file + rename) to avoid partial state.

    Args:
        run_dir: Path to the run directory.
        section_metadata: The validated section metadata to append.
        token_usage: Token usage dictionary to append.

    Raises:
        SectionStepError: If state update fails.
    """
    state_path = run_dir / "state.json"

    # Load current state
    try:
        with state_path.open(encoding="utf-8") as f:
            state = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise SectionStepError(f"Error reading state for update: {e}") from e

    # Update state: append section and token usage
    if "sections" not in state:
        state["sections"] = []
    state["sections"].append(section_metadata)
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
        raise SectionStepError(f"Error writing updated state: {e}") from e


def execute_section_step(
    run_dir: Path,
    context_dir: Path,
    prompts_dir: Path,
    llm_provider: LLMProvider,
    logger: RunLogger,
    section_index: int,
    schema_base: Path | None = None,
) -> None:
    """Execute the section generation step for a single outline beat.

    Generates a narrative section from an outline beat, using rolling
    summary and continuity ledger to maintain consistency.

    Args:
        run_dir: Path to the run directory.
        context_dir: Path to the app's context directory.
        prompts_dir: Path to the app's prompts directory.
        llm_provider: LLM provider instance.
        logger: Run logger instance.
        section_index: Zero-based index of the section to generate
            (0 for first section, 1 for second, etc.).
        schema_base: Base path for schema resolution. If None, uses
            src/llm_storytell/schemas relative to run_dir.

    Raises:
        SectionStepError: If any step fails.
    """
    try:
        # Load state
        state = _load_state(run_dir)

        # Validate outline exists
        outline = state.get("outline", [])
        if not outline:
            raise SectionStepError("Outline not found in state.json")
        if section_index < 0 or section_index >= len(outline):
            raise SectionStepError(
                f"Section index {section_index} out of range "
                f"(outline has {len(outline)} beats)"
            )

        # Get the outline beat for this section
        beat = outline[section_index]
        if not isinstance(beat, dict):
            raise SectionStepError(
                f"Invalid outline beat format at index {section_index}"
            )

        # Build rolling summary from existing summaries
        summaries = state.get("summaries", [])
        rolling_summary = build_rolling_summary(summaries)

        # Get continuity context
        continuity_ledger = state.get("continuity_ledger", {})
        continuity_context = get_continuity_context(continuity_ledger)

        # Get seed from state
        seed = state.get("seed")
        if not seed:
            raise SectionStepError("Seed not found in state.json")

        # Load context files (shared contract: lore_bible, style, location, characters)
        try:
            context_vars = build_prompt_context_vars(context_dir, state)
        except ContextLoaderError as e:
            raise SectionStepError(f"Context loading failed: {e}") from e

        # Load and render prompt template
        prompt_path = prompts_dir / "20_section.md"
        if not prompt_path.exists():
            raise SectionStepError(f"Prompt template not found: {prompt_path}")

        # Section ID is 1-based for display
        section_id = section_index + 1

        prompt_vars = {
            "section_id": section_id,
            "section_index": section_index,
            "seed": seed,
            "outline_beat": json.dumps(beat, indent=2),
            "rolling_summary": rolling_summary,
            "continuity_context": continuity_context,
            "lore_bible": context_vars["lore_bible"],
            "style_rules": context_vars["style_rules"],
            "location_context": context_vars["location_context"],
            "character_context": context_vars["character_context"],
        }

        try:
            rendered_prompt = render_prompt(prompt_path, prompt_vars)
        except TemplateNotFoundError as e:
            raise SectionStepError(f"Prompt template not found: {e}") from e
        except MissingVariableError as e:
            raise SectionStepError(f"Missing variables in prompt template: {e}") from e

        # Save LLM I/O for debugging (pre-call: prompt + meta, no response.txt)
        stage_name = f"section_{section_index:02d}"
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
                step=f"section_{section_index:02d}",
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
            raise SectionStepError(f"LLM provider error: {e}") from e

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
            f"Section {section_index} step LLM response: length={len(result.content)} chars, "
            f"first 200 chars: {result.content[:200]!r}"
        )

        # Parse markdown with frontmatter
        try:
            frontmatter, section_text = _parse_markdown_with_frontmatter(result.content)
        except SectionStepError:
            raise
        except Exception as e:
            raise SectionStepError(f"Error parsing section content: {e}") from e

        # Ensure section_id in frontmatter matches
        frontmatter["section_id"] = section_id

        # Extract only schema-required fields for validation
        # The schema only validates metadata, not all frontmatter fields
        schema_fields = {
            "section_id",
            "local_summary",
            "new_entities",
            "new_locations",
            "unresolved_threads",
        }
        metadata_for_validation = {
            k: v for k, v in frontmatter.items() if k in schema_fields
        }

        # Validate frontmatter against schema
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

        schema_path = schema_base_path / "section.schema.json"
        try:
            validate_json_schema(metadata_for_validation, schema_path, logger)
        except SchemaValidationError as e:
            raise SectionStepError(f"Schema validation failed: {e}") from e

        # Reconstruct full section content with frontmatter
        frontmatter_yaml = yaml.dump(
            frontmatter, default_flow_style=False, sort_keys=False
        )
        # Remove trailing newline from yaml.dump output
        frontmatter_yaml = frontmatter_yaml.rstrip()
        full_section_content = f"---\n{frontmatter_yaml}\n---\n\n{section_text}"

        # Write artifact
        artifacts_dir = run_dir / "artifacts"
        artifacts_dir.mkdir(exist_ok=True)
        artifact_filename = f"20_section_{section_id:02d}.md"
        artifact_path = artifacts_dir / artifact_filename

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
                f.write(full_section_content)

            temp_file.replace(artifact_path)
            temp_file = None

            # Log artifact creation
            size_bytes = artifact_path.stat().st_size
            logger.log_artifact_write(Path("artifacts") / artifact_filename, size_bytes)
        except OSError as e:
            if temp_file and temp_file.exists():
                temp_file.unlink()
            raise SectionStepError(f"Error writing section artifact: {e}") from e

        # Record token usage
        token_usage_dict = record_token_usage(
            logger=logger,
            step=f"section_{section_index:02d}",
            provider=result.provider,
            model=result.model,
            prompt_tokens=result.prompt_tokens or 0,
            completion_tokens=result.completion_tokens or 0,
            total_tokens=result.total_tokens,
        )

        # Update state with section metadata
        _update_state(run_dir, frontmatter, token_usage_dict)

    except SectionStepError:
        raise
    except Exception as e:
        raise SectionStepError(f"Unexpected error in section step: {e}") from e
