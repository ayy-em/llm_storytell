"""Command-line interface for llm_storytell."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .config import (
    AppConfig,
    AppConfigError,
    AppNotFoundError,
    AppPaths,
    load_app_config,
    resolve_app,
)
from .context import ContextLoader, ContextLoaderError
from .llm import LLMProvider, LLMProviderError, OpenAIProvider
from .llm.pricing import estimate_run_cost
from .run_dir import RunInitializationError, get_run_logger, initialize_run
from .steps.critic import CriticStepError, execute_critic_step
from .steps.outline import OutlineStepError, execute_outline_step
from .steps.section import SectionStepError, execute_section_step
from .steps.summarize import SummarizeStepError, execute_summarize_step


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        prog="llm_storytell",
        description="A deterministic content generation pipeline for narrative text.",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # 'run' subcommand
    run_parser = subparsers.add_parser(
        "run", help="Run the content generation pipeline"
    )
    run_parser.add_argument(
        "--app",
        required=True,
        help="Name of the app to run (requires apps/<app>/context/)",
    )
    run_parser.add_argument(
        "--seed",
        required=False,
        help="Short natural-language description of the story (2-3 sentences)",
    )
    run_parser.add_argument(
        "--beats",
        type=int,
        required=False,
        help="Number of outline beats (1-20, default: app-defined)",
    )
    run_parser.add_argument(
        "--sections",
        type=int,
        required=False,
        help="Alias for --beats (one section per beat)",
    )
    run_parser.add_argument(
        "--run-id",
        required=False,
        help="Optional run ID override (default: run-YYYYMMDD-HHMMSS)",
    )
    run_parser.add_argument(
        "--config-path",
        type=Path,
        default=Path("config/"),
        help="Path to configuration directory (default: config/)",
    )
    run_parser.add_argument(
        "--model",
        required=False,
        help="Model identifier for all LLM calls in this run (default: gpt-4.1-mini). Fails immediately if the provider does not recognize the model.",
    )
    run_parser.add_argument(
        "--section-length",
        type=int,
        required=False,
        metavar="N",
        help="Target words per section; pipeline uses range [N*0.8, N*1.2]. Overrides app config when set.",
    )
    run_parser.add_argument(
        "--word-count",
        type=int,
        required=False,
        metavar="N",
        help="Target total word count for the story (100 < N < 15000). Derives beat count and section length; see SPEC.",
    )

    return parser


def _section_length_midpoint(section_length_str: str) -> int:
    """Parse section_length string (e.g. '400-600') to midpoint; fallback 500."""
    s = section_length_str.strip()
    if "-" in s:
        parts = s.split("-", 1)
        try:
            lo, hi = int(parts[0].strip()), int(parts[1].strip())
            if lo > 0 and hi >= lo:
                return (lo + hi) // 2
        except ValueError:
            pass
    try:
        return int(s)
    except ValueError:
        pass
    return 500


def resolve_app_or_exit(app_name: str, base_dir: Path | None = None) -> AppPaths:
    """Resolve app paths or exit with an error message.

    Args:
        app_name: The name of the app to resolve.
        base_dir: The base directory of the project.

    Returns:
        AppPaths if resolution succeeds.

    Exits:
        With code 1 if app resolution fails.
    """
    try:
        return resolve_app(app_name, base_dir)
    except AppNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def _update_state_selected_context(
    run_dir: Path, selected_context: dict[str, Any]
) -> None:
    """Update state.json with selected context files.

    Args:
        run_dir: Path to the run directory.
        selected_context: Dictionary with 'location', 'characters', and
            'world_files' keys (basenames for reproducibility).
    """
    state_path = run_dir / "state.json"
    with state_path.open("r", encoding="utf-8") as f:
        state = json.load(f)

    state["selected_context"] = selected_context

    with state_path.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def _create_llm_provider_from_config(
    config_path: Path, default_model: str = "gpt-4.1-mini"
) -> LLMProvider:
    """Create LLM provider from configuration.

    Args:
        config_path: Path to config directory.
        default_model: Model to use for all LLM calls (CLI override or default).

    Returns:
        LLM provider instance.

    Raises:
        SystemExit: If provider cannot be created.
    """
    # For v1.0, we'll use OpenAIProvider with a simple client wrapper
    # In a real implementation, this would load from config/model.yaml
    try:
        from openai import OpenAI
    except ImportError:
        print(
            "Error: openai package not installed. Install with: pip install openai",
            file=sys.stderr,
        )
        sys.exit(1)

    # Try to load API key from config/creds.json
    creds_path = config_path / "creds.json"
    api_key = None
    if creds_path.exists():
        try:
            with creds_path.open(encoding="utf-8") as f:
                creds = json.load(f)
                # Try multiple common key name variations
                api_key = (
                    creds.get("openai_api_key")
                    or creds.get("OPENAI_KEY")
                    or creds.get("OPEN_AI")
                    or creds.get("OPENAI_API_KEY")
                )
        except (OSError, json.JSONDecodeError, KeyError):
            pass

    if not api_key:
        print(
            "Error: No OpenAI API key found. "
            "Create config/creds.json with one of these fields: "
            "'openai_api_key', 'OPENAI_KEY', 'OPEN_AI', or 'OPENAI_API_KEY'.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        client = OpenAI(api_key=api_key)

        def openai_client_wrapper(
            prompt: str, model: str, **kwargs: Any
        ) -> dict[str, Any]:
            """Wrapper around OpenAI client for the provider interface."""
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                **kwargs,
            )
            return {
                "choices": [
                    {"message": {"content": response.choices[0].message.content}}
                ],
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
            }

        return OpenAIProvider(
            client=openai_client_wrapper,
            default_model=default_model,
            temperature=0.7,
        )
    except Exception as e:
        print(f"Error creating LLM provider: {e}", file=sys.stderr)
        sys.exit(1)


def _run_pipeline(
    app_paths: AppPaths,
    app_config: AppConfig,
    seed: str,
    beats: int | None,
    section_length: str,
    run_id: str | None,
    config_path: Path,
    model: str = "gpt-4.1-mini",
    llm_provider: LLMProvider | None = None,
    word_count: int | None = None,
) -> int:
    """Run the complete content generation pipeline.

    Args:
        app_paths: Resolved app paths.
        app_config: Merged app config (defaults + app overrides) for context limits, etc.
        seed: Story seed/description.
        beats: Number of outline beats (None for app-defined default).
        section_length: Target word range for sections (e.g. "400-600").
        run_id: Optional run ID override.
        config_path: Path to configuration directory.
        model: Model identifier for all LLM calls in this run.
        llm_provider: Optional LLM provider (for testing). If None, creates from config.
        word_count: Optional target total word count (when --word-count was used).

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    try:
        # Initialize run directory
        base_dir = Path.cwd()
        run_dir = initialize_run(
            app_name=app_paths.app_name,
            seed=seed,
            context_dir=app_paths.context_dir,
            prompts_dir=app_paths.prompts_dir,
            beats=beats,
            run_id=run_id,
            base_dir=base_dir,
            word_count=word_count,
        )

        logger = get_run_logger(run_dir)

        # Basic CLI progress output so runs don't feel "silent"
        print(
            f"[llm_storytell] Initialized run '{run_dir.name}' "
            f"for app '{app_paths.app_name}'.",
            flush=True,
        )
        print(f"[llm_storytell] Run directory: {run_dir}", flush=True)

        # Load and select context (required: lore_bible + at least one character)
        try:
            loader = ContextLoader(
                app_paths.context_dir,
                logger=logger,
                app_config=app_config,
            )
            selection = loader.load_context(run_dir.name)
        except ContextLoaderError as e:
            logger.error(str(e))
            print(
                f"[llm_storytell] Error: {e}",
                file=sys.stderr,
                flush=True,
            )
            return 1

        # Persist selected context (basenames for reproducibility)
        selected_context: dict[str, Any] = {
            "location": Path(selection.selected_location).name
            if selection.selected_location
            else None,
            "characters": [Path(p).name for p in selection.selected_characters],
            "world_files": [Path(p).name for p in selection.world_files],
        }
        _update_state_selected_context(run_dir, selected_context)

        # Create or use provided LLM provider (model applies to all LLM calls in this run)
        if llm_provider is None:
            llm_provider = _create_llm_provider_from_config(
                config_path, default_model=model
            )

        # Get schema base path
        schema_base = base_dir / "src" / "llm_storytell" / "schemas"

        # Stage 1: Outline generation
        print(
            f"[llm_storytell] Generating outline ({beats} beats)...",
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

        # Load state to get outline beats
        state_path = run_dir / "state.json"
        with state_path.open(encoding="utf-8") as f:
            state = json.load(f)

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

        # Stage 2: Section generation loop
        print(
            f"[llm_storytell] Generating {num_sections} section(s)...",
            flush=True,
        )
        for section_index in range(num_sections):
            stage_name = f"section_{section_index:02d}"

            # Generate section
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

            # Summarize section
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

        # Stage 3: Critic/Editor pass
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

        logger.info(f"Pipeline completed successfully. Run directory: {run_dir}")
        print("[llm_storytell] Run complete.", flush=True)
        # Token and cost summary from state
        try:
            with (run_dir / "state.json").open(encoding="utf-8") as f:
                state = json.load(f)
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
        except (OSError, json.JSONDecodeError, KeyError):
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


def main(argv: list[str] | None = None) -> int:
    """Main entry point for the CLI.

    Args:
        argv: Command-line arguments. If None, uses sys.argv[1:].

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    parser = create_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "run":
        # Validate required arguments
        if not args.seed:
            print("Error: --seed is required for 'run' command", file=sys.stderr)
            parser.print_help()
            return 1

        base_dir = Path.cwd()
        # Resolve app paths (apps/<app>/ only)
        app_paths = resolve_app_or_exit(args.app, base_dir)

        # Load app config (defaults + optional apps/<app>/app_config.yaml)
        try:
            app_config = load_app_config(
                app_paths.app_name,
                base_dir=base_dir,
                app_root=app_paths.app_root,
            )
        except AppConfigError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        # Handle --beats vs --sections conflict (prefer --beats)
        beats = args.beats
        if args.sections is not None:
            if beats is not None:
                print(
                    "Warning: Both --beats and --sections specified. Using --beats.",
                    file=sys.stderr,
                )
            else:
                beats = args.sections

        # Validate --word-count range when provided (100 < N < 15000)
        word_count: int | None = getattr(args, "word_count", None)
        if word_count is not None:
            if word_count <= 100 or word_count >= 15000:
                print(
                    "Error: --word-count must be greater than 100 and less than 15000",
                    file=sys.stderr,
                )
                return 1

        # Derive beats and section_length from --word-count when provided
        if word_count is not None:
            if beats is not None:
                # Both --beats and --word-count: validate words-per-section
                words_per = word_count / beats
                if words_per <= 100:
                    print(
                        "Error: --word-count / --beats must be greater than 100 "
                        f"(got {word_count}/{beats} = {words_per:.0f} words per section)",
                        file=sys.stderr,
                    )
                    return 1
                if words_per >= 1000:
                    print(
                        "Error: --word-count / --beats must be less than 1000 "
                        f"(got {word_count}/{beats} = {words_per:.0f} words per section)",
                        file=sys.stderr,
                    )
                    return 1
                section_length_per = word_count / beats
            else:
                # Only --word-count: derive beats from baseline section length
                if args.section_length is not None:
                    baseline = args.section_length
                else:
                    baseline = _section_length_midpoint(app_config.section_length)
                beats = max(1, min(20, round(word_count / baseline)))
                section_length_per = word_count / beats
            lo = int(section_length_per * 0.8)
            hi = int(section_length_per * 1.2)
            section_length = f"{lo}-{hi}"
        else:
            # No --word-count: validate beats range if provided
            if beats is not None and (beats < 1 or beats > 20):
                print(
                    "Error: --beats must be between 1 and 20 (inclusive)",
                    file=sys.stderr,
                )
                return 1
            if beats is None:
                beats = app_config.beats
            # Section length: CLI --section-length N -> range [N*0.8, N*1.2], else app config
            if args.section_length is not None:
                lo = int(args.section_length * 0.8)
                hi = int(args.section_length * 1.2)
                section_length = f"{lo}-{hi}"
            else:
                section_length = app_config.section_length

        # Model for all LLM calls: CLI override or default
        model = args.model if args.model is not None else "gpt-4.1-mini"

        # Run the pipeline
        return _run_pipeline(
            app_paths=app_paths,
            app_config=app_config,
            seed=args.seed,
            beats=beats,
            section_length=section_length,
            run_id=args.run_id,
            config_path=args.config_path,
            model=model,
            word_count=word_count,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
