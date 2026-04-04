"""Pipeline runner: orchestration of run init, context, steps, and providers."""

import json
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import httpx

from llm_storytell.context import ContextLoaderError
from llm_storytell.llm import LLMProvider, LLMProviderError
from llm_storytell.llm.pricing import estimate_run_cost, estimate_tts_cost
from llm_storytell.pipeline.context import load_and_persist_context
from llm_storytell.pipeline.deliverable_to_book import (
    copy_no_tts_deliverable_to_book,
    copy_tts_deliverable_to_book,
)
from llm_storytell.pipeline.providers import (
    ProviderError,
    create_llm_provider,
    create_tts_provider,
)
from llm_storytell.pipeline.resolve import RunSettings
from llm_storytell.pipeline.state import StateIOError, load_state
from llm_storytell.run_dir import RunInitializationError, get_run_logger, initialize_run
from llm_storytell.steps.audio_prep import AudioPrepStepError, execute_audio_prep_step
from llm_storytell.steps.critic import CriticStepError, execute_critic_step
from llm_storytell.steps.llm_tts import LLMTTSStepError, execute_llm_tts_step
from llm_storytell.steps.outline import OutlineStepError, execute_outline_step
from llm_storytell.steps.section import SectionStepError, execute_section_step
from llm_storytell.steps.summarize import SummarizeStepError, execute_summarize_step
from llm_storytell.tts_providers import TTSProviderError


class TelegramDeliveryError(Exception):
    """Telegram delivery failed (credentials, book file, or Bot API)."""


class TelegramRetryableError(Exception):
    """Transient Telegram/HTTP failure; the delivery step may retry."""


def _timestamp_utc() -> str:
    """Current UTC timestamp in ISO 8601 format (seconds)."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _log_and_print_failure(
    logger, run_dir: Path, stage_message: str, e: BaseException
) -> None:
    """Log full exception with traceback to run.log and print to stderr."""
    end_ts = _timestamp_utc()
    logger.info(f"Pipeline run finished at {end_ts} (failed)")
    print(
        f"[llm_storytell] Pipeline run finished at {end_ts} (failed)",
        file=sys.stderr,
        flush=True,
    )
    tb_str = "".join(
        traceback.format_exception(type(e), e, e.__traceback__, chain=True)
    )
    logger.error(f"{stage_message}: {e}\n{tb_str}")
    print(f"[llm_storytell] Error: {stage_message}: {e}", file=sys.stderr, flush=True)
    print(tb_str, file=sys.stderr, flush=True)
    print(
        f"[llm_storytell] See log for details: {run_dir / 'run.log'}",
        file=sys.stderr,
        flush=True,
    )


def _load_telegram_creds(config_path: Path) -> tuple[str, str]:
    creds_file = (Path(config_path) / "creds.json").expanduser().resolve()
    if not creds_file.is_file():
        raise TelegramDeliveryError(
            f"Missing creds file for Telegram delivery: {creds_file}"
        )
    with creds_file.open(encoding="utf-8") as f:
        raw = json.load(f)
    token = (raw.get("TELEGRAM_BOT_API_TOKEN") or "").strip()
    receiver = raw.get("TELEGRAM_RECEIVER_ID")
    chat_id = "" if receiver is None else str(receiver).strip()
    if not token or not chat_id:
        raise TelegramDeliveryError(
            "Telegram delivery requires TELEGRAM_BOT_API_TOKEN and "
            "TELEGRAM_RECEIVER_ID in config/creds.json"
        )
    return token, chat_id


def _newest_file_in_dir(directory: Path) -> Path | None:
    if not directory.is_dir():
        return None
    candidates = [p for p in directory.iterdir() if p.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime_ns)


def _telegram_method_for_suffix(suffix: str) -> tuple[str, str]:
    ext = suffix.lower()
    if ext in (".mp3", ".m4a"):
        return "sendAudio", "audio"
    return "sendDocument", "document"


def _mime_for_suffix(suffix: str) -> str:
    ext = suffix.lower()
    if ext == ".mp3":
        return "audio/mpeg"
    if ext == ".m4a":
        return "audio/mp4"
    if ext == ".pdf":
        return "application/pdf"
    return "application/octet-stream"


def _post_telegram_file(
    token: str,
    chat_id: str,
    file_path: Path,
    *,
    client: httpx.Client,
) -> None:
    method, field = _telegram_method_for_suffix(file_path.suffix)
    url = f"https://api.telegram.org/bot{token}/{method}"
    mime = _mime_for_suffix(file_path.suffix)
    data: dict[str, str] = {"chat_id": chat_id}
    if method == "sendAudio":
        data["title"] = file_path.stem[:64]
    with file_path.open("rb") as fh:
        files = {field: (file_path.name, fh, mime)}
        response = client.post(url, data=data, files=files)
    try:
        body = response.json() if response.content else {}
    except json.JSONDecodeError:
        raise TelegramDeliveryError(
            f"Telegram API returned non-JSON (HTTP {response.status_code}): "
            f"{response.text[:500]}"
        ) from None
    if response.status_code in (429, 500, 502, 503, 504):
        raise TelegramRetryableError(
            f"HTTP {response.status_code}: {body.get('description', response.text[:200])}"
        )
    if response.status_code >= 400:
        raise TelegramDeliveryError(
            body.get("description")
            or f"Telegram API HTTP {response.status_code}: {response.text[:500]}"
        )
    if not body.get("ok"):
        raise TelegramDeliveryError(body.get("description") or str(body))


def _execute_telegram_delivery(
    config_path: Path,
    base_dir: Path,
    logger,
) -> None:
    token, chat_id = _load_telegram_creds(config_path)
    book_dir = (base_dir / "runs" / "book").resolve()
    book_file = _newest_file_in_dir(book_dir)
    if book_file is None:
        raise TelegramDeliveryError(
            f"No deliverable file found in {book_dir} (expected copy from pipeline)"
        )
    size_b = book_file.stat().st_size
    logger.info(
        f"Telegram delivery: sending {book_file.name} ({size_b} bytes) via Bot API"
    )

    delays = (1.0, 2.0, 4.0)
    for attempt in range(len(delays) + 1):
        try:
            with httpx.Client(timeout=120.0) as client:
                _post_telegram_file(token, chat_id, book_file, client=client)
            logger.info("Telegram delivery completed successfully")
            return
        except TelegramRetryableError as e:
            if attempt >= len(delays):
                raise TelegramDeliveryError(
                    f"Telegram delivery failed after retries: {e}"
                ) from e
            logger.warning(
                f"Telegram delivery attempt {attempt + 1} failed ({e!s}); "
                f"retrying in {delays[attempt]:.0f}s..."
            )
            time.sleep(delays[attempt])
        except httpx.RequestError as e:
            if attempt >= len(delays):
                raise TelegramDeliveryError(
                    f"Telegram delivery failed after retries: {e}"
                ) from e
            logger.warning(
                f"Telegram delivery attempt {attempt + 1} network error ({e!s}); "
                f"retrying in {delays[attempt]:.0f}s..."
            )
            time.sleep(delays[attempt])


def run_pipeline(settings: RunSettings) -> int:
    """Run the complete content generation pipeline.

    Executes: run init, context load and persist, outline, section loop,
    summarize, critic; optionally TTS and audio-prep when tts_enabled.

    Args:
        settings: Resolved run settings (from pipeline.resolve).

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    try:
        base_dir = Path.cwd()
        run_dir = initialize_run(
            app_name=settings.app_paths.app_name,
            seed=settings.seed,
            context_dir=settings.app_paths.context_dir,
            prompts_dir=settings.app_paths.prompts_dir,
            beats=settings.beats,
            run_id=settings.run_id,
            base_dir=base_dir,
            word_count=settings.word_count,
            resolved_tts_config=settings.resolved_tts_config,
            model=settings.model,
            language=settings.language,
        )

        logger = get_run_logger(run_dir)
        start_ts = _timestamp_utc()
        logger.info(f"Pipeline run started at {start_ts}")
        print(f"[llm_storytell] Pipeline run started at {start_ts}", flush=True)

        print(
            f"[llm_storytell] Initialized run '{run_dir.name}' "
            f"for app '{settings.app_paths.app_name}'.",
            flush=True,
        )
        print(f"[llm_storytell] Run directory: {run_dir}", flush=True)

        try:
            load_and_persist_context(
                run_dir=run_dir,
                context_dir=settings.app_paths.context_dir,
                app_config=settings.app_config,
                model=settings.model,
                logger=logger,
                run_id=run_dir.name,
            )
        except ContextLoaderError as e:
            _log_and_print_failure(logger, run_dir, "context load failed", e)
            return 1

        try:
            llm_provider: LLMProvider = create_llm_provider(
                settings.config_path, default_model=settings.model
            )
        except ProviderError as e:
            _log_and_print_failure(logger, run_dir, "LLM provider creation failed", e)
            return 1

        schema_base = base_dir / "src" / "llm_storytell" / "schemas"
        section_length = settings.section_length
        app_paths = settings.app_paths

        # Stage 1: Outline
        print(
            f"[llm_storytell] Generating outline ({settings.beats} beats)...",
            flush=True,
        )
        logger.log_stage_start("outline")
        try:
            execute_outline_step(
                run_dir=run_dir,
                context_dir=app_paths.context_dir,
                prompts_dir=app_paths.prompts_dir,
                llm_provider=llm_provider,
                logger=logger,
                schema_base=schema_base,
            )
            logger.log_stage_end("outline", success=True)
        except (OutlineStepError, LLMProviderError) as e:
            logger.log_stage_end("outline", success=False)
            _log_and_print_failure(logger, run_dir, "outline stage failed", e)
            return 1

        try:
            state = load_state(run_dir)
        except StateIOError as e:
            _log_and_print_failure(
                logger, run_dir, "loading state after outline failed", e
            )
            return 1

        outline_beats = state.get("outline", [])
        if not outline_beats:
            logger.error("Outline generation produced no beats")
            print(
                "[llm_storytell] Error: outline generation produced no beats. "
                f"See log for details: {run_dir / 'run.log'}",
                file=sys.stderr,
                flush=True,
            )
            return 1

        num_sections = len(outline_beats)

        # Stage 2: Section loop
        print(
            f"[llm_storytell] Generating {num_sections} section(s)...",
            flush=True,
        )
        for section_index in range(num_sections):
            stage_name = f"section_{section_index:02d}"

            print(
                f"[llm_storytell]  - Section {section_index + 1}/{num_sections}",
                flush=True,
            )
            logger.log_stage_start(stage_name)
            try:
                execute_section_step(
                    run_dir=run_dir,
                    context_dir=app_paths.context_dir,
                    prompts_dir=app_paths.prompts_dir,
                    llm_provider=llm_provider,
                    logger=logger,
                    section_index=section_index,
                    section_length=section_length,
                    schema_base=schema_base,
                )
                logger.log_stage_end(stage_name, success=True)
            except (SectionStepError, LLMProviderError) as e:
                logger.log_stage_end(stage_name, success=False)
                _log_and_print_failure(
                    logger,
                    run_dir,
                    f"section {section_index} failed",
                    e,
                )
                return 1

            summarize_stage_name = f"summarize_{section_index:02d}"
            logger.log_stage_start(summarize_stage_name)
            try:
                execute_summarize_step(
                    run_dir=run_dir,
                    prompts_dir=app_paths.prompts_dir,
                    llm_provider=llm_provider,
                    logger=logger,
                    section_index=section_index,
                    schema_base=schema_base,
                )
                logger.log_stage_end(summarize_stage_name, success=True)
            except (SummarizeStepError, LLMProviderError) as e:
                logger.log_stage_end(summarize_stage_name, success=False)
                _log_and_print_failure(
                    logger,
                    run_dir,
                    f"summarize {section_index} failed",
                    e,
                )
                return 1

        # Stage 3: Critic
        print("[llm_storytell] Running critic/finalization...", flush=True)
        logger.log_stage_start("critic")
        try:
            execute_critic_step(
                run_dir=run_dir,
                context_dir=app_paths.context_dir,
                prompts_dir=app_paths.prompts_dir,
                llm_provider=llm_provider,
                logger=logger,
                schema_base=schema_base,
            )
            logger.log_stage_end("critic", success=True)
        except (CriticStepError, LLMProviderError) as e:
            logger.log_stage_end("critic", success=False)
            _log_and_print_failure(logger, run_dir, "critic stage failed", e)
            return 1

        if not settings.tts_enabled:
            copy_no_tts_deliverable_to_book(
                run_dir=run_dir, base_dir=base_dir, logger=logger
            )

        # TTS (when enabled)
        if settings.tts_enabled and settings.resolved_tts_config:
            try:
                tts_provider = create_tts_provider(
                    settings.config_path, settings.resolved_tts_config
                )
            except ProviderError as e:
                _log_and_print_failure(
                    logger, run_dir, "TTS provider creation failed", e
                )
                return 1

            tts_model = settings.resolved_tts_config.get("tts_model")
            tts_voice = settings.resolved_tts_config.get("tts_voice")

            print("[llm_storytell] Running TTS (text-to-speech)...", flush=True)
            logger.log_stage_start("tts")
            try:
                execute_llm_tts_step(
                    run_dir=run_dir,
                    tts_provider=tts_provider,
                    logger=logger,
                    tts_model=tts_model,
                    tts_voice=tts_voice,
                )
                logger.log_stage_end("tts", success=True)
            except (LLMTTSStepError, TTSProviderError) as e:
                logger.log_stage_end("tts", success=False)
                _log_and_print_failure(logger, run_dir, "TTS stage failed", e)
                return 1

            print("[llm_storytell] Running audio prep (stitch + mix)...", flush=True)
            logger.log_stage_start("audio_prep")
            try:
                execute_audio_prep_step(
                    run_dir=run_dir,
                    base_dir=base_dir,
                    logger=logger,
                    app_name=app_paths.app_name,
                )
                logger.log_stage_end("audio_prep", success=True)
                copy_tts_deliverable_to_book(
                    run_dir=run_dir, base_dir=base_dir, logger=logger
                )
            except AudioPrepStepError as e:
                logger.log_stage_end("audio_prep", success=False)
                _log_and_print_failure(logger, run_dir, "audio-prep stage failed", e)
                return 1

        try:
            state = load_state(run_dir)
            usage = state.get("token_usage") or []
            tts_usage = state.get("tts_token_usage") or []
            model, prompt_total, completion_total, total_tokens, chat_cost = (
                estimate_run_cost(usage)
            )
            total_tts_chars, tts_cost = estimate_tts_cost(tts_usage)

            if model is not None:
                print(f"[llm_storytell] Model: {model}", flush=True)

            # One line: Chat tokens and optionally TTS characters
            tokens_line_parts: list[str] = []
            if prompt_total or completion_total or total_tokens:
                tokens_line_parts.append(
                    f"Chat Tokens: {prompt_total:,} input, {completion_total:,} output, "
                    f"{total_tokens:,} total"
                )
            if total_tts_chars:
                tokens_line_parts.append(
                    f"TTS: {total_tts_chars:,} characters requested"
                )
            if tokens_line_parts:
                tokens_line = ". ".join(tokens_line_parts)
                print(f"[llm_storytell] {tokens_line}", flush=True)
                logger.info(tokens_line)

            # Next line: estimated cost split by service
            cost_parts: list[str] = []
            if chat_cost is not None:
                cost_parts.append(f"${chat_cost:.2f} Chat")
            elif model is not None and (prompt_total or completion_total):
                cost_parts.append("Chat N/A (model not in pricing table)")
            if tts_cost is not None:
                cost_parts.append(f"${tts_cost:.2f} TTS")
            elif total_tts_chars:
                cost_parts.append("TTS N/A (model not in pricing table)")
            if cost_parts:
                total_cost: float | None = None
                if chat_cost is not None and tts_cost is not None:
                    total_cost = chat_cost + tts_cost
                elif chat_cost is not None:
                    total_cost = chat_cost
                elif tts_cost is not None:
                    total_cost = tts_cost
                cost_line = "Estimated cost: " + " + ".join(cost_parts)
                if total_cost is not None:
                    cost_line += f" = ${total_cost:.2f} total"
                print(f"[llm_storytell] {cost_line}", flush=True)
                logger.info(cost_line)
            elif model is not None and not total_tts_chars:
                print(
                    "[llm_storytell] Estimated cost: N/A (model not in pricing table)",
                    flush=True,
                )
                logger.info("Estimated cost: N/A (model not in pricing table)")
        except (StateIOError, KeyError):
            pass

        if settings.delivery:
            print("[llm_storytell] Delivering to Telegram...", flush=True)
            logger.log_stage_start("telegram_delivery")
            try:
                _execute_telegram_delivery(
                    config_path=settings.config_path,
                    base_dir=base_dir,
                    logger=logger,
                )
                logger.log_stage_end("telegram_delivery", success=True)
            except TelegramDeliveryError as e:
                logger.log_stage_end("telegram_delivery", success=False)
                _log_and_print_failure(logger, run_dir, "telegram delivery failed", e)
                return 1

        end_ts = _timestamp_utc()
        logger.info(f"Pipeline run finished at {end_ts}")
        print(f"[llm_storytell] Pipeline run finished at {end_ts}", flush=True)
        logger.info(f"Pipeline completed successfully. Run directory: {run_dir}")
        print("[llm_storytell] Run complete.", flush=True)

        print(
            f"[llm_storytell] Artifacts are in: {run_dir / 'artifacts'}",
            flush=True,
        )
        return 0

    except RunInitializationError as e:
        end_ts = _timestamp_utc()
        print(
            f"[llm_storytell] Pipeline run finished at {end_ts} (failed)",
            file=sys.stderr,
            flush=True,
        )
        print(f"Error: Failed to initialize run: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        end_ts = _timestamp_utc()
        print(
            f"[llm_storytell] Pipeline run finished at {end_ts} (failed)",
            file=sys.stderr,
            flush=True,
        )
        tb_str = "".join(
            traceback.format_exception(type(e), e, e.__traceback__, chain=True)
        )
        print(f"Error: Unexpected error: {e}", file=sys.stderr)
        print(tb_str, file=sys.stderr)
        return 1
