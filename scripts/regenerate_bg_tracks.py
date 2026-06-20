"""Rebuild ``voiceover/bg_looped.wav`` and ``voiceover/bg_enveloped.wav`` from ``voiceover/voiceover.*``.

Uses the current duration of ``voiceover/voiceover.<ext>`` (e.g. after manual slowdown), same
loop length and envelope timing as the main audio-prep step. Does not touch the voiceover file
or write the final mixed artifact.

Run from project root::

    uv run python scripts/regenerate_bg_tracks.py --run-id run-20260509-004345

With explicit background source and optional ``--bg-volume-scale`` (same envelope as main prep)::

    uv run python scripts/regenerate_bg_tracks.py \\
        --run-id run-20260509-004345 \\
        --bg-music apps/irindica_truecrime/assets/bg-music.mp3
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from llm_storytell.run_dir import get_run_logger
from llm_storytell.steps.audio_prep import AudioPrepStepError, rebuild_background_loop_and_envelope


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def main() -> None:
    p = argparse.ArgumentParser(
        description="Regenerate bg_looped.wav and bg_enveloped.wav from existing voiceover/voiceover.*"
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
    p.add_argument(
        "--bg-music",
        default=None,
        help="Background file to loop (default: resolve from app assets / default-bg-music)",
    )
    p.add_argument("--bg-volume-scale", type=float, default=None)
    p.add_argument("--pad-start", type=float, default=None)
    p.add_argument("--pad-end", type=float, default=None)
    p.add_argument("--bg-duck-ramp", type=float, default=None)
    p.add_argument("--bg-loop-crossfade", type=float, default=None)
    p.add_argument(
        "--app-name",
        default=None,
        help="Override app name for bg resolution (default: inputs.json)",
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
    if args.bg_music is not None:
        kw["bg_music_path"] = Path(args.bg_music).expanduser()
    if args.bg_volume_scale is not None:
        kw["bg_volume_scale"] = args.bg_volume_scale
    if args.pad_start is not None:
        kw["pad_start"] = args.pad_start
    if args.pad_end is not None:
        kw["pad_end"] = args.pad_end
    if args.bg_duck_ramp is not None:
        kw["bg_duck_ramp"] = args.bg_duck_ramp
    if args.bg_loop_crossfade is not None:
        kw["bg_loop_crossfade"] = args.bg_loop_crossfade
    if args.app_name is not None:
        kw["app_name"] = args.app_name

    try:
        looped, enveloped = rebuild_background_loop_and_envelope(
            run_dir,
            root,
            logger,
            **kw,
        )
    except AudioPrepStepError as e:
        raise SystemExit(str(e)) from e

    print(f"[regenerate_bg_tracks] Wrote\n  {looped}\n  {enveloped}", flush=True)


if __name__ == "__main__":
    main()
