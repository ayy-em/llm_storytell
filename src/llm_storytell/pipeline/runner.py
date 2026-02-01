"""Pipeline runner: orchestration of run init, context, steps, and providers."""

import sys
from pathlib import Path

from llm_storytell.context import ContextLoaderError
from llm_storytell.llm import LLMProvider, LLMProviderError
from llm_storytell.llm.pricing import estimate_run_cost
from llm_storytell.pipeline.context import load_and_persist_context
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
        )

        logger = get_run_logger(run_dir)

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
            logger.error(str(e))
            print(
                f"[llm_storytell] Error: {e}",
                file=sys.stderr,
                flush=True,
            )
            return 1

        try:
            llm_provider: LLMProvider = create_llm_provider(
                settings.config_path, default_model=settings.model
            )
        except ProviderError as e:
            logger.error(str(e))
            print(f"[llm_storytell] Error: {e}", file=sys.stderr, flush=True)
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
            logger.error(f"Outline step failed: {e}")
            logger.log_stage_end("outline", success=False)
            print(
                f"[llm_storytell] Error: outline stage failed: {e}",
                file=sys.stderr,
                flush=True,
            )
            print(
                f"[llm_storytell] See log for details: {run_dir / 'run.log'}",
                file=sys.stderr,
                flush=True,
            )
            return 1

        try:
            state = load_state(run_dir)
        except StateIOError as e:
            logger.error(str(e))
            print(
                f"[llm_storytell] Error: {e}",
                file=sys.stderr,
                flush=True,
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
                logger.error(f"Section {section_index} step failed: {e}")
                logger.log_stage_end(stage_name, success=False)
                print(
                    f"[llm_storytell] Error: section {section_index} failed: {e}",
                    file=sys.stderr,
                    flush=True,
                )
                print(
                    f"[llm_storytell] See log for details: {run_dir / 'run.log'}",
                    file=sys.stderr,
                    flush=True,
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
                logger.error(f"Summarize {section_index} step failed: {e}")
                logger.log_stage_end(summarize_stage_name, success=False)
                print(
                    f"[llm_storytell] Error: summarize {section_index} failed: {e}",
                    file=sys.stderr,
                    flush=True,
                )
                print(
                    f"[llm_storytell] See log for details: {run_dir / 'run.log'}",
                    file=sys.stderr,
                    flush=True,
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
            logger.error(f"Critic step failed: {e}")
            logger.log_stage_end("critic", success=False)
            print(
                f"[llm_storytell] Error: critic stage failed: {e}",
                file=sys.stderr,
                flush=True,
            )
            print(
                f"[llm_storytell] See log for details: {run_dir / 'run.log'}",
                file=sys.stderr,
                flush=True,
            )
            return 1

        # TTS (when enabled)
        if settings.tts_enabled and settings.resolved_tts_config:
            try:
                tts_provider = create_tts_provider(
                    settings.config_path, settings.resolved_tts_config
                )
            except ProviderError as e:
                logger.error(str(e))
                print(f"[llm_storytell] Error: {e}", file=sys.stderr, flush=True)
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
                logger.error(f"TTS step failed: {e}")
                logger.log_stage_end("tts", success=False)
                print(
                    f"[llm_storytell] Error: TTS stage failed: {e}",
                    file=sys.stderr,
                    flush=True,
                )
                print(
                    f"[llm_storytell] See log for details: {run_dir / 'run.log'}",
                    file=sys.stderr,
                    flush=True,
                )
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
            except AudioPrepStepError as e:
                logger.error(f"Audio-prep step failed: {e}")
                logger.log_stage_end("audio_prep", success=False)
                print(
                    f"[llm_storytell] Error: audio-prep stage failed: {e}",
                    file=sys.stderr,
                    flush=True,
                )
                print(
                    f"[llm_storytell] See log for details: {run_dir / 'run.log'}",
                    file=sys.stderr,
                    flush=True,
                )
                return 1

        logger.info(f"Pipeline completed successfully. Run directory: {run_dir}")
        print("[llm_storytell] Run complete.", flush=True)

        try:
            state = load_state(run_dir)
            usage = state.get("token_usage") or []
            model, prompt_total, completion_total, total_tokens, cost_usd = (
                estimate_run_cost(usage)
            )
            if model is not None:
                print(f"[llm_storytell] Model: {model}", flush=True)
            if prompt_total or completion_total or total_tokens:
                print(
                    f"[llm_storytell] Tokens: {prompt_total:,} prompt, "
                    f"{completion_total:,} completion ({total_tokens:,} total)",
                    flush=True,
                )
            if cost_usd is not None:
                print(
                    f"[llm_storytell] Estimated cost: ~${cost_usd:.4g} (Standard pricing)",
                    flush=True,
                )
            elif model is not None:
                print(
                    "[llm_storytell] Estimated cost: N/A (model not in pricing table)",
                    flush=True,
                )
        except (StateIOError, KeyError):
            pass

        print(
            f"[llm_storytell] Artifacts are in: {run_dir / 'artifacts'}",
            flush=True,
        )
        return 0

    except RunInitializationError as e:
        print(f"Error: Failed to initialize run: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: Unexpected error: {e}", file=sys.stderr)
        return 1
