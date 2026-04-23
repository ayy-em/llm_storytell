"""Manual audio-prep tweaks: custom background file, mix levels, envelope timing.

Run from project root, for example::

    uv run python scripts/audio_tweak.py \\
        --bg-music /path/to/theme.wav \\
        --run-id run-20260408-015251 \\
        --voiceover-mix-gain 1.4 \\
        --bg-volume-scale 0.45

Or import ``run_audio_tweak`` and pass the same options as keyword arguments to
``execute_audio_prep_step`` (except ``bg_music_path``, which maps from ``bg_music_filepath``).
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from llm_storytell.run_dir import get_run_logger
from llm_storytell.steps.audio_prep import AudioPrepStepError, execute_audio_prep_step


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def run_audio_tweak(
    bg_music_filepath: str,
    run_id: str,
    *,
    base_dir: Path | str | None = None,
    **kwargs: Any,
) -> None:
    """Re-run audio prep for an existing run using a chosen background track and optional overrides.

    ``run_id`` is the folder name under ``runs/`` (e.g. ``run-20260408-015251``).

    Additional keyword arguments are forwarded to ``execute_audio_prep_step`` (see that
    function's docstring). Common examples:

    - ``voiceover_mix_gain``: linear gain on the voice in the final mix (default 1.25).
    - ``bg_volume_scale``: scales background envelope loudness (default module constant).
    - ``pad_start`` / ``pad_end``: intro/outro padding in seconds (defaults 3 / 3).
    - ``bg_duck_ramp``: seconds to ramp bg into the duck level after intro.
    - ``bg_loop_crossfade``: crossfade length when looping the bg file.
    - ``apply_voiceover_polish`` / ``voiceover_polish_af``: control the polish ffmpeg chain.
    - ``use_existing_voiceover``: if True, use ``voiceover/voiceover.<ext>`` and skip stitch.

    Args:
        bg_music_filepath: Path to the background music file to loop and envelope.
        run_id: Run directory name under ``runs/``.
        base_dir: Project root; default is the repo root (parent of ``scripts/``).
        **kwargs: Passed to ``execute_audio_prep_step`` after ``bg_music_path=...``.
    """
    root = Path(base_dir).resolve() if base_dir is not None else _project_root()
    run_dir = root / "runs" / run_id
    if not run_dir.is_dir():
        raise AudioPrepStepError(f"Run directory not found: {run_dir}")

    log_path = run_dir / "run.log"
    log_path.touch(exist_ok=True)
    logger = get_run_logger(run_dir)

    execute_audio_prep_step(
        run_dir,
        root,
        logger,
        bg_music_path=Path(bg_music_filepath).expanduser(),
        **kwargs,
    )


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Manual audio-prep with explicit background music and optional mix/envelope tweaks."
    )
    p.add_argument(
        "--bg-music",
        required=True,
        dest="bg_music_filepath",
        help="Path to background music file",
    )
    p.add_argument(
        "--run-id",
        required=True,
        help='Run folder name under runs/, e.g. "run-20260408-015251"',
    )
    p.add_argument(
        "--base-dir",
        default=None,
        help="Project root (default: parent of scripts/)",
    )
    p.add_argument("--voiceover-mix-gain", type=float, default=None)
    p.add_argument("--bg-volume-scale", type=float, default=None)
    p.add_argument("--pad-start", type=float, default=None)
    p.add_argument("--pad-end", type=float, default=None)
    p.add_argument("--bg-duck-ramp", type=float, default=None)
    p.add_argument("--bg-loop-crossfade", type=float, default=None)
    p.add_argument(
        "--no-voiceover-polish",
        action="store_true",
        help="Skip the voiceover polish ffmpeg pass",
    )
    p.add_argument(
        "--use-existing-voiceover",
        action="store_true",
        help="Use voiceover/voiceover.<ext>; do not stitch from tts/outputs/",
    )
    p.add_argument(
        "--app-name",
        default=None,
        help="Override app name (default: read from inputs.json)",
    )
    return p


def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()
    kw: dict[str, Any] = {}
    if args.voiceover_mix_gain is not None:
        kw["voiceover_mix_gain"] = args.voiceover_mix_gain
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
    if args.no_voiceover_polish:
        kw["apply_voiceover_polish"] = False
    if args.use_existing_voiceover:
        kw["use_existing_voiceover"] = True
    if args.app_name is not None:
        kw["app_name"] = args.app_name

    run_audio_tweak(
        args.bg_music_filepath,
        args.run_id,
        base_dir=args.base_dir,
        **kw,
    )


if __name__ == "__main__":
    main()
