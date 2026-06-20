"""Re-stitch ``voiceover/voiceover.<ext>`` from ``tts/outputs/segment_*`` (no polish, no mix).

Uses ffmpeg concat with stream copy so the result matches a lossless join of the segment
files. Run from project root::

    uv run python scripts/stitch_voiceover.py --run-id run-20260509-004345
"""

from __future__ import annotations

import argparse
from pathlib import Path

from llm_storytell.run_dir import get_run_logger
from llm_storytell.steps.audio_prep import AudioPrepStepError, stitch_voiceover_from_tts_segments


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def main() -> None:
    p = argparse.ArgumentParser(
        description="Rebuild voiceover/voiceover.<ext> from tts/outputs/segment_* (ffmpeg -c copy)."
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
    args = p.parse_args()

    root = Path(args.base_dir).resolve() if args.base_dir else _project_root()
    run_dir = root / "runs" / args.run_id
    if not run_dir.is_dir():
        raise SystemExit(f"Run directory not found: {run_dir}")

    log_path = run_dir / "run.log"
    log_path.touch(exist_ok=True)
    logger = get_run_logger(run_dir)

    try:
        out = stitch_voiceover_from_tts_segments(run_dir, logger)
    except AudioPrepStepError as e:
        raise SystemExit(str(e)) from e

    print(f"[stitch_voiceover] Wrote {out}", flush=True)


if __name__ == "__main__":
    main()
