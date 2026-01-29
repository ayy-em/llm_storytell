"""Command-line interface for llm_storytell."""

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path
from typing import Any

from .config import AppNotFoundError, AppPaths, resolve_app
from .llm import LLMProvider, LLMProviderError, OpenAIProvider
from .logging import RunLogger
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
        help="Name of the app to run (must exist under context/ and prompts/apps/)",
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

    return parser


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


def _select_context_files(
    context_dir: Path, run_id: str, logger: RunLogger
) -> dict[str, Any]:
    """Select context files randomly but deterministically based on run_id.

    Args:
        context_dir: Path to the app's context directory.
        run_id: Run ID used as seed for deterministic selection.
        logger: Logger instance for logging selections.

    Returns:
        Dictionary with 'location' and 'characters' keys for selected context.
    """
    # Use run_id as seed for deterministic randomness
    seed_hash = int(hashlib.md5(run_id.encode()).hexdigest(), 16)
    rng = random.Random(seed_hash)

    selected: dict[str, Any] = {"location": None, "characters": []}

    # Select one location (if locations directory exists and has files)
    locations_dir = context_dir / "locations"
    if locations_dir.exists():
        location_files = list(locations_dir.glob("*.md"))
        if location_files:
            selected_location = rng.choice(location_files)
            selected["location"] = selected_location.name
            logger.info(f"Selected location: {selected_location.name}")

    # Select 2-3 characters (if characters directory exists and has files)
    characters_dir = context_dir / "characters"
    if characters_dir.exists():
        character_files = list(characters_dir.glob("*.md"))
        if character_files:
            num_to_select = min(rng.randint(2, 3), len(character_files))
            selected_characters = rng.sample(character_files, num_to_select)
            selected["characters"] = [f.name for f in selected_characters]
            logger.info(
                f"Selected {len(selected['characters'])} characters: "
                f"{', '.join(selected['characters'])}"
            )

    return selected


def _update_state_selected_context(
    run_dir: Path, selected_context: dict[str, Any]
) -> None:
    """Update state.json with selected context files.

    Args:
        run_dir: Path to the run directory.
        selected_context: Dictionary with 'location' and 'characters' keys.
    """
    state_path = run_dir / "state.json"
    with state_path.open("r", encoding="utf-8") as f:
        state = json.load(f)

    state["selected_context"] = selected_context

    with state_path.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def _create_llm_provider_from_config(
    config_path: Path, default_model: str = "gpt-4"
) -> LLMProvider:
    """Create LLM provider from configuration.

    Args:
        config_path: Path to config directory.
        default_model: Default model to use if config is missing.

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
                    {"message": {"content": response.choices[0].message.content or ""}}
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
    seed: str,
    beats: int | None,
    run_id: str | None,
    config_path: Path,
    llm_provider: LLMProvider | None = None,
) -> int:
    """Run the complete content generation pipeline.

    Args:
        app_paths: Resolved app paths.
        seed: Story seed/description.
        beats: Number of outline beats (None for app-defined default).
        run_id: Optional run ID override.
        config_path: Path to configuration directory.
        llm_provider: Optional LLM provider (for testing). If None, creates from config.

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
        )

        logger = get_run_logger(run_dir)

        # Basic CLI progress output so runs don't feel "silent"
        print(
            f"[llm_storytell] Initialized run '{run_dir.name}' "
            f"for app '{app_paths.app_name}'.",
            flush=True,
        )
        print(f"[llm_storytell] Run directory: {run_dir}", flush=True)

        # Select context files and update state
        selected_context = _select_context_files(
            context_dir=app_paths.context_dir,
            run_id=run_dir.name,
            logger=logger,
        )
        _update_state_selected_context(run_dir, selected_context)

        # Create or use provided LLM provider
        if llm_provider is None:
            llm_provider = _create_llm_provider_from_config(config_path)

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
        print(
            f"[llm_storytell] Pipeline completed successfully. "
            f"Artifacts are in: {run_dir / 'artifacts'}",
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

        # Resolve app paths
        app_paths = resolve_app_or_exit(args.app)

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

        # Validate beats range if provided
        if beats is not None and (beats < 1 or beats > 20):
            print(
                "Error: --beats must be between 1 and 20 (inclusive)",
                file=sys.stderr,
            )
            return 1

        # Use default beats if not provided (app-defined default would go here in future)
        # For v1.0, use 5 as a reasonable default
        if beats is None:
            beats = 5

        # Run the pipeline
        return _run_pipeline(
            app_paths=app_paths,
            seed=args.seed,
            beats=beats,
            run_id=args.run_id,
            config_path=args.config_path,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
