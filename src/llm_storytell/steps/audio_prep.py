"""Audio-prep pipeline step: stitch TTS segments, add background music, mix."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from llm_storytell.logging import RunLogger

# Segment limits (must match llm_tts step)
MAX_SEGMENTS = 22
MIN_SEGMENTS = 1


class AudioPrepStepError(Exception):
    """Raised when the audio-prep step fails."""

    pass


def _sanitize_filename_part(s: str) -> str:
    """Replace characters unsafe in filenames with underscore."""
    if not s or not isinstance(s, str):
        return "unknown"
    return re.sub(r"[^\w\-.]", "_", s.strip()).strip(".") or "unknown"


def _parse_run_id_dd_mm(run_id: str) -> tuple[str, str]:
    """Parse run-YYYYMMDD-HHMMSS to (dd, mm) as two-digit strings. Returns ('00','00') if not matching."""
    if not run_id or not isinstance(run_id, str):
        return "00", "00"
    m = re.match(r"run-(\d{4})(\d{2})(\d{2})", run_id.strip())
    if not m:
        return "00", "00"
    _yyyy, mm, dd = m.group(1), m.group(2), m.group(3)
    return dd, mm


def _voiceover_artifact_filename(run_dir: Path, app_name: str, ext: str) -> str:
    """Build story-{app}-{llm_model}-{tts_model}-{tts_voice}-{dd}-{mm}{ext} from run_dir state/inputs."""
    from llm_storytell.pipeline.state import StateIOError, load_inputs, load_state

    llm_model = "unknown"
    tts_model = "unknown"
    tts_voice = "unknown"
    dd, mm = "00", "00"

    try:
        inputs_data = load_inputs(run_dir)
        llm_model = str(inputs_data.get("model") or "unknown").strip()
        run_id = inputs_data.get("run_id") or run_dir.name
        dd, mm = _parse_run_id_dd_mm(str(run_id))
    except StateIOError:
        pass

    try:
        state = load_state(run_dir)
        tts_cfg = state.get("tts_config") or {}
        tts_model = str(tts_cfg.get("tts_model") or "unknown").strip()
        tts_voice = str(tts_cfg.get("tts_voice") or "unknown").strip()
    except StateIOError:
        pass

    app = _sanitize_filename_part(app_name)
    llm = _sanitize_filename_part(llm_model)
    tts_m = _sanitize_filename_part(tts_model)
    tts_v = _sanitize_filename_part(tts_voice)
    return f"story-{app}-{llm}-{tts_m}-{tts_v}-{dd}-{mm}{ext}"


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


# Single-pass voiceover polish: clean rumble/harshness, normalize, light reverb, de-ess, limit
VOICEOVER_POLISH_AF = (
    "highpass=f=80,lowpass=f=16000,"
    "equalizer=f=3000:t=q:w=1.2:g=-2,dynaudnorm=f=150:g=7,"
    "aecho=0.8:0.88:20|40:0.15|0.10,highpass=f=80,"
    "equalizer=f=7500:t=q:w=1.0:g=-4,equalizer=f=9500:t=q:w=1.0:g=-2,"
    "alimiter=limit=0.97"
)


def _apply_voiceover_polish(
    voiceover_path: Path,
    ext: str,
    logger: RunLogger,
) -> None:
    """Apply polish (clean, reverb, de-ess, limit) to stitched voiceover in place."""
    voiceover_dir = voiceover_path.parent
    polished_path = voiceover_dir / f"voiceover_polished{ext}"

    _run_ffmpeg(
        [
            "-i",
            str(voiceover_path),
            "-af",
            VOICEOVER_POLISH_AF,
            str(polished_path),
        ],
        "voiceover polish (clean, reverb, de-ess, limit)",
    )
    polished_path.replace(voiceover_path)
    size = voiceover_path.stat().st_size
    logger.log_artifact_write(Path("voiceover") / voiceover_path.name, size)
    logger.info("Voiceover polish applied")


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


# Crossfade duration (seconds) at loop points when building looped bg track
BG_LOOP_CROSSFADE = 5


def _build_looped_bg_with_crossfade(
    bg_path: Path,
    total_seconds: float,
    run_dir: Path,
    logger: RunLogger,
) -> Path:
    """Create a looped bg track of length total_seconds with crossfade at loop points."""
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
    d = BG_LOOP_CROSSFADE

    if bg_duration <= d:
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
        # N copies with d-second crossfade between them
        # n copies give length n*bg_duration - (n-1)*d >= total_seconds
        n = max(1, int((total_seconds - d) / (bg_duration - d)) + 1)
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
                    f"[0:a][1:a]acrossfade=d={d}:c1={d}:c2={d}[o1];"
                    f"[o1]atrim=0:{total_seconds},asetpts=PTS-STARTPTS[out]"
                )
            else:
                parts = []
                parts.append(f"[0:a][1:a]acrossfade=d={d}:c1={d}:c2={d}[o1]")
                for i in range(2, n):
                    parts.append(
                        f"[o{i - 1}][{i}:a]acrossfade=d={d}:c1={d}:c2={d}[o{i}]"
                    )
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


# Intro/outro padding (seconds): voiceover sits from PAD_START to PAD_START+voice_duration on the track.
PAD_START = 3
PAD_END = 3


def _apply_bg_volume_envelope(
    looped_bg_path: Path,
    voice_duration: float,
    run_dir: Path,
) -> Path:
    """Apply volume envelope to bg: 0-3s 65%→5%, 3s to (3+voice) at 5%, last 3s 5%→65%."""
    voiceover_dir = run_dir / "voiceover"
    enveloped_path = voiceover_dir / "bg_enveloped.wav"
    v = voice_duration
    flat_end = PAD_START + v
    end_fade_end = PAD_START + PAD_END + v
    # 0-3s: 65%→5%; 3 to 3+v: 5%; 3+v to 3+v+3: 5%→65%
    # Commas inside -af separate filters; escape literal commas so ffmpeg parses one volume filter
    expr = (
        f"if(lt(t,{PAD_START}),0.65-t/{PAD_START}*0.35,"
        f"if(lt(t,{flat_end}),0.05,"
        f"if(lt(t,{end_fade_end}),0.05+(t-{flat_end})/{PAD_END}*0.65,0.75)))"
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
    voice_duration: float,
) -> None:
    """Mix voiceover and background; write to out_path.

    Voiceover is placed from PAD_START to PAD_START+voice_duration on the track
    (3s intro of music only, then voice+music, then PAD_END s of music only).
    Voice track gets 1.75x gain.
    """
    if ext.lower() == ".wav":
        codec_args = ["-c:a", "pcm_s16le"]
    else:
        codec_args = ["-c:a", "libmp3lame", "-q:a", "2"]
    delay_ms = int(PAD_START * 1000)
    # Delay voice by PAD_START so it starts at 3s; pad end by PAD_END so total = bg length
    filter_complex = (
        f"[0:a]volume=1.75,adelay={delay_ms}|{delay_ms},apad=pad_dur={PAD_END}[vo];"
        "[vo][1:a]amix=inputs=2:duration=first[aout]"
    )
    _run_ffmpeg(
        [
            "-i",
            str(voiceover_path),
            "-i",
            str(bg_path),
            "-filter_complex",
            filter_complex,
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
    """Stitch TTS segments, polish voiceover, add background music with envelope, mix to final narration.

    Steps:
    1. Stitch segments from run_dir/tts/outputs/ into one voiceover track.
    2. Apply voiceover polish (highpass/lowpass, EQ, dynaudnorm, reverb, de-ess, limiter).
    3. Get voiceover duration.
    4. Load bg music: apps/<app_name>/assets/bg-music.* if exists, else assets/default-bg-music.wav.
    5. Loop bg with crossfade to voice_duration + 6s (3s intro + voice + 3s outro).
    6. Apply bg volume envelope: 0-3s 65%→5%, 3s to (3+voice_duration) at 5%, last 3s 5%→65%.
    7. Mix: voiceover placed from 00m03s to (3+voice_duration)s on the track; write to run_dir/artifacts/story-<app>-<llm_model>-<tts_model>-<tts_voice>-<dd>-<mm>.<ext>.

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
    _apply_voiceover_polish(voiceover_path, ext, logger)
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
    out_name = _voiceover_artifact_filename(run_dir, app_name, ext)
    out_path = artifacts_dir / out_name

    _mix_voiceover_and_bg(
        voiceover_path, enveloped_bg, out_path, run_dir, logger, ext, voice_duration
    )
    logger.info(f"Audio-prep complete: {out_path}")
