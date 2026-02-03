"""LLM-TTS pipeline step: chunk final script and synthesize to audio segments."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from llm_storytell.logging import RunLogger
from llm_storytell.tts_providers import TTSProvider, TTSProviderError


class LLMTTSStepError(Exception):
    """Raised when the LLM-TTS step fails."""

    pass


# Chunking constants
MIN_WORDS = 300
MAX_WORDS = 500
MAX_SEGMENTS = 45


def _word_spans(text: str) -> list[re.Match[str]]:
    """Return list of regex matches for non-whitespace (words) in order."""
    return list(re.finditer(r"\S+", text))


def _chunk_text(
    text: str,
    min_words: int = MIN_WORDS,
    max_words: int = MAX_WORDS,
    max_segments: int = MAX_SEGMENTS,
) -> tuple[list[str], list[bool]]:
    """Split text into segments of 700–1000 words, cutting at first newline after 700.

    Returns:
        (segments, imperfect_flags): list of segment strings and per-segment
        True if cut was at 1000 with no newline (imperfect split).
    """
    text = text.strip()
    if not text:
        return [], []

    words = _word_spans(text)
    n = len(words)
    if n == 0:
        return [], []

    segments: list[str] = []
    imperfect: list[bool] = []
    i = 0

    while i < n:
        start_char = words[i].start()
        j_700 = min(i + min_words, n)
        j_1000 = min(i + max_words, n)
        end_700 = words[j_700 - 1].end() if j_700 > i else start_char
        end_1000 = words[j_1000 - 1].end() if j_1000 > i else end_700

        newline_pos = text.find("\n", end_700)
        if newline_pos != -1 and newline_pos < end_1000:
            cut = newline_pos + 1
            segment_text = text[start_char:cut]
            segments.append(segment_text)
            imperfect.append(False)
            while i < n and words[i].start() < cut:
                i += 1
        else:
            cut = end_1000
            segment_text = text[start_char:cut]
            segments.append(segment_text)
            imperfect.append(True)
            i = j_1000

    if len(segments) > max_segments:
        merged = segments[: max_segments - 1]
        merged.append("\n\n".join(segments[max_segments - 1 :]))
        segments = merged
        imperfect = imperfect[: max_segments - 1] + [any(imperfect[max_segments - 1 :])]

    return segments, imperfect


def _load_final_script(run_dir: Path) -> str:
    """Load final script from run_dir (artifacts/final_script.md or state path)."""
    from llm_storytell.pipeline.state import StateIOError, load_state

    path_from_state: str | None = None
    try:
        state = load_state(run_dir)
        path_from_state = state.get("final_script_path")
    except StateIOError:
        pass

    if path_from_state:
        script_path = run_dir / path_from_state
    else:
        script_path = run_dir / "artifacts" / "final_script.md"

    if not script_path.exists():
        raise LLMTTSStepError(f"Final script not found: {script_path}")

    try:
        return script_path.read_text(encoding="utf-8")
    except OSError as e:
        raise LLMTTSStepError(f"Error reading final script: {e}") from e


def execute_llm_tts_step(
    run_dir: Path,
    tts_provider: TTSProvider,
    logger: RunLogger,
    *,
    tts_model: str | None = None,
    tts_voice: str | None = None,
    audio_ext: str = "mp3",
) -> None:
    """Chunk the final script and synthesize each segment to audio.

    Reads artifacts/final_script.md (or state.final_script_path), chunks into
    700–1000 word segments (cut at first newline after 700; if none by 1000,
    cut at 1000 and log warning). Enforces 1 ≤ segments ≤ 22. Writes
    tts/prompts/segment_NN.txt and tts/outputs/segment_NN.<audio_ext>, logs
    progress and cumulative token usage, and appends TTS usage to
    state.tts_token_usage.

    Args:
        run_dir: Run directory (runs/<run_id>/).
        tts_provider: TTS provider instance.
        logger: Run logger.
        tts_model: Optional model override for TTS.
        tts_voice: Optional voice override for TTS.
        audio_ext: Audio file extension (e.g. mp3).

    Raises:
        LLMTTSStepError: On missing input, chunking failure, or TTS error.
    """
    run_dir = run_dir.resolve()
    text = _load_final_script(run_dir)
    segments, imperfect_flags = _chunk_text(text)

    if len(segments) < 1:
        raise LLMTTSStepError("Chunking produced no segments")

    if len(segments) > MAX_SEGMENTS:
        raise LLMTTSStepError(
            f"Chunking produced {len(segments)} segments; max is {MAX_SEGMENTS}"
        )

    prompts_dir = run_dir / "tts" / "prompts"
    outputs_dir = run_dir / "tts" / "outputs"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)

    from llm_storytell.pipeline.state import (
        StateIOError,
        load_state,
        update_state_atomic,
    )

    total_text_prompt = 0
    total_text_completion = 0
    try:
        s = load_state(run_dir)
        for entry in s.get("token_usage") or []:
            if isinstance(entry, dict):
                total_text_prompt += entry.get("prompt_tokens", 0) or 0
                total_text_completion += entry.get("completion_tokens", 0) or 0
    except StateIOError:
        pass

    tts_usage_entries: list[dict[str, Any]] = []
    tts_prompt_sum = 0
    tts_completion_sum = 0
    cumulative_characters = 0
    num_segments = len(segments)

    for idx, (segment_text, is_imperfect) in enumerate(zip(segments, imperfect_flags)):
        seg_num = idx + 1
        input_characters = len(segment_text)
        cumulative_characters += input_characters

        logger.info(f"TTS segment {seg_num}/{num_segments}")
        if is_imperfect:
            logger.warning(
                f"TTS segment {seg_num}: no newline found by {MAX_WORDS} words; "
                "cut at max words"
            )

        prompt_path = prompts_dir / f"segment_{seg_num:02d}.txt"
        prompt_path.write_text(segment_text, encoding="utf-8")
        logger.log_artifact_write(
            Path("tts/prompts") / prompt_path.name, prompt_path.stat().st_size
        )

        try:
            result = tts_provider.synthesize(
                segment_text,
                model=tts_model,
                voice=tts_voice,
            )
        except TTSProviderError as e:
            raise LLMTTSStepError(
                f"TTS synthesis failed for segment {seg_num}: {e}"
            ) from e

        out_path = outputs_dir / f"segment_{seg_num:02d}.{audio_ext}"
        out_path.write_bytes(result.audio)
        logger.log_artifact_write(
            Path("tts/outputs") / out_path.name, out_path.stat().st_size
        )

        pt = result.prompt_tokens or 0
        ct = result.completion_tokens or 0
        tt = result.total_tokens or (pt + ct)
        tts_prompt_sum += pt
        tts_completion_sum += ct
        tts_usage_entries.append(
            {
                "step": f"tts_{seg_num:02d}",
                "provider": result.provider,
                "model": result.model,
                "prompt_tokens": pt,
                "completion_tokens": ct,
                "total_tokens": tt,
                "input_characters": input_characters,
            }
        )
        logger.log_tts_character_usage(
            step=f"tts_{seg_num:02d}",
            provider=result.provider,
            model=result.model,
            input_characters=input_characters,
            cumulative_characters=cumulative_characters,
        )
        print(
            f"[llm_storytell] TTS segment {seg_num}: {input_characters:,} characters "
            f"(cumulative: {cumulative_characters:,})",
            flush=True,
        )
        logger.log_token_usage(
            step=f"tts_{seg_num:02d}",
            provider=result.provider,
            model=result.model,
            prompt_tokens=pt,
            completion_tokens=ct,
            total_tokens=tt,
        )

    def updater(s: dict[str, Any]) -> None:
        s.setdefault("tts_token_usage", []).extend(tts_usage_entries)

    try:
        update_state_atomic(run_dir, updater)
    except StateIOError as e:
        raise LLMTTSStepError(str(e)) from e

    total_text_tokens = total_text_prompt + total_text_completion
    total_tts_tokens = tts_prompt_sum + tts_completion_sum
    total_tokens = total_text_tokens + total_tts_tokens
    logger.log_tts_cumulative(
        response_prompt_tokens=total_text_prompt,
        response_completion_tokens=total_text_completion,
        tts_prompt_tokens=tts_prompt_sum,
        total_text_tokens=total_text_tokens,
        total_tts_tokens=total_tts_tokens,
        total_tokens=total_tokens,
    )
