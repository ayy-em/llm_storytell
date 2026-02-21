"""Copy final deliverable to runs/book/ with canonical naming (additive, best-effort)."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from llm_storytell.logging import RunLogger
from llm_storytell.pipeline.state import StateIOError, load_inputs, load_state


def _sanitize(s: str) -> str:
    """Replace characters unsafe in filenames with underscore."""
    if not s or not isinstance(s, str):
        return "unknown"
    return re.sub(r"[^\w\-.]", "_", s.strip()).strip(".") or "unknown"


def _run_id_to_dd_mm_yy(run_id: str) -> tuple[str, str, str]:
    """Parse run-YYYYMMDD-HHMMSS to (dd, mm, yy) as two-digit strings. ('01','01','00') if not matching."""
    if not run_id or not isinstance(run_id, str):
        return "01", "01", "00"
    m = re.match(r"run-(\d{4})(\d{2})(\d{2})", run_id.strip())
    if not m:
        return "01", "01", "00"
    yyyy, mm, dd = m.group(1), m.group(2), m.group(3)
    yy = yyyy[-2:] if len(yyyy) >= 2 else "00"
    return dd, mm, yy


def _book_basename_tts(run_dir: Path) -> str:
    """Build {DD-MM-YY}_{app}_{model}_{tts_voice}.mp3 from run_dir."""
    dd, mm, yy = "01", "01", "00"
    app_name = "unknown"
    model = "unknown"
    tts_voice = "unknown"
    try:
        inputs_data = load_inputs(run_dir)
        app_name = str(inputs_data.get("app") or "unknown").strip()
        model = str(inputs_data.get("model") or "unknown").strip()
        run_id = inputs_data.get("run_id") or run_dir.name
        dd, mm, yy = _run_id_to_dd_mm_yy(str(run_id))
    except StateIOError:
        pass
    try:
        state = load_state(run_dir)
        tts_cfg = state.get("tts_config") or {}
        tts_voice = str(tts_cfg.get("tts_voice") or "unknown").strip()
    except StateIOError:
        pass
    return f"{dd}-{mm}-{yy}_{_sanitize(app_name)}_{_sanitize(model)}_{_sanitize(tts_voice)}.mp3"


def _book_basename_no_tts(run_dir: Path) -> str:
    """Build {DD-MM-YY}_{app}_{model}.pdf from run_dir."""
    dd, mm, yy = "01", "01", "00"
    app_name = "unknown"
    model = "unknown"
    try:
        inputs_data = load_inputs(run_dir)
        app_name = str(inputs_data.get("app") or "unknown").strip()
        model = str(inputs_data.get("model") or "unknown").strip()
        run_id = inputs_data.get("run_id") or run_dir.name
        dd, mm, yy = _run_id_to_dd_mm_yy(str(run_id))
    except StateIOError:
        pass
    return f"{dd}-{mm}-{yy}_{_sanitize(app_name)}_{_sanitize(model)}.pdf"


def copy_tts_deliverable_to_book(
    run_dir: Path,
    base_dir: Path,
    logger: RunLogger,
) -> None:
    """Copy the final TTS artifact (artifacts/story-*.mp3) to runs/book/ with canonical name.

    Best-effort: on failure logs error and returns without raising.
    """
    run_dir = run_dir.resolve()
    base_dir = base_dir.resolve()
    try:
        from llm_storytell.steps.audio_prep import (
            _get_app_name,
            _voiceover_artifact_filename,
        )

        app_name = _get_app_name(run_dir)
        artifact_name = _voiceover_artifact_filename(run_dir, app_name, ".mp3")
        src = run_dir / "artifacts" / artifact_name
        if not src.is_file():
            logger.error(f"Book copy skipped: TTS artifact not found: {src}")
            return
        book_dir = base_dir / "runs" / "book"
        book_dir.mkdir(parents=True, exist_ok=True)
        dest_name = _book_basename_tts(run_dir)
        dest = book_dir / dest_name
        shutil.copy2(src, dest)
        logger.info(f"Deliverable copied to runs/book/{dest_name}")
    except Exception as e:
        logger.error(f"Book copy failed: {e}")


def _markdown_to_pdf(md_content: str, out_path: Path) -> None:
    """Convert markdown string to PDF at out_path using markdown + weasyprint."""
    import markdown
    from weasyprint import HTML

    html_body = markdown.markdown(md_content)
    html_doc = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'/>"
        "<style>@page { size: A4; margin: 2cm; } body { font-family: serif; font-size: 12pt; }</style>"
        "</head><body>"
        f"{html_body}"
        "</body></html>"
    )
    HTML(string=html_doc).write_pdf(out_path)


def copy_no_tts_deliverable_to_book(
    run_dir: Path,
    base_dir: Path,
    logger: RunLogger,
) -> None:
    """Convert final_script.md to PDF and write to runs/book/ with canonical name.

    Best-effort: on failure logs error and returns without raising.
    """
    run_dir = run_dir.resolve()
    base_dir = base_dir.resolve()
    try:
        state = load_state(run_dir)
        script_path_rel = state.get("final_script_path") or "artifacts/final_script.md"
        src = run_dir / script_path_rel
        if not src.is_file():
            logger.error(f"Book copy skipped: final script not found: {src}")
            return
        md_content = src.read_text(encoding="utf-8")
        book_dir = base_dir / "runs" / "book"
        book_dir.mkdir(parents=True, exist_ok=True)
        dest_name = _book_basename_no_tts(run_dir)
        dest = book_dir / dest_name
        _markdown_to_pdf(md_content, dest)
        logger.info(f"Deliverable copied to runs/book/{dest_name}")
    except Exception as e:
        logger.error(f"Book copy failed: {e}")
