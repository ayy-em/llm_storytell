"""Tests for Telegram delivery helpers and step (mocked HTTP)."""

import json
from pathlib import Path

import httpx
import pytest

from llm_storytell.logging import RunLogger
from llm_storytell.pipeline import runner as runner_mod
from llm_storytell.pipeline.runner import (
    TelegramDeliveryError,
    _execute_telegram_delivery,
    _load_telegram_creds,
    _log_and_print_failure,
    _newest_file_in_dir,
    _post_telegram_file,
)


def test_load_telegram_creds_success(tmp_path: Path) -> None:
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "creds.json").write_text(
        json.dumps(
            {"TELEGRAM_BOT_API_TOKEN": "abc:token", "TELEGRAM_RECEIVER_ID": 12345}
        ),
        encoding="utf-8",
    )
    token, chat = _load_telegram_creds(cfg)
    assert token == "abc:token"
    assert chat == "12345"


def test_load_telegram_creds_missing_file(tmp_path: Path) -> None:
    cfg = tmp_path / "config"
    cfg.mkdir()
    with pytest.raises(TelegramDeliveryError, match="Missing creds"):
        _load_telegram_creds(cfg)


def test_load_telegram_creds_empty_values(tmp_path: Path) -> None:
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "creds.json").write_text(
        json.dumps({"TELEGRAM_BOT_API_TOKEN": "", "TELEGRAM_RECEIVER_ID": ""}),
        encoding="utf-8",
    )
    with pytest.raises(TelegramDeliveryError, match="TELEGRAM_BOT_API_TOKEN"):
        _load_telegram_creds(cfg)


def test_newest_file_in_dir(tmp_path: Path) -> None:
    d = tmp_path / "book"
    d.mkdir()
    (d / "old.txt").write_text("a", encoding="utf-8")
    new = d / "new.txt"
    new.write_text("b", encoding="utf-8")
    assert _newest_file_in_dir(d) == new


def test_newest_file_in_dir_empty(tmp_path: Path) -> None:
    d = tmp_path / "empty"
    d.mkdir()
    assert _newest_file_in_dir(d) is None


def test_post_telegram_mp3_uses_sendaudio(tmp_path: Path) -> None:
    mp3 = tmp_path / "x.mp3"
    mp3.write_bytes(b"id3")

    requests_made: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests_made.append(request)
        return httpx.Response(200, json={"ok": True, "result": {}})

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        _post_telegram_file("tok", "99", mp3, client=client)

    assert len(requests_made) == 1
    assert "sendAudio" in str(requests_made[0].url)


def test_post_telegram_pdf_uses_senddocument(tmp_path: Path) -> None:
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF")

    requests_made: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests_made.append(request)
        return httpx.Response(200, json={"ok": True, "result": {}})

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        _post_telegram_file("tok", "99", pdf, client=client)

    assert len(requests_made) == 1
    assert "sendDocument" in str(requests_made[0].url)


def test_post_telegram_ok_false_raises(tmp_path: Path) -> None:
    mp3 = tmp_path / "x.mp3"
    mp3.write_bytes(b"x")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": False, "description": "bad chat"})

    transport = httpx.MockTransport(handler)
    with (
        httpx.Client(transport=transport) as client,
        pytest.raises(TelegramDeliveryError, match="bad chat"),
    ):
        _post_telegram_file("tok", "99", mp3, client=client)


def test_execute_telegram_delivery_retries_on_503(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "creds.json").write_text(
        json.dumps({"TELEGRAM_BOT_API_TOKEN": "t", "TELEGRAM_RECEIVER_ID": "1"}),
        encoding="utf-8",
    )
    book = tmp_path / "runs" / "book"
    book.mkdir(parents=True)
    (book / "a.mp3").write_bytes(b"x")

    n = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        n["count"] += 1
        if n["count"] < 2:
            return httpx.Response(503, json={"ok": False})
        return httpx.Response(200, json={"ok": True, "result": {}})

    transport = httpx.MockTransport(handler)
    real_client = httpx.Client

    def client_with_transport(*args: object, **kwargs: object) -> httpx.Client:
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr(runner_mod.httpx, "Client", client_with_transport)
    monkeypatch.setattr(runner_mod.time, "sleep", lambda _s: None)

    logger = RunLogger(tmp_path / "run.log")
    _execute_telegram_delivery(cfg, tmp_path, logger)
    assert n["count"] == 2


def test_execute_telegram_delivery_no_book_file(
    tmp_path: Path,
) -> None:
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "creds.json").write_text(
        json.dumps({"TELEGRAM_BOT_API_TOKEN": "t", "TELEGRAM_RECEIVER_ID": "1"}),
        encoding="utf-8",
    )
    (tmp_path / "runs" / "book").mkdir(parents=True)
    logger = RunLogger(tmp_path / "run.log")
    with pytest.raises(TelegramDeliveryError, match="No deliverable file"):
        _execute_telegram_delivery(cfg, tmp_path, logger)


def test_log_and_print_failure_includes_traceback_for_telegram_error(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """Delivery failures use _log_and_print_failure: chained traceback in run.log and stderr."""
    run_dir = tmp_path / "run-z"
    run_dir.mkdir()
    log_path = run_dir / "run.log"
    logger = RunLogger(log_path)
    try:
        raise RuntimeError("root cause")
    except RuntimeError as cause:
        try:
            raise TelegramDeliveryError("bad token") from cause
        except TelegramDeliveryError as err:
            _log_and_print_failure(logger, run_dir, "telegram delivery failed", err)
    log_text = log_path.read_text(encoding="utf-8")
    assert "telegram delivery failed" in log_text
    assert "TelegramDeliveryError" in log_text
    assert "Traceback" in log_text
    assert "bad token" in log_text
    out_err = capsys.readouterr().err
    assert "telegram delivery failed" in out_err.lower()
    assert "Traceback" in out_err
