"""Tests for deliverable-to-book copy (runs/book/ naming and copy/convert)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from llm_storytell.logging import RunLogger
from llm_storytell.pipeline.deliverable_to_book import (
    _book_basename_no_tts,
    _book_basename_tts,
    copy_no_tts_deliverable_to_book,
    copy_tts_deliverable_to_book,
)
from llm_storytell.steps.audio_prep import _voiceover_artifact_filename


def _run_dir_tts(
    tmp_path: Path,
    *,
    app: str = "my_app",
    model: str = "gpt-4.1-mini",
    run_id: str = "run-20250209-120000",
    tts_voice: str = "onyx",
) -> Path:
    """Create a minimal run_dir with inputs, state, and TTS artifact."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "inputs.json").write_text(
        json.dumps({"app": app, "model": model, "run_id": run_id}),
        encoding="utf-8",
    )
    (run_dir / "state.json").write_text(
        json.dumps(
            {
                "tts_config": {
                    "tts_model": "openai-tts",
                    "tts_voice": tts_voice,
                },
            }
        ),
        encoding="utf-8",
    )
    artifacts = run_dir / "artifacts"
    artifacts.mkdir()
    artifact_name = _voiceover_artifact_filename(run_dir, app, ".mp3")
    (artifacts / artifact_name).write_bytes(b"fake_mp3_content")
    return run_dir


def _run_dir_no_tts(
    tmp_path: Path,
    *,
    app: str = "my_app",
    model: str = "gpt-4.1-mini",
    run_id: str = "run-20250219-143000",
    final_script_path: str = "artifacts/final_script.md",
) -> Path:
    """Create a minimal run_dir with inputs, state, and final_script.md."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "inputs.json").write_text(
        json.dumps({"app": app, "model": model, "run_id": run_id}),
        encoding="utf-8",
    )
    (run_dir / "state.json").write_text(
        json.dumps({"final_script_path": final_script_path}),
        encoding="utf-8",
    )
    artifacts = run_dir / "artifacts"
    artifacts.mkdir()
    (artifacts / "final_script.md").write_text(
        "# Title\n\nA short paragraph.",
        encoding="utf-8",
    )
    return run_dir


class TestBookBasename:
    """Book filename format: {DD-MM-YY}_{app}_{model}_{tts_voice}.mp3 or .pdf."""

    def test_book_basename_tts(self, tmp_path: Path) -> None:
        run_dir = _run_dir_tts(tmp_path)
        name = _book_basename_tts(run_dir)
        assert name == "09-02-25_my_app_gpt-4.1-mini_onyx.mp3"

    def test_book_basename_tts_fallback(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "inputs.json").write_text(
            json.dumps({"app": "x", "run_id": "run-001"}),
            encoding="utf-8",
        )
        name = _book_basename_tts(run_dir)
        assert name.endswith(".mp3")
        assert "01-01-00" in name

    def test_book_basename_no_tts(self, tmp_path: Path) -> None:
        run_dir = _run_dir_no_tts(tmp_path)
        name = _book_basename_no_tts(run_dir)
        assert name == "19-02-25_my_app_gpt-4.1-mini.pdf"

    def test_book_basename_no_tts_fallback(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "inputs.json").write_text(
            json.dumps({"app": "x", "run_id": "run-001"}),
            encoding="utf-8",
        )
        name = _book_basename_no_tts(run_dir)
        assert name.endswith(".pdf")
        assert "01-01-00" in name


class TestCopyTtsDeliverableToBook:
    """copy_tts_deliverable_to_book copies artifacts/story-*.mp3 to runs/book/."""

    def test_copies_mp3_to_book_dir(self, tmp_path: Path) -> None:
        run_dir = _run_dir_tts(tmp_path)
        base_dir = tmp_path / "base"
        base_dir.mkdir()
        log_path = tmp_path / "run.log"
        log_path.touch()
        logger = RunLogger(log_path)

        copy_tts_deliverable_to_book(run_dir=run_dir, base_dir=base_dir, logger=logger)

        book_file = base_dir / "runs" / "book" / "09-02-25_my_app_gpt-4.1-mini_onyx.mp3"
        assert book_file.is_file()
        assert book_file.read_bytes() == b"fake_mp3_content"

    def test_skips_when_artifact_missing(self, tmp_path: Path) -> None:
        run_dir = _run_dir_tts(tmp_path)
        mp3s = list((run_dir / "artifacts").glob("story-*.mp3"))
        assert len(mp3s) == 1
        mp3s[0].unlink()
        base_dir = tmp_path / "base"
        base_dir.mkdir()
        log_path = tmp_path / "run.log"
        log_path.touch()
        logger = RunLogger(log_path)

        copy_tts_deliverable_to_book(run_dir=run_dir, base_dir=base_dir, logger=logger)

        book_dir = base_dir / "runs" / "book"
        assert not book_dir.exists() or len(list(book_dir.iterdir())) == 0


class TestCopyNoTtsDeliverableToBook:
    """copy_no_tts_deliverable_to_book converts final_script.md to PDF in runs/book/."""

    def test_writes_pdf_to_book_dir(self, tmp_path: Path) -> None:
        run_dir = _run_dir_no_tts(tmp_path)
        base_dir = tmp_path / "base"
        base_dir.mkdir()
        log_path = tmp_path / "run.log"
        log_path.touch()
        logger = RunLogger(log_path)

        def fake_md_to_pdf(md_content: str, out_path: Path) -> None:
            out_path.write_bytes(b"%PDF-1.4 fake")

        with patch(
            "llm_storytell.pipeline.deliverable_to_book._markdown_to_pdf",
            side_effect=fake_md_to_pdf,
        ):
            copy_no_tts_deliverable_to_book(
                run_dir=run_dir, base_dir=base_dir, logger=logger
            )

        book_file = base_dir / "runs" / "book" / "19-02-25_my_app_gpt-4.1-mini.pdf"
        assert book_file.is_file()
        assert book_file.read_bytes()[:4] == b"%PDF"

    def test_skips_when_final_script_missing(self, tmp_path: Path) -> None:
        run_dir = _run_dir_no_tts(tmp_path)
        (run_dir / "artifacts" / "final_script.md").unlink()
        base_dir = tmp_path / "base"
        base_dir.mkdir()
        log_path = tmp_path / "run.log"
        log_path.touch()
        logger = RunLogger(log_path)

        copy_no_tts_deliverable_to_book(
            run_dir=run_dir, base_dir=base_dir, logger=logger
        )

        book_dir = base_dir / "runs" / "book"
        assert not book_dir.exists() or len(list(book_dir.iterdir())) == 0
