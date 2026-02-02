"""Audio-prep pipeline step: stitch TTS segments, add background music, mix."""

from __future__ import annotations

import subprocess
from pathlib import Path

from llm_storytell.logging import RunLogger

# Segment limits (must match llm_tts step)
MAX_SEGMENTS = 22
MIN_SEGMENTS = 1


class AudioPrepStepError(Exception):
    """Raised when the audio-prep step fails."""

    pass


def _get_app_name(run_dir: Path) -> str:
    """Read app name from run_dir/inputs.json."""
    from llm_storytell.pipeline.state import StateIOError, load_inputs

    try:
        data = load_inputs(run_dir)
    except StateIOError as e:
        raise AudioPrepStepError(str(e)) from e
    app = data.get("app")
    if not app:
        raise AudioPrepStepError("inputs.json missing 'app'")
    return str(app)


def _discover_segments(run_dir: Path) -> tuple[list[Path], str]:
    """Find segment files in run_dir/tts/outputs/ in order (segment_01, segment_02, ...).

    Returns:
        (ordered list of paths, extension including dot e.g. '.mp3').
    """
    outputs_dir = run_dir / "tts" / "outputs"
    if not outputs_dir.is_dir():
        raise AudioPrepStepError(f"TTS outputs directory not found: {outputs_dir}")

    segments: list[Path] = []
    ext: str | None = None
    for i in range(1, MAX_SEGMENTS + 1):
        # Try common extensions if we don't know yet
        if ext is None:
            for e in (".mp3", ".wav", ".m4a", ".ogg"):
                p = outputs_dir / f"segment_{i:02d}{e}"
                if p.exists():
                    segments.append(p)
                    ext = e
                    break
            if ext is None and i == 1:
                raise AudioPrepStepError(f"No segment_01.* found in {outputs_dir}")
            if ext is None:
                break
        else:
            p = outputs_dir / f"segment_{i:02d}{ext}"
            if not p.exists():
                break
            segments.append(p)

    if not segments:
        raise AudioPrepStepError(f"No segment files found in {outputs_dir}")
    if len(segments) > MAX_SEGMENTS:
        raise AudioPrepStepError(
            f"Found {len(segments)} segments; max is {MAX_SEGMENTS}"
        )
    return segments, ext


def _run_ffmpeg(args: list[str], error_context: str) -> None:
    """Run ffmpeg; raise AudioPrepStepError on non-zero exit."""
    result = subprocess.run(
        ["ffmpeg", "-y", *args],
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode != 0:
        stderr = (result.stderr or "").strip() or "(no stderr)"
        raise AudioPrepStepError(
            f"{error_context}: ffmpeg exited {result.returncode}; stderr: {stderr}"
        )


def _run_ffprobe(args: list[str], error_context: str) -> str:
    """Run ffprobe and return stdout; raise AudioPrepStepError on non-zero exit."""
    result = subprocess.run(
        ["ffprobe", *args],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        stderr = (result.stderr or "").strip() or "(no stderr)"
        raise AudioPrepStepError(
            f"{error_context}: ffprobe exited {result.returncode}; stderr: {stderr}"
        )
    return (result.stdout or "").strip()


def _get_duration_seconds(path: Path) -> float:
    """Return duration of audio file in seconds via ffprobe."""
    out = _run_ffprobe(
        [
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        f"get duration of {path}",
    )
    if not out:
        raise AudioPrepStepError(f"ffprobe returned no duration for {path}")
    try:
        return float(out)
    except ValueError as e:
        raise AudioPrepStepError(f"Invalid duration from ffprobe: {out}") from e


def _stitch_segments(
    run_dir: Path,
    segments: list[Path],
    ext: str,
    logger: RunLogger,
) -> Path:
    """Concat segment files into one voiceover file under run_dir/voiceover/."""
    voiceover_dir = run_dir / "voiceover"
    voiceover_dir.mkdir(parents=True, exist_ok=True)
    out_path = voiceover_dir / f"voiceover{ext}"

    # Concat list file: "file 'path'" per line (escape single quotes in path)
    list_path = voiceover_dir / "concat_list.txt"
    lines = []
    for p in segments:
        escaped = str(p).replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
    list_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    _run_ffmpeg(
        [
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
            "-c",
            "copy",
            str(out_path),
        ],
        "stitch segments",
    )
    size = out_path.stat().st_size
    logger.log_artifact_write(Path("voiceover") / out_path.name, size)
    return out_path


def _resolve_bg_music(base_dir: Path, app_name: str) -> Path:
    """Resolve background music: apps/<app>/assets/bg-music.* else assets/default-bg-music.wav."""
    base_dir = base_dir.resolve()
    app_assets = base_dir / "apps" / app_name / "assets"
    if app_assets.is_dir():
        matches = sorted(app_assets.glob("bg-music.*"))
        if matches:
            return matches[0]
    default_path = base_dir / "assets" / "default-bg-music.wav"
    if default_path.exists():
        return default_path
    raise AudioPrepStepError(
        f"No background music found: tried {app_assets / 'bg-music.*'} and {default_path}"
    )


def _build_looped_bg_with_crossfade(
    bg_path: Path,
    total_seconds: float,
    run_dir: Path,
    logger: RunLogger,
) -> Path:
    """Create a looped bg track of length total_seconds with 2s crossfade at loop points."""
    duration_out = _run_ffprobe(
        [
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(bg_path),
        ],
        f"get duration of {bg_path}",
    )
    try:
        bg_duration = float(duration_out.strip())
    except ValueError:
        raise AudioPrepStepError(f"Invalid bg duration: {duration_out}")

    voiceover_dir = run_dir / "voiceover"
    voiceover_dir.mkdir(parents=True, exist_ok=True)
    looped_path = voiceover_dir / "bg_looped.wav"

    if bg_duration <= 2:
        # No crossfade: just loop and trim
        n = max(1, int(total_seconds / bg_duration) + 1)
        _run_ffmpeg(
            [
                "-stream_loop",
                str(n),
                "-i",
                str(bg_path),
                "-t",
                str(total_seconds),
                "-c",
                "copy",
                str(looped_path),
            ],
            "loop bg (no crossfade)",
        )
    else:
        # N copies with 2s crossfade between them
        # n copies give length n*bg_duration - (n-1)*2 >= total_seconds
        n = max(1, int((total_seconds - 2) / (bg_duration - 2)) + 1)
        if n == 1:
            _run_ffmpeg(
                [
                    "-i",
                    str(bg_path),
                    "-t",
                    str(total_seconds),
                    "-c",
                    "copy",
                    str(looped_path),
                ],
                "trim single bg",
            )
        else:
            # Build filter: [0:a][1:a]acrossfade -> [o1]; [o1][2:a]acrossfade -> [o2]; ...; [o(n-1)]atrim
            inputs = ["-i", str(bg_path)] * n
            if n == 2:
                filter_complex = (
                    f"[0:a][1:a]acrossfade=d=2:c1=2:c2=2[o1];"
                    f"[o1]atrim=0:{total_seconds},asetpts=PTS-STARTPTS[out]"
                )
            else:
                parts = []
                parts.append("[0:a][1:a]acrossfade=d=2:c1=2:c2=2[o1]")
                for i in range(2, n):
                    parts.append(f"[o{i - 1}][{i}:a]acrossfade=d=2:c1=2:c2=2[o{i}]")
                parts.append(
                    f"[o{n - 1}]atrim=0:{total_seconds},asetpts=PTS-STARTPTS[out]"
                )
                filter_complex = ";".join(parts)
            _run_ffmpeg(
                inputs
                + [
                    "-filter_complex",
                    filter_complex,
                    "-map",
                    "[out]",
                    "-c:a",
                    "pcm_s16le",
                    str(looped_path),
                ],
                "loop bg with crossfade",
            )
    logger.info(f"Looped background music to {total_seconds}s")
    return looped_path


def _apply_bg_volume_envelope(
    looped_bg_path: Path,
    voice_duration: float,
    run_dir: Path,
) -> Path:
    """Apply volume envelope to bg: 0-1.5s 75%, 1.5-3s fade to 10%, 10% during narration, after fade to 70% over 2s."""
    voiceover_dir = run_dir / "voiceover"
    enveloped_path = voiceover_dir / "bg_enveloped.wav"
    v = voice_duration
    # ffmpeg volume expression: 0-1.5 -> 0.75, 1.5-3 -> linear to 0.1, 3-v -> 0.1, v to v+2 -> linear to 0.7, rest 0.7
    # Commas inside -af separate filters; escape literal commas in the expression so ffmpeg parses one volume filter
    expr = (
        f"if(lt(t,1.5),0.75,"
        f"if(lt(t,3),0.75-(t-1.5)/1.5*0.65,"
        f"if(lt(t,{v}),0.1,"
        f"if(lt(t,{v + 2}),0.1+(t-{v})/2*0.6,0.7))))"
    )
    expr_escaped = expr.replace(",", "\\,")
    _run_ffmpeg(
        [
            "-i",
            str(looped_bg_path),
            "-af",
            f"volume={expr_escaped}",
            "-c:a",
            "pcm_s16le",
            str(enveloped_path),
        ],
        "apply bg volume envelope",
    )
    return enveloped_path


def _mix_voiceover_and_bg(
    voiceover_path: Path,
    bg_path: Path,
    out_path: Path,
    run_dir: Path,
    logger: RunLogger,
    ext: str,
) -> None:
    """Mix voiceover and background; write to out_path.

    The voiceover track's volume is increased by 50% (factor 1.5).
    """
    if ext.lower() == ".wav":
        codec_args = ["-c:a", "pcm_s16le"]
    else:
        codec_args = ["-c:a", "libmp3lame", "-q:a", "2"]
    _run_ffmpeg(
        [
            "-i",
            str(voiceover_path),
            "-i",
            str(bg_path),
            "-filter_complex",
            # 1.5x gain for [0:a], then amix with [1:a]:
            "[0:a]volume=1.5[a1];[a1][1:a]amix=inputs=2:duration=first[aout]",
            "-map",
            "[aout]",
            *codec_args,
            str(out_path),
        ],
        "mix voiceover and bg with boosted voiceover volume",
    )
    size = out_path.stat().st_size
    rel = out_path.relative_to(run_dir)
    logger.log_artifact_write(rel, size)


def execute_audio_prep_step(
    run_dir: Path,
    base_dir: Path,
    logger: RunLogger,
    *,
    app_name: str | None = None,
) -> None:
    """Stitch TTS segments, add background music with envelope, mix to final narration.

    Steps:
    1. Stitch segments from run_dir/tts/outputs/ into one voiceover track.
    2. Get voiceover duration.
    3. Load bg music: apps/<app_name>/assets/bg-music.* if exists, else assets/default-bg-music.wav.
    4. Loop bg with 2s crossfade to duration + 6s.
    5. Apply bg volume envelope (0-1.5s 75%, 1.5-3s fade to 10%, 10% during narration, after fade to 70% over 2s).
    6. Mix voiceover + bg; write to run_dir/artifacts/narration-<app_name>.<ext>.

    Args:
        run_dir: Run directory (runs/<run_id>/).
        base_dir: Project root (contains runs/, apps/, assets/).
        logger: Run logger.
        app_name: App name for output filename and bg path; if None, read from run_dir/inputs.json.

    Raises:
        AudioPrepStepError: On missing inputs, ffmpeg/ffprobe failure, or no bg music found.
    """
    run_dir = run_dir.resolve()
    base_dir = base_dir.resolve()

    if app_name is None:
        app_name = _get_app_name(run_dir)

    segments, ext = _discover_segments(run_dir)
    logger.info(f"Stitching {len(segments)} segments")

    voiceover_path = _stitch_segments(run_dir, segments, ext, logger)
    voice_duration = _get_duration_seconds(voiceover_path)
    logger.info(f"Voiceover duration: {voice_duration:.2f}s")

    bg_target_length = voice_duration + 6.0
    bg_path = _resolve_bg_music(base_dir, app_name)
    logger.info(f"Background music: {bg_path}")

    looped_bg = _build_looped_bg_with_crossfade(
        bg_path, bg_target_length, run_dir, logger
    )
    enveloped_bg = _apply_bg_volume_envelope(looped_bg, voice_duration, run_dir)

    artifacts_dir = run_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    out_path = artifacts_dir / f"narration-{app_name}{ext}"

    _mix_voiceover_and_bg(voiceover_path, enveloped_bg, out_path, run_dir, logger, ext)
    logger.info(f"Audio-prep complete: {out_path}")
