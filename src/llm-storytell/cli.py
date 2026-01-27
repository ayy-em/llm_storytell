"""Command-line interface for llm-storytell."""

import argparse
import sys
from pathlib import Path

from .config import AppNotFoundError, AppPaths, resolve_app


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        prog="llm-storytell",
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
        # Resolve app paths
        app_paths = resolve_app_or_exit(args.app)

        # For now, just print the resolved paths (pipeline execution comes later)
        print(f"App: {app_paths.app_name}")
        print(f"Context directory: {app_paths.context_dir}")
        print(f"Prompts directory: {app_paths.prompts_dir}")

        # TODO: T0002+ will implement actual pipeline execution
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
