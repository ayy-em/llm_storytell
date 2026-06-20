"""Final narration mix: ``voiceover/voiceover.<ext>`` + ``voiceover/bg_enveloped.wav`` → ``artifacts/story-...``.

Skips stitch, polish, bg loop, and envelope. Requires both files already in the run folder.

From project root::

    uv run python scripts/mix_story_audio.py --run-id run-20260509-004345

Optional mix timing (defaults match audio-prep: 3s intro / 3s outro padding)::

    uv run python scripts/mix_story_audio.py --run-id run-20260509-004345 --voiceover-mix-gain 1.3
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from llm_storytell.run_dir import get_run_logger
from llm_storytell.steps.audio_prep import AudioPrepStepError, finalize_story_audio_mix


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def main() -> None:
    p = argparse.ArgumentParser(
        description="Mix existing voiceover + bg_enveloped.wav into artifacts/story-<...>.mp3 (or same ext as voiceover)."
    )
    p.add_argument(
        "--run-id",
        required=True,
        help='Run folder under runs/, e.g. "run-20260509-004345"',
    )
    p.add_argument(
        "--base-dir",
        default=None,
        help="Project root (default: parent of scripts/)",
    )
    p.add_argument("--voiceover-mix-gain", type=float, default=None)
    p.add_argument("--pad-start", type=float, default=None)
    p.add_argument("--pad-end", type=float, default=None)
    p.add_argument(
        "--app-name",
        default=None,
        help="Override app name (default: inputs.json)",
    )
    args = p.parse_args()

    root = Path(args.base_dir).resolve() if args.base_dir else _project_root()
    run_dir = root / "runs" / args.run_id
    if not run_dir.is_dir():
        raise SystemExit(f"Run directory not found: {run_dir}")

    log_path = run_dir / "run.log"
    log_path.touch(exist_ok=True)
    logger = get_run_logger(run_dir)

    kw: dict[str, Any] = {}
    if args.voiceover_mix_gain is not None:
        kw["voiceover_mix_gain"] = args.voiceover_mix_gain
    if args.pad_start is not None:
        kw["pad_start"] = args.pad_start
    if args.pad_end is not None:
        kw["pad_end"] = args.pad_end
    if args.app_name is not None:
        kw["app_name"] = args.app_name

    try:
        out = finalize_story_audio_mix(run_dir, root, logger, **kw)
    except AudioPrepStepError as e:
        raise SystemExit(str(e)) from e

    print(f"[mix_story_audio] Wrote {out}", flush=True)


if __name__ == "__main__":
    main()
