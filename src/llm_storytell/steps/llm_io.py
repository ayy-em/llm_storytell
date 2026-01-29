"""Helper functions for capturing LLM prompts and responses."""

import json
from pathlib import Path
from typing import Any

# Keys whose values are redacted when writing raw_response.json
_RAW_RESPONSE_REDACT_KEYS = frozenset(
    k.lower()
    for k in ("api_key", "apikey", "token", "secret", "password", "credential", "auth")
)


def save_llm_io(
    run_dir: Path,
    stage_name: str,
    prompt: str,
    response: str | None = None,
    *,
    meta: dict[str, Any] | None = None,
    raw_response: Any | None = None,
) -> None:
    """Save LLM prompt and optional response/meta/raw to llm_io/<stage_name>/.

    Creates the directory structure if it doesn't exist and writes:
    - prompt.txt: always (the rendered prompt sent to the LLM)
    - response.txt: only when response is provided and non-empty (not written for
      None or empty string, preserving backwards compatibility with "no placeholder"
      behavior)
    - meta.json: when meta is provided (must include status, provider, model; error
      only when status is "error")
    - raw_response.json: when raw_response is provided (sensitive keys redacted)

    Backwards compatibility: existing calls save_llm_io(run_dir, stage_name, prompt, response)
    remain valid. When response is passed and is non-empty, response.txt is written
    as before. Passing response=None or response="" does not write response.txt.

    Args:
        run_dir: Path to the run directory.
        stage_name: Name of the pipeline stage (e.g., "outline", "section_00", "critic").
        prompt: The rendered prompt text.
        response: The raw response text from the LLM. None or empty string: do not
            write response.txt. Non-empty string: write response.txt.
        meta: Optional metadata dict. When provided, must include at least:
            status: "pending" | "success" | "error"
            provider: str (e.g. "openai")
            model: str (when available)
            error: str, only when status is "error"
        raw_response: Optional raw provider response for debugging (keys redacted).

    Raises:
        OSError: If files cannot be written.
    """
    llm_io_dir = run_dir / "llm_io" / stage_name
    llm_io_dir.mkdir(parents=True, exist_ok=True)

    prompt_path = llm_io_dir / "prompt.txt"
    prompt_path.write_text(prompt, encoding="utf-8")

    if response is not None and response.strip() != "":
        response_path = llm_io_dir / "response.txt"
        response_path.write_text(response, encoding="utf-8")

    if meta is not None:
        meta_path = llm_io_dir / "meta.json"
        meta_path.write_text(
            json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    if raw_response is not None:
        try:
            if isinstance(raw_response, dict):
                payload = {
                    k: "[REDACTED]" if k.lower() in _RAW_RESPONSE_REDACT_KEYS else v
                    for k, v in raw_response.items()
                }
            elif isinstance(raw_response, list):
                payload = raw_response
            else:
                payload = {"raw": str(raw_response)}
            raw_path = llm_io_dir / "raw_response.json"
            raw_path.write_text(
                json.dumps(payload, indent=2, default=str, ensure_ascii=False),
                encoding="utf-8",
            )
        except (TypeError, ValueError):
            raw_path = llm_io_dir / "raw_response.json"
            raw_path.write_text(
                json.dumps({"error": "Could not serialize raw response"}, indent=2),
                encoding="utf-8",
            )
