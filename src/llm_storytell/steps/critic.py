"""Critic step for the pipeline.

Consolidates and corrects the full draft by reviewing all sections,
identifying issues, and producing a final script with an editor report.
"""

import json
import re
import tempfile
from pathlib import Path
from typing import Any

import yaml

from ..context import ContextLoaderError, build_prompt_context_vars
from ..llm import LLMProvider, LLMProviderError
from ..llm.token_tracking import record_token_usage
from ..logging import RunLogger
from ..prompt_render import MissingVariableError, TemplateNotFoundError, render_prompt
from ..schemas import SchemaValidationError, validate_json_schema


class CriticStepError(Exception):
    """Raised when critic step execution fails."""

    pass


def _load_state(run_dir: Path) -> dict[str, Any]:
    """Load state.json from run directory.

    Args:
        run_dir: Path to the run directory.

    Returns:
        State dictionary.

    Raises:
        CriticStepError: If state.json cannot be loaded.
    """
    state_path = run_dir / "state.json"
    if not state_path.exists():
        raise CriticStepError(f"State file not found: {state_path}")

    try:
        with state_path.open(encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise CriticStepError(f"Invalid JSON in state.json: {e}") from e
    except OSError as e:
        raise CriticStepError(f"Error reading state.json: {e}") from e


def _strip_frontmatter(content: str) -> str:
    """Strip YAML frontmatter from markdown content.

    Only strips valid YAML frontmatter at the very top of the content.
    If frontmatter is malformed or missing, raises an error.

    Args:
        content: Markdown content with frontmatter.

    Returns:
        Markdown content without frontmatter.

    Raises:
        CriticStepError: If frontmatter is malformed or missing.
    """
    # Match YAML frontmatter between --- markers at the start
    frontmatter_pattern = r"^---\s*\n(.*?)\n---\s*\n(.*)$"
    match = re.match(frontmatter_pattern, content, re.DOTALL)

    if not match:
        raise CriticStepError(
            "Section content missing valid YAML frontmatter "
            "(expected --- markers at the top)"
        )

    frontmatter_text = match.group(1)
    markdown_body = match.group(2)

    # Validate that frontmatter is valid YAML
    try:
        yaml.safe_load(frontmatter_text)
    except yaml.YAMLError as e:
        raise CriticStepError(f"Invalid YAML in frontmatter: {e}") from e

    return markdown_body


def _load_all_sections(run_dir: Path, expected_section_count: int) -> str:
    """Load and concatenate all section artifacts into a full draft.

    Loads all section files (20_section_<NN>.md) in order, strips frontmatter,
    and concatenates them into a single draft.

    Args:
        run_dir: Path to the run directory.
        expected_section_count: Expected number of sections (from outline length).

    Returns:
        Full draft text (all sections concatenated).

    Raises:
        CriticStepError: If sections are missing, numbering has gaps, or files
            cannot be read.
    """
    artifacts_dir = run_dir / "artifacts"
    if not artifacts_dir.exists():
        raise CriticStepError(
            f"Artifacts directory not found: {artifacts_dir}. "
            "Pipeline step 'section' must be completed first."
        )

    # Find all section files
    section_pattern = re.compile(r"^20_section_(\d+)\.md$")
    section_files: list[tuple[int, Path]] = []

    for file_path in artifacts_dir.iterdir():
        if not file_path.is_file():
            continue
        match = section_pattern.match(file_path.name)
        if match:
            section_num = int(match.group(1))
            section_files.append((section_num, file_path))

    if not section_files:
        raise CriticStepError(
            f"No section artifacts found in {artifacts_dir}. "
            "Pipeline step 'section' must be completed first. "
            "Expected files: 20_section_01.md, 20_section_02.md, ..."
        )

    # Sort by section number
    section_files.sort(key=lambda x: x[0])

    # Check for gaps in numbering based on expected count
    expected_nums = set(range(1, expected_section_count + 1))
    actual_nums = {num for num, _ in section_files}
    missing_nums = sorted(expected_nums - actual_nums)

    if missing_nums:
        missing_list = ", ".join(str(n) for n in missing_nums)
        raise CriticStepError(
            f"Section numbering has gaps. Missing section indices: {missing_list}. "
            f"Found sections: {sorted(actual_nums)}. "
            f"Expected {expected_section_count} sections based on outline. "
            "All sections must be generated before running the critic step. "
            "Check that the 'section' pipeline step completed successfully."
        )

    # Load and concatenate sections
    draft_parts: list[str] = []
    for section_num, file_path in section_files:
        try:
            content = file_path.read_text(encoding="utf-8")
        except OSError as e:
            raise CriticStepError(
                f"Error reading section artifact {file_path.name} "
                f"(section {section_num}): {e}. "
                "Pipeline step 'section' may have failed partially."
            ) from e

        try:
            body = _strip_frontmatter(content)
        except CriticStepError as e:
            raise CriticStepError(
                f"Error processing section {section_num} ({file_path.name}): {e}"
            ) from e

        draft_parts.append(body)

    return "\n\n".join(draft_parts)


def _repair_json_quotes(json_str: str) -> str:
    """Attempt to repair JSON with unescaped quotes in string values.

    Uses a state machine to track when we're inside a string value and
    escapes unescaped quotes that appear within string content.

    Args:
        json_str: JSON string that may have unescaped quotes.

    Returns:
        Repaired JSON string.
    """
    result = []
    i = 0
    in_string = False

    while i < len(json_str):
        char = json_str[i]

        # Handle escape sequences
        if char == "\\" and in_string:
            # Check if this is a valid escape sequence
            if i + 1 < len(json_str):
                next_char = json_str[i + 1]
                # Valid escape sequences in JSON: \" \\ \/ \b \f \n \r \t \uXXXX
                if next_char in ('"', "\\", "/", "b", "f", "n", "r", "t", "u"):
                    result.append(char)
                    result.append(next_char)
                    i += 2
                    continue
                # If not a valid escape, treat backslash as literal (shouldn't happen in valid JSON)
                result.append("\\")
                result.append(next_char)
                i += 2
                continue
            else:
                # Backslash at end - treat as literal
                result.append(char)
                i += 1
                continue

        # Handle quote characters
        if char == '"':
            if in_string:
                # We're in a string - check if this is a closing quote
                # by looking for JSON structure after it
                j = i + 1
                # Skip whitespace
                while j < len(json_str) and json_str[j] in " \t\n\r":
                    j += 1
                if j < len(json_str):
                    next_non_ws = json_str[j]
                    # If followed by structure chars, it's a closing quote
                    if next_non_ws in (":", ",", "}", "]"):
                        in_string = False
                        result.append(char)
                        i += 1
                        continue
                # Otherwise, it's likely an unescaped quote in content
                result.append("\\")
                result.append(char)
            else:
                # Opening quote
                in_string = True
                result.append(char)
            i += 1
            continue

        result.append(char)
        i += 1

    return "".join(result)


def _extract_json_from_response(content: str) -> dict[str, Any]:
    """Extract JSON from LLM response, handling markdown code blocks and common JSON errors.

    Args:
        content: Raw LLM response content.

    Returns:
        Parsed JSON dictionary.

    Raises:
        CriticStepError: If JSON cannot be extracted or parsed.
    """
    import re

    # Try direct JSON parse first
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code blocks
    # Match JSON in ```json ... ``` or ``` ... ``` blocks
    code_block_pattern = r"```(?:json)?\s*\n(.*?)```"
    match = re.search(code_block_pattern, content, re.DOTALL)
    if match:
        extracted = match.group(1)
        try:
            return json.loads(extracted)
        except json.JSONDecodeError:
            # Try repairing quotes in extracted JSON
            try:
                repaired = _repair_json_quotes(extracted)
                return json.loads(repaired)
            except (json.JSONDecodeError, Exception):
                pass

    # Try finding JSON object boundaries
    # Find first { and last }
    first_brace = content.find("{")
    last_brace = content.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        json_candidate = content[first_brace : last_brace + 1]
        try:
            return json.loads(json_candidate)
        except json.JSONDecodeError:
            # Try repairing quotes
            try:
                repaired = _repair_json_quotes(json_candidate)
                return json.loads(repaired)
            except (json.JSONDecodeError, Exception):
                pass

    # Final attempt: try repairing the entire content
    try:
        repaired = _repair_json_quotes(content)
        return json.loads(repaired)
    except (json.JSONDecodeError, Exception):
        pass

    # If all else fails, try to get more diagnostic info
    # Attempt one more parse to capture the exact error location
    try:
        json.loads(content)
    except json.JSONDecodeError as e:
        error_pos = getattr(e, "pos", None)
        if error_pos is not None and error_pos < len(content):
            # Show context around the error
            start = max(0, error_pos - 100)
            end = min(len(content), error_pos + 100)
            context = content[start:end]
            raise CriticStepError(
                f"Could not extract valid JSON from LLM response. "
                f"JSON error at position {error_pos}: {e.msg}. "
                f"Context around error: {context!r}"
            ) from e

    # Fallback error message
    snippet = content[:500] if len(content) > 500 else content
    raise CriticStepError(
        f"Could not extract valid JSON from LLM response. "
        f"Response (first 500 chars): {snippet!r}"
    )


def _validate_llm_response(response_data: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Validate LLM response structure strictly.

    Enforces:
    - Top-level object
    - Required keys: final_script, editor_report
    - No extra keys unless explicitly allowed
    - editor_report must be a dict

    Args:
        response_data: Parsed JSON response from LLM.

    Returns:
        Tuple of (final_script, editor_report).

    Raises:
        CriticStepError: If response structure is invalid.
    """
    if not isinstance(response_data, dict):
        raise CriticStepError(
            "LLM response must be a top-level JSON object, "
            f"got {type(response_data).__name__}"
        )

    # Check required keys
    required_keys = {"final_script", "editor_report"}
    missing_keys = required_keys - set(response_data.keys())
    if missing_keys:
        raise CriticStepError(
            f"LLM response missing required keys: {sorted(missing_keys)}. "
            f"Found keys: {sorted(response_data.keys())}"
        )

    # Check for extra keys (strict enforcement)
    allowed_keys = {"final_script", "editor_report"}
    extra_keys = set(response_data.keys()) - allowed_keys
    if extra_keys:
        raise CriticStepError(
            f"LLM response contains extra keys (not allowed): {sorted(extra_keys)}. "
            f"Allowed keys: {sorted(allowed_keys)}"
        )

    # Validate types
    final_script = response_data.get("final_script")
    if not isinstance(final_script, str):
        raise CriticStepError(
            f"final_script must be a string, got {type(final_script).__name__}"
        )

    editor_report = response_data.get("editor_report")
    if not isinstance(editor_report, dict):
        raise CriticStepError(
            f"editor_report must be a dictionary, got {type(editor_report).__name__}"
        )

    return final_script, editor_report


def _update_state(
    run_dir: Path,
    final_script_path: str,
    editor_report_path: str,
    token_usage: dict[str, Any],
) -> None:
    """Update state.json with final script path, editor report path, and token usage.

    Uses atomic write (temp file + rename) to avoid partial state.

    Args:
        run_dir: Path to the run directory.
        final_script_path: Path to final_script.md (relative to run_dir, as string).
        editor_report_path: Path to editor_report.json (relative to run_dir, as string).
        token_usage: Token usage dictionary to append.

    Raises:
        CriticStepError: If state update fails.
    """
    state_path = run_dir / "state.json"

    # Load current state
    try:
        with state_path.open(encoding="utf-8") as f:
            state = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise CriticStepError(f"Error reading state for update: {e}") from e

    # Update state: store paths and append token usage
    state["final_script_path"] = final_script_path
    state["editor_report_path"] = editor_report_path
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
        raise CriticStepError(f"Error writing updated state: {e}") from e


def execute_critic_step(
    run_dir: Path,
    context_dir: Path,
    prompts_dir: Path,
    llm_provider: LLMProvider,
    logger: RunLogger,
    schema_base: Path | None = None,
) -> None:
    """Execute the critic step.

    Loads all sections, combines them into a full draft, calls LLM to review
    and correct, then produces final_script.md and editor_report.json.

    Args:
        run_dir: Path to the run directory.
        context_dir: Path to the app's context directory.
        prompts_dir: Path to the app's prompts directory.
        llm_provider: LLM provider instance.
        logger: Run logger instance.
        schema_base: Base path for schema resolution. If None, uses
            src/llm_storytell/schemas relative to run_dir.

    Raises:
        CriticStepError: If any step fails.
    """
    logger.log_stage_start("critic")

    try:
        # Load state
        state = _load_state(run_dir)

        # Validate outline exists
        outline = state.get("outline", [])
        if not outline:
            raise CriticStepError("Outline not found in state.json")

        # Load all sections and combine into full draft
        expected_section_count = len(outline)
        full_draft = _load_all_sections(run_dir, expected_section_count)

        # Get seed from state
        seed = state.get("seed")
        if not seed:
            raise CriticStepError("Seed not found in state.json")

        # Load context files (shared contract: lore_bible, style, location, characters)
        try:
            context_vars = build_prompt_context_vars(context_dir, state)
        except ContextLoaderError as e:
            raise CriticStepError(f"Context loading failed: {e}") from e

        # Load and render prompt template
        prompt_path = prompts_dir / "30_critic.md"
        if not prompt_path.exists():
            raise CriticStepError(f"Prompt template not found: {prompt_path}")

        prompt_vars = {
            "seed": seed,
            "full_draft": full_draft,
            "lore_bible": context_vars["lore_bible"],
            "style_rules": context_vars["style_rules"],
            "outline": json.dumps(outline, indent=2),
            "location_context": context_vars["location_context"],
            "character_context": context_vars["character_context"],
        }

        try:
            rendered_prompt = render_prompt(prompt_path, prompt_vars)
        except TemplateNotFoundError as e:
            raise CriticStepError(f"Prompt template not found: {e}") from e
        except MissingVariableError as e:
            raise CriticStepError(f"Missing variables in prompt template: {e}") from e

        # Call LLM provider with extended timeout for critic step (300 seconds)
        try:
            result = llm_provider.generate(
                rendered_prompt,
                step="critic",
                temperature=0.7,
                timeout=300,
            )
        except LLMProviderError as e:
            raise CriticStepError(f"LLM provider error: {e}") from e

        # Parse JSON response (with fallback extraction)
        try:
            response_data = _extract_json_from_response(result.content)
        except CriticStepError:
            raise
        except Exception as e:
            raise CriticStepError(
                f"Invalid JSON in LLM response: {e}. "
                "Response must be valid JSON with 'final_script' and 'editor_report' keys."
            ) from e

        # Validate response structure strictly
        try:
            final_script, editor_report = _validate_llm_response(response_data)
        except CriticStepError:
            raise
        except Exception as e:
            raise CriticStepError(
                f"Error validating LLM response structure: {e}"
            ) from e

        # Validate editor_report against schema
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

        schema_path = schema_base_path / "critic_report.schema.json"
        try:
            validate_json_schema(editor_report, schema_path, logger)
        except SchemaValidationError as e:
            raise CriticStepError(f"Schema validation failed: {e}") from e

        # Write artifacts
        artifacts_dir = run_dir / "artifacts"
        artifacts_dir.mkdir(exist_ok=True)

        # Write final_script.md
        final_script_path = artifacts_dir / "final_script.md"
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
                f.write(final_script)

            temp_file.replace(final_script_path)
            temp_file = None

            # Log artifact creation
            size_bytes = final_script_path.stat().st_size
            logger.log_artifact_write(Path("artifacts") / "final_script.md", size_bytes)
        except OSError as e:
            if temp_file and temp_file.exists():
                temp_file.unlink()
            raise CriticStepError(f"Error writing final_script.md: {e}") from e

        # Write editor_report.json
        editor_report_path = artifacts_dir / "editor_report.json"
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
                json.dump(editor_report, f, indent=2, ensure_ascii=False)

            temp_file.replace(editor_report_path)
            temp_file = None

            # Log artifact creation
            size_bytes = editor_report_path.stat().st_size
            logger.log_artifact_write(
                Path("artifacts") / "editor_report.json", size_bytes
            )
        except OSError as e:
            if temp_file and temp_file.exists():
                temp_file.unlink()
            raise CriticStepError(f"Error writing editor_report.json: {e}") from e

        # Record token usage
        token_usage_dict = record_token_usage(
            logger=logger,
            step="critic",
            provider=result.provider,
            model=result.model,
            prompt_tokens=result.prompt_tokens or 0,
            completion_tokens=result.completion_tokens or 0,
            total_tokens=result.total_tokens,
        )

        # Update state with paths (relative to run_dir, normalized to forward slashes)
        _update_state(
            run_dir,
            Path("artifacts/final_script.md").as_posix(),
            Path("artifacts/editor_report.json").as_posix(),
            token_usage_dict,
        )

        logger.log_stage_end("critic", success=True)

    except CriticStepError:
        logger.log_stage_end("critic", success=False)
        raise
    except Exception as e:
        logger.log_stage_end("critic", success=False)
        raise CriticStepError(f"Unexpected error in critic step: {e}") from e
