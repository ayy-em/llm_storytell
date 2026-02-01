"""Command-line interface for llm_storytell."""

import argparse
import sys
from pathlib import Path

from llm_storytell.config import (
    AppConfigError,
    AppNotFoundError,
    AppPaths,
    load_app_config,
    resolve_app,
)
from llm_storytell.pipeline.resolve import resolve_run_settings
from llm_storytell.pipeline.runner import run_pipeline


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
    run_parser.add_argument(
        "--tts",
        action="store_true",
        help="Enable TTS (text-to-speech) after critic step (default).",
    )
    run_parser.add_argument(
        "--no-tts",
        action="store_true",
        help="Disable TTS; pipeline ends after critic step.",
    )
    run_parser.add_argument(
        "--tts-provider",
        required=False,
        help="TTS provider (e.g. openai). Overrides app config. Resolution: CLI → app_config → default.",
    )
    run_parser.add_argument(
        "--tts-voice",
        required=False,
        help="TTS voice name (e.g. Onyx). Overrides app config. Resolution: CLI → app_config → default.",
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
        if not args.seed:
            print("Error: --seed is required for 'run' command", file=sys.stderr)
            parser.print_help()
            return 1

        base_dir = Path.cwd()
        app_paths = resolve_app_or_exit(args.app, base_dir)

        try:
            app_config = load_app_config(
                app_paths.app_name,
                base_dir=base_dir,
                app_root=app_paths.app_root,
            )
        except AppConfigError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        beats = args.beats
        if args.sections is not None:
            if beats is not None:
                print(
                    "Warning: Both --beats and --sections specified. Using --beats.",
                    file=sys.stderr,
                )
            else:
                beats = args.sections

        word_count: int | None = getattr(args, "word_count", None)
        if word_count is not None:
            if word_count <= 100 or word_count >= 15000:
                print(
                    "Error: --word-count must be greater than 100 and less than 15000",
                    file=sys.stderr,
                )
                return 1

        if word_count is not None and beats is not None:
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

        if word_count is None and beats is not None and (beats < 1 or beats > 20):
            print(
                "Error: --beats must be between 1 and 20 (inclusive)",
                file=sys.stderr,
            )
            return 1

        tts_enabled = not getattr(args, "no_tts", False)
        tts_provider = getattr(args, "tts_provider", None) or app_config.tts_provider
        tts_voice = getattr(args, "tts_voice", None) or app_config.tts_voice

        settings = resolve_run_settings(
            app_paths,
            app_config,
            args.seed,
            beats_arg=beats,
            sections_arg=args.sections,
            word_count=word_count,
            section_length_arg=args.section_length,
            model_arg=args.model,
            tts_enabled=tts_enabled,
            tts_provider=tts_provider,
            tts_voice=tts_voice,
            run_id=args.run_id,
            config_path=args.config_path,
        )

        return run_pipeline(settings)

    return 0


if __name__ == "__main__":
    sys.exit(main())
