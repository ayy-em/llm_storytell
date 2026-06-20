"""Audio-prep pipeline step: stitch TTS segments, add background music, mix."""

from __future__ import annotations

import re
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

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


_CET = ZoneInfo("Europe/Berlin")


def _cet_dd_mm_stamp() -> str:
    """Current calendar day in Europe/Berlin (CET/CEST) as DD-MM (no year)."""
    return datetime.now(_CET).strftime("%d-%m")


def _cet_dd_mm_dot_title_prefix() -> str:
    """Current calendar day in Europe/Berlin (CET/CEST) as DD.MM for ID3 title prefix."""
    return datetime.now(_CET).strftime("%d.%m")


def _app_prefix_four_chars(name: str) -> str:
    """First four characters of the sanitized app name (for compact filenames)."""
    base = _sanitize_filename_part(name)
    return base[:4] if base else "unkn"


def _default_audio_title_from_seed(
    seed: str | None, fallback: str, *, max_len: int = 30
) -> str:
    """Collapse whitespace and truncate story seed for ID3 title (fits common TIT2 limits)."""
    if seed is None or not str(seed).strip():
        return fallback
    text = " ".join(str(seed).split())
    if len(text) <= max_len:
        return text
    return text[:max_len].rstrip()


def _voiceover_artifact_filename(run_dir: Path, app_name: str, ext: str) -> str:
    """Build story-{app4}-{llm_model}-{tts_model}-{tts_voice}-{DD-MM}{ext} (date in CET)."""
    from llm_storytell.pipeline.state import StateIOError, load_inputs, load_state

    llm_model = "unknown"
    tts_model = "unknown"
    tts_voice = "unknown"

    try:
        inputs_data = load_inputs(run_dir)
        llm_model = str(inputs_data.get("model") or "unknown").strip()
    except StateIOError:
        pass

    try:
        state = load_state(run_dir)
        tts_cfg = state.get("tts_config") or {}
        tts_model = str(tts_cfg.get("tts_model") or "unknown").strip()
        tts_voice = str(tts_cfg.get("tts_voice") or "unknown").strip()
    except StateIOError:
        pass

    app4 = _app_prefix_four_chars(app_name)
    llm = _sanitize_filename_part(llm_model)
    tts_m = _sanitize_filename_part(tts_model)
    tts_v = _sanitize_filename_part(tts_voice)
    dd_mm = _cet_dd_mm_stamp()
    return f"story-{app4}-{llm}-{tts_m}-{tts_v}-{dd_mm}{ext}"


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


def _resolve_existing_voiceover(run_dir: Path) -> tuple[Path, str]:
    """Return (path, ext with dot) for run_dir/voiceover/voiceover.<ext> if present."""
    voiceover_dir = run_dir / "voiceover"
    if not voiceover_dir.is_dir():
        raise AudioPrepStepError(f"Voiceover directory not found: {voiceover_dir}")
    for e in (".mp3", ".wav", ".m4a", ".ogg"):
        p = voiceover_dir / f"voiceover{e}"
        if p.is_file():
            return p, e
    raise AudioPrepStepError(
        f"No voiceover/voiceover.* found in {voiceover_dir} "
        "(expected e.g. voiceover.mp3 from a previous audio-prep run)"
    )


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


def stitch_voiceover_from_tts_segments(run_dir: Path, logger: RunLogger) -> Path:
    """Rebuild ``voiceover/voiceover.<ext>`` from ``tts/outputs/segment_*`` via ffmpeg concat (-c copy).

    Does not apply polish, atempo, or mixing. Use after manual experiments have altered
    ``voiceover/voiceover.*`` when the original per-segment TTS files are still intact.

    Args:
        run_dir: Run directory (runs/<run_id>/).
        logger: Run logger (e.g. from ``get_run_logger(run_dir)``).

    Returns:
        Path to the written ``voiceover/voiceover.<ext>``.

    Raises:
        AudioPrepStepError: If segments are missing or ffmpeg fails.
    """
    run_dir = run_dir.resolve()
    segments, ext = _discover_segments(run_dir)
    logger.info(f"Stitch-only: joining {len(segments)} TTS segment(s) → voiceover{ext}")
    return _stitch_segments(run_dir, segments, ext, logger)


def rebuild_background_loop_and_envelope(
    run_dir: Path,
    base_dir: Path,
    logger: RunLogger,
    *,
    app_name: str | None = None,
    bg_music_path: Path | str | None = None,
    bg_volume_scale: float | None = None,
    pad_start: float | None = None,
    pad_end: float | None = None,
    bg_duck_ramp: float | None = None,
    bg_loop_crossfade: float | None = None,
) -> tuple[Path, Path]:
    """Rebuild ``voiceover/bg_looped.wav`` and ``voiceover/bg_enveloped.wav`` from ``voiceover/voiceover.<ext>``.

    Uses ffprobe-measured duration of the existing stitched voiceover (e.g. after manual slowdown
    in a DAW) and the same looping / envelope logic as :func:`execute_audio_prep_step`. Does not
    alter the voiceover file or run the final mix.

    Args:
        run_dir: Run directory (runs/<run_id>/).
        base_dir: Project root (contains apps/, assets/).
        logger: Run logger.
        app_name: For resolving bg music path; if None, read from run_dir/inputs.json.
        bg_music_path: If set, use this file instead of app/default bg music.
        bg_volume_scale: Multiplies intro/body/outro BG levels (default 1).
        pad_start / pad_end: Timeline padding matching the eventual mix (defaults 3 / 3).
        bg_loop_crossfade: Crossfade when looping bg.
        bg_duck_ramp: Ignored (API compat).

    Returns:
        ``(bg_looped.wav path, bg_enveloped.wav path)`` under run_dir/voiceover/.

    Raises:
        AudioPrepStepError: If voiceover is missing or ffmpeg/ffprobe fails.
    """
    run_dir = run_dir.resolve()
    base_dir = base_dir.resolve()

    if app_name is None:
        app_name = _get_app_name(run_dir)

    voiceover_path, _ext = _resolve_existing_voiceover(run_dir)
    logger.info(f"BG rebuild: using voiceover {voiceover_path}")

    ps = PAD_START if pad_start is None else float(pad_start)
    pe = PAD_END if pad_end is None else float(pad_end)

    voice_duration = _get_duration_seconds(voiceover_path)
    logger.info(f"BG rebuild: voiceover duration {voice_duration:.2f}s")

    bg_target_length = voice_duration + ps + pe
    if bg_music_path is not None:
        bg_path = Path(bg_music_path).expanduser().resolve()
        if not bg_path.is_file():
            raise AudioPrepStepError(f"Background music file not found: {bg_path}")
    else:
        bg_path = _resolve_bg_music(base_dir, app_name)
    logger.info(f"BG rebuild: background source {bg_path}")

    looped_bg = _build_looped_bg_with_crossfade(
        bg_path,
        bg_target_length,
        run_dir,
        logger,
        crossfade_seconds=bg_loop_crossfade,
    )
    enveloped_bg = _apply_bg_volume_envelope(
        looped_bg,
        voice_duration,
        run_dir,
        pad_start=pad_start,
        pad_end=pad_end,
        bg_duck_ramp=bg_duck_ramp,
        bg_volume_scale=bg_volume_scale,
    )
    logger.info(f"BG rebuild complete: {looped_bg}, {enveloped_bg}")
    return looped_bg, enveloped_bg


# Single-pass voiceover polish: clean rumble/harshness, normalize, very light reverb, de-ess, limit
# Adjusted to minimize sudden boundary clicks:
#   - Short fade-in at t=0 only (do NOT use afade=t=out:st=0 — in ffmpeg that fades out from the
#     start of the stream and leaves the remainder silent).
#   - Limiter at end for peak control.
#   - Lower reverb and echo; increase dynaudnorm smoothness.
#   - Remove potential double-highpass (which can risk phase clicks).

VOICEOVER_POLISH_AF = (
    "afade=t=in:ss=0:d=0.03,"
    "highpass=f=80,lowpass=f=13500,"
    "equalizer=f=3000:t=q:w=1.2:g=-2,"
    "dynaudnorm=f=250:g=3:p=0.8:m=10,"
    "aecho=0.7:0.32:40|80:0.035|0.012,"
    "equalizer=f=5500:t=q:w=1.0:g=-2,"
    "equalizer=f=7500:t=q:w=1.5:g=-7,"
    "equalizer=f=9500:t=q:w=1.1:g=-5,"
    "alimiter=limit=0.95"
)


def _apply_voiceover_polish(
    voiceover_path: Path,
    ext: str,
    logger: RunLogger,
    *,
    polish_af: str | None = None,
) -> None:
    """Apply polish (clean, reverb, de-ess, limit) to stitched voiceover in place."""
    voiceover_dir = voiceover_path.parent
    polished_path = voiceover_dir / f"voiceover_polished{ext}"
    af = polish_af if polish_af is not None else VOICEOVER_POLISH_AF

    _run_ffmpeg(
        [
            "-i",
            str(voiceover_path),
            "-af",
            af,
            str(polished_path),
        ],
        "voiceover polish (clean, reverb, de-ess, limit)",
    )
    polished_path.replace(voiceover_path)
    size = voiceover_path.stat().st_size
    logger.log_artifact_write(Path("voiceover") / voiceover_path.name, size)
    logger.info("Voiceover polish applied")


def _apply_voiceover_atempo(
    voiceover_path: Path,
    ext: str,
    logger: RunLogger,
    tempo: float,
) -> None:
    """Scale voiceover playback speed with ffmpeg atempo (in place). tempo < 1 slows down."""
    t = float(tempo)
    if not (0.5 <= t <= 2.0):
        raise AudioPrepStepError(
            f"voiceover_atempo must be between 0.5 and 2.0 (ffmpeg atempo), got {tempo}"
        )
    voiceover_dir = voiceover_path.parent
    out_path = voiceover_dir / f"voiceover_atempo{ext}"
    _run_ffmpeg(
        [
            "-i",
            str(voiceover_path),
            "-af",
            f"atempo={t}",
            str(out_path),
        ],
        "voiceover tempo (atempo)",
    )
    out_path.replace(voiceover_path)
    size = voiceover_path.stat().st_size
    logger.log_artifact_write(Path("voiceover") / voiceover_path.name, size)
    logger.info(f"Voiceover tempo applied (atempo={t})")


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


ALBUM_COVER_FILENAME = "album-cover.png"


def _resolve_album_cover(base_dir: Path, app_name: str) -> Path | None:
    """Resolve album cover image for final audio metadata.

    First checks apps/<app_name>/assets/album-cover.png; if missing, checks
    base_dir/assets/album-cover.png. Returns path if either exists, else None.
    """
    base_dir = base_dir.resolve()
    app_cover = base_dir / "apps" / app_name / "assets" / ALBUM_COVER_FILENAME
    if app_cover.is_file():
        return app_cover
    default_cover = base_dir / "assets" / ALBUM_COVER_FILENAME
    if default_cover.is_file():
        return default_cover
    return None


# Crossfade duration (seconds) at loop points when building looped bg track
BG_LOOP_CROSSFADE = 5


def _build_looped_bg_with_crossfade(
    bg_path: Path,
    total_seconds: float,
    run_dir: Path,
    logger: RunLogger,
    *,
    crossfade_seconds: float | None = None,
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
    d = BG_LOOP_CROSSFADE if crossfade_seconds is None else float(crossfade_seconds)

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


# Intro/outro padding (seconds): VO starts after PAD_START music-only; PAD_END trailing music-only.
PAD_START = 3
PAD_END = 3

# Linear gain on bg_looped.wav (relative to nominal full scale); voice stays at nominal 1.0 (see ``voiceover_mix_gain``).
BG_ENVELOPE_INTRO_PEAK = 1.3  # start of timeline (music-only intro)
BG_ENVELOPE_BODY_LEVEL = 0.9  # while voice plays (music + narration)
BG_ENVELOPE_OUTRO_PEAK = 1.3  # end of file after outro ramp (music-only tail)

# Default uniform multiplier applied to all three BG levels (advanced tuning only).
_BG_ENVELOPE_UNITY_SCALE_DEFAULT = 1.0


def _apply_bg_volume_envelope(
    looped_bg_path: Path,
    voice_duration: float,
    run_dir: Path,
    *,
    pad_start: float | None = None,
    pad_end: float | None = None,
    bg_duck_ramp: float | None = None,
    bg_volume_scale: float | None = None,
) -> Path:
    """Apply a deterministic linear BG envelope on looped ambient.

    Timeline (matching final mix semantics):

    * ``t in [0, pad_start)``: BG linear ``BG_ENVELOPE_INTRO_PEAK`` → ``BG_ENVELOPE_BODY_LEVEL``.
    * ``t in [pad_start, pad_start + voice_duration)``: BG flat at ``BG_ENVELOPE_BODY_LEVEL`` (voice runs here too).
    * ``t`` in trailing ``pad_end`` seconds before EOF: BG linear ``BG_ENVELOPE_BODY_LEVEL`` →
      ``BG_ENVELOPE_OUTRO_PEAK`` (voice finishes at start of this region).

    ``bg_volume_scale`` multiplies the whole curve (default 1); ``bg_duck_ramp`` is ignored (API compat).
    """
    _ = bg_duck_ramp

    ps = PAD_START if pad_start is None else float(pad_start)
    ps_tm = max(float(ps), 1e-9)
    pe_raw = PAD_END if pad_end is None else float(pad_end)
    pe = max(float(pe_raw), 1e-9)

    unity = (
        _BG_ENVELOPE_UNITY_SCALE_DEFAULT
        if bg_volume_scale is None
        else float(bg_volume_scale)
    )
    hi = BG_ENVELOPE_INTRO_PEAK * unity
    lo = BG_ENVELOPE_BODY_LEVEL * unity
    oph = BG_ENVELOPE_OUTRO_PEAK * unity
    intro_drop = hi - lo
    outro_rise = oph - lo
    voiceover_dir = run_dir / "voiceover"
    enveloped_path = voiceover_dir / "bg_enveloped.wav"
    v = voice_duration
    flat_end = ps + v
    end_fade_end = flat_end + pe

    # Single expression — VO starts exactly at pad_start on the timeline in the mix stage.
    expr = (
        f"if(lt(t,{ps}),{hi}-t/{ps_tm}*{intro_drop},"
        f"if(lt(t,{flat_end}),{lo},"
        f"if(lt(t,{end_fade_end}),{lo}+(t-{flat_end})/{pe}*{outro_rise},{oph})))"
    )
    # Commas inside volume= must be \, so -af doesn't split filters; commas between filters do not escape.
    expr_escaped = expr.replace(",", "\\,")
    af_chain = (
        "asetpts=PTS-STARTPTS,"
        f"volume={expr_escaped}:eval=frame"
    )
    # eval=frame: time-varying volume; eval=once leaves ``t`` undefined (silent/wrong levels).
    # asetpts: stable timeline/presentation time for ``t`` on some bg sources/decodes.
    _run_ffmpeg(
        [
            "-i",
            str(looped_bg_path),
            "-af",
            af_chain,
            "-c:a",
            "pcm_s16le",
            str(enveloped_path),
        ],
        "apply bg volume envelope",
    )
    return enveloped_path


def _load_audio_metadata_from_app_config(
    base_dir: Path,
    app_name: str,
    out_basename_no_ext: str,
    *,
    story_seed: str | None = None,
) -> dict[str, str]:
    """Load optional audio_artist, audio_title, audio_album from app config (default + app overrides).

    Returns a dict suitable for ffmpeg -metadata (e.g. artist, title, album).
    Defaults: artist=app_name, title=truncated story seed from inputs or out_basename_no_ext, album empty.
    The title is always prefixed with the current Europe/Berlin calendar day as ``DD.MM - `` before embedding.
    """
    merged: dict = {}
    default_path = base_dir / "apps" / "default_config.yaml"
    if default_path.exists():
        try:
            with default_path.open(encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if isinstance(data, dict):
                merged = dict(data)
        except Exception:
            pass
    app_config_path = base_dir / "apps" / app_name / "app_config.yaml"
    if app_config_path.exists():
        try:
            with app_config_path.open(encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if isinstance(data, dict):
                for k, v in data.items():
                    if v is not None:
                        merged[k] = v
        except Exception:
            pass

    def _get(*keys: str, default: str = "") -> str:
        for key in keys:
            if key in merged and merged[key] is not None:
                v = str(merged[key]).strip()
                if v:
                    return v
        return default

    artist = _get("audio_artist", "audio-artist", default=app_name)
    default_title = _default_audio_title_from_seed(story_seed, out_basename_no_ext)
    title = _get("audio_title", "audio-title", default=default_title)
    title = f"{_cet_dd_mm_dot_title_prefix()} - {title}"
    album = _get("audio_album", "audio-album", default="")
    out: dict[str, str] = {"artist": artist, "title": title}
    if album:
        out["album"] = album
    return out


def _mp3_metadata_args(metadata: dict[str, str]) -> list[str]:
    """Build ffmpeg -metadata key=value args from a dict. Only non-empty values."""
    args: list[str] = []
    for key, value in metadata.items():
        if value and isinstance(value, str) and value.strip():
            args.extend(["-metadata", f"{key}={value.strip()}"])
    return args


BG_ENVELOPED_FILENAME = "bg_enveloped.wav"


def finalize_story_audio_mix(
    run_dir: Path,
    base_dir: Path,
    logger: RunLogger,
    *,
    app_name: str | None = None,
    pad_start: float | None = None,
    pad_end: float | None = None,
    voiceover_mix_gain: float | None = None,
) -> Path:
    """Mix existing ``voiceover/voiceover.<ext>`` with ``voiceover/bg_enveloped.wav`` into ``artifacts/story-...``.

    Does not stitch TTS segments, polish, tempo-change the voiceover, loop source music, or rebuild
    the envelope. Use when both files are already correct; ``bg_enveloped.wav`` should match the same
    timeline as in the full audio-prep step (length ≈ ``pad_start + voice_duration + pad_end``).

    Raises:
        AudioPrepStepError: If voiceover or ``bg_enveloped.wav`` is missing, or ffmpeg/ffprobe fails.
    """
    run_dir = run_dir.resolve()
    base_dir = base_dir.resolve()
    if app_name is None:
        app_name = _get_app_name(run_dir)

    voiceover_path, ext = _resolve_existing_voiceover(run_dir)
    enveloped_bg = run_dir / "voiceover" / BG_ENVELOPED_FILENAME
    if not enveloped_bg.is_file():
        raise AudioPrepStepError(
            f"Missing enveloped background: {enveloped_bg}. "
            "Rebuild with the main audio-prep step or scripts/regenerate_bg_tracks.py."
        )

    voice_duration = _get_duration_seconds(voiceover_path)
    logger.info(
        f"Final mix only: voiceover {voice_duration:.2f}s + {BG_ENVELOPED_FILENAME}"
    )

    artifacts_dir = run_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    out_name = _voiceover_artifact_filename(run_dir, app_name, ext)
    out_path = artifacts_dir / out_name
    out_basename_no_ext = out_path.stem

    story_seed: str | None = None
    try:
        from llm_storytell.pipeline.state import StateIOError, load_inputs

        inp = load_inputs(run_dir)
        raw = inp.get("seed")
        if raw is not None:
            story_seed = str(raw)
    except StateIOError:
        pass

    metadata = _load_audio_metadata_from_app_config(
        base_dir, app_name, out_basename_no_ext, story_seed=story_seed
    )
    cover_path = _resolve_album_cover(base_dir, app_name)
    if cover_path is not None:
        logger.info(f"Album cover: {cover_path}")

    _mix_voiceover_and_bg(
        voiceover_path,
        enveloped_bg,
        out_path,
        run_dir,
        logger,
        ext,
        voice_duration,
        metadata=metadata,
        cover_path=cover_path,
        pad_start=pad_start,
        pad_end=pad_end,
        voiceover_mix_gain=voiceover_mix_gain,
    )
    logger.info(f"Final mix complete: {out_path}")
    return out_path


def _mix_voiceover_and_bg(
    voiceover_path: Path,
    bg_path: Path,
    out_path: Path,
    run_dir: Path,
    logger: RunLogger,
    ext: str,
    voice_duration: float,
    *,
    metadata: dict[str, str] | None = None,
    cover_path: Path | None = None,
    pad_start: float | None = None,
    pad_end: float | None = None,
    voiceover_mix_gain: float | None = None,
) -> None:
    """Mix voiceover and background; write to out_path.

    Voiceover is placed from PAD_START to PAD_START+voice_duration on the track
    (3s intro of music only, then voice+music, then PAD_END s of music only).
    Voice track gets a configurable gain (default 1.0 = ``100%``).
    For MP3/M4A, optional metadata (e.g. artist, title, album) is written as ID3/tags.
    When cover_path is set and ext is .mp3 or .m4a, the image is embedded as album cover.
    """
    if ext.lower() == ".wav":
        codec_args = ["-c:a", "pcm_s16le"]
        meta_args: list[str] = []
    else:
        codec_args = ["-c:a", "libmp3lame", "-q:a", "2"]
        meta_args = _mp3_metadata_args(metadata or {})
    ps = PAD_START if pad_start is None else float(pad_start)
    pe = PAD_END if pad_end is None else float(pad_end)
    vgain = 1.0 if voiceover_mix_gain is None else float(voiceover_mix_gain)
    delay_ms = int(ps * 1000)
    # Delay voice by ps; pad end by pe so total = bg length
    # duration=first: match padded voice timeline; normalize=0: do not attenuate summed signals
    # (ffmpeg amix defaults normalize=true, which strongly ducks beds under narration).
    filter_complex = (
        f"[0:a]volume={vgain},adelay={delay_ms}|{delay_ms},apad=pad_dur={pe}[vo];"
        "[vo][1:a]amix=inputs=2:duration=first:normalize=0[aout]"
    )
    embed_cover = (
        cover_path is not None
        and cover_path.is_file()
        and ext.lower() in (".mp3", ".m4a")
    )
    ffmpeg_args: list[str] = [
        "-i",
        str(voiceover_path),
        "-i",
        str(bg_path),
    ]
    if embed_cover:
        ffmpeg_args.extend(["-i", str(cover_path)])
    ffmpeg_args.extend(
        [
            "-filter_complex",
            filter_complex,
            "-map",
            "[aout]",
        ]
    )
    if embed_cover:
        ffmpeg_args.extend(["-map", "2:0", "-c:v", "mjpeg", "-id3v2_version", "3"])
        ffmpeg_args.extend(
            [
                "-metadata:s:v",
                "title=Album cover",
                "-metadata:s:v",
                "comment=Cover (front)",
            ]
        )
    ffmpeg_args.extend(codec_args)
    ffmpeg_args.extend(meta_args)
    ffmpeg_args.append(str(out_path))
    _run_ffmpeg(
        ffmpeg_args,
        "mix voiceover and bg",
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
    bg_music_path: Path | str | None = None,
    voiceover_mix_gain: float | None = None,
    bg_volume_scale: float | None = None,
    pad_start: float | None = None,
    pad_end: float | None = None,
    bg_duck_ramp: float | None = None,
    bg_loop_crossfade: float | None = None,
    voiceover_atempo: float | None = None,
    apply_voiceover_polish: bool = True,
    voiceover_polish_af: str | None = None,
    use_existing_voiceover: bool = False,
) -> None:
    """Stitch TTS segments, polish voiceover, add background music with envelope, mix to final narration.

    Steps:
    1. Stitch segments from run_dir/tts/outputs/ into one voiceover track (unless use_existing_voiceover).
    2. Apply voiceover polish (highpass/lowpass, EQ, dynaudnorm, reverb, de-ess, limiter) unless disabled.
    3. Optionally apply voiceover ``atempo`` when ``voiceover_atempo`` is set.
    4. Measure voiceover duration.
    5. Load bg music: explicit bg_music_path, else apps/<app_name>/assets/bg-music.*, else assets/default-bg-music.wav.
    6. Loop bg with crossfade to voice_duration + pad_start + pad_end.
    7. Apply bg volume envelope (shape scaled by bg_volume_scale when set).
    8. Resolve album cover: apps/<app_name>/assets/album-cover.png if present, else base_dir/assets/album-cover.png; if neither exists, no cover.
    9. Mix: voiceover delayed by pad_start; write to run_dir/artifacts/story-<app4>-<llm_model>-<tts_model>-<tts_voice>-<DD-MM>.<ext>. When cover is present and output is MP3/M4A, embed cover as attached picture.

    Optional tuning (defaults match module constants) is intended for manual iteration via scripts/audio_tweak.py.

    Args:
        run_dir: Run directory (runs/<run_id>/).
        base_dir: Project root (contains runs/, apps/, assets/).
        logger: Run logger.
        app_name: App name for output filename and bg path; if None, read from run_dir/inputs.json.
        bg_music_path: If set, use this file instead of resolving app/default assets.
        voiceover_mix_gain: Linear gain on voiceover in the final mix (default ``1.0`` = nominal TTS loudness).
        bg_volume_scale: Multiplies BG intro/body/outro envelope (default ``1``; see ``BG_ENVELOPE_*``).
        pad_start: Seconds of music-only intro before voice (default ``PAD_START``).
        pad_end: Seconds of music-only outro after voice (default ``PAD_END``).
        bg_duck_ramp: Ignored (reserved for API compat).
        bg_loop_crossfade: Crossfade duration when looping bg (default ``BG_LOOP_CROSSFADE``).
        voiceover_atempo: If set, ffmpeg ``atempo`` applied after polish (0.5–2.0; <1 slows down).
        apply_voiceover_polish: When False, skip the polish ffmpeg pass after stitch.
        voiceover_polish_af: Full ``-af`` chain for polish; only used when polish is enabled.
        use_existing_voiceover: When True, use run_dir/voiceover/voiceover.<ext> and skip stitch (and polish if disabled).

    Raises:
        AudioPrepStepError: On missing inputs, ffmpeg/ffprobe failure, or no bg music found.
    """
    run_dir = run_dir.resolve()
    base_dir = base_dir.resolve()

    if app_name is None:
        app_name = _get_app_name(run_dir)

    ps = PAD_START if pad_start is None else float(pad_start)
    pe = PAD_END if pad_end is None else float(pad_end)

    if use_existing_voiceover:
        voiceover_path, ext = _resolve_existing_voiceover(run_dir)
        logger.info(f"Using existing voiceover: {voiceover_path}")
    else:
        segments, ext = _discover_segments(run_dir)
        logger.info(f"Stitching {len(segments)} segments")
        voiceover_path = _stitch_segments(run_dir, segments, ext, logger)

    if apply_voiceover_polish:
        _apply_voiceover_polish(
            voiceover_path, ext, logger, polish_af=voiceover_polish_af
        )
    else:
        logger.info("Skipping voiceover polish")

    if voiceover_atempo is not None:
        _apply_voiceover_atempo(
            voiceover_path, ext, logger, float(voiceover_atempo)
        )

    voice_duration = _get_duration_seconds(voiceover_path)
    logger.info(f"Voiceover duration: {voice_duration:.2f}s")

    bg_target_length = voice_duration + ps + pe
    if bg_music_path is not None:
        bg_path = Path(bg_music_path).expanduser().resolve()
        if not bg_path.is_file():
            raise AudioPrepStepError(f"Background music file not found: {bg_path}")
    else:
        bg_path = _resolve_bg_music(base_dir, app_name)
    logger.info(f"Background music: {bg_path}")

    looped_bg = _build_looped_bg_with_crossfade(
        bg_path,
        bg_target_length,
        run_dir,
        logger,
        crossfade_seconds=bg_loop_crossfade,
    )
    enveloped_bg = _apply_bg_volume_envelope(
        looped_bg,
        voice_duration,
        run_dir,
        pad_start=pad_start,
        pad_end=pad_end,
        bg_duck_ramp=bg_duck_ramp,
        bg_volume_scale=bg_volume_scale,
    )

    artifacts_dir = run_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    out_name = _voiceover_artifact_filename(run_dir, app_name, ext)
    out_path = artifacts_dir / out_name
    out_basename_no_ext = out_path.stem
    story_seed: str | None = None
    try:
        from llm_storytell.pipeline.state import StateIOError, load_inputs

        inp = load_inputs(run_dir)
        raw = inp.get("seed")
        if raw is not None:
            story_seed = str(raw)
    except StateIOError:
        pass
    metadata = _load_audio_metadata_from_app_config(
        base_dir, app_name, out_basename_no_ext, story_seed=story_seed
    )
    cover_path = _resolve_album_cover(base_dir, app_name)
    if cover_path is not None:
        logger.info(f"Album cover: {cover_path}")

    _mix_voiceover_and_bg(
        voiceover_path,
        enveloped_bg,
        out_path,
        run_dir,
        logger,
        ext,
        voice_duration,
        metadata=metadata,
        cover_path=cover_path,
        pad_start=pad_start,
        pad_end=pad_end,
        voiceover_mix_gain=voiceover_mix_gain,
    )
    logger.info(f"Audio-prep complete: {out_path}")
