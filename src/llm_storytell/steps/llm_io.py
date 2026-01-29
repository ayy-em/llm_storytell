"""Helper functions for capturing LLM prompts and responses."""

from pathlib import Path


def save_llm_io(
    run_dir: Path,
    stage_name: str,
    prompt: str,
    response: str,
) -> None:
    """Save LLM prompt and response to llm_io/<stage_name>/ directory.

    Creates the directory structure if it doesn't exist and writes:
    - prompt.txt: The rendered prompt sent to the LLM
    - response.txt: The raw response from the LLM

    Args:
        run_dir: Path to the run directory.
        stage_name: Name of the pipeline stage (e.g., "outline", "section_00", "critic").
        prompt: The rendered prompt text.
        response: The raw response text from the LLM.

    Raises:
        OSError: If files cannot be written.
    """
    llm_io_dir = run_dir / "llm_io" / stage_name
    llm_io_dir.mkdir(parents=True, exist_ok=True)

    # Write prompt
    prompt_path = llm_io_dir / "prompt.txt"
    prompt_path.write_text(prompt, encoding="utf-8")

    # Write response
    response_path = llm_io_dir / "response.txt"
    response_path.write_text(response, encoding="utf-8")
