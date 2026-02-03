"""Tests for the audio-prep pipeline step (stitching + background music)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from llm_storytell.logging import RunLogger
from llm_storytell.steps.audio_prep import (
    MAX_SEGMENTS,
    AudioPrepStepError,
    _discover_segments,
    _get_app_name,
    _resolve_bg_music,
    execute_audio_prep_step,
)


def _run_dir(
    tmp_path: Path, segments: list[str], app_name: str = "example_app"
) -> Path:
    """Create a minimal run_dir with tts/outputs and inputs.json."""
    run_dir = tmp_path / "run-001"
    run_dir.mkdir()
    (run_dir / "inputs.json").write_text(
        json.dumps({"app": app_name, "run_id": "run-001"}),
        encoding="utf-8",
    )
    outputs = run_dir / "tts" / "outputs"
    outputs.mkdir(parents=True)
    for name in segments:
        (outputs / name).write_bytes(b"fake_audio")
    return run_dir


class TestGetAppName:
    """Reading app name from inputs.json."""

    def test_gets_app_from_inputs(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "inputs.json").write_text(
            json.dumps({"app": "my_app", "seed": "x"}),
            encoding="utf-8",
        )
        assert _get_app_name(run_dir) == "my_app"

    def test_missing_inputs_raises(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        with pytest.raises(AudioPrepStepError, match="inputs.json not found"):
            _get_app_name(run_dir)

    def test_missing_app_key_raises(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "inputs.json").write_text(
            json.dumps({"seed": "x"}),
            encoding="utf-8",
        )
        with pytest.raises(AudioPrepStepError, match="missing 'app'"):
            _get_app_name(run_dir)


class TestDiscoverSegments:
    """Segment discovery from tts/outputs."""

    def test_no_outputs_dir_raises(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        with pytest.raises(AudioPrepStepError, match="TTS outputs directory not found"):
            _discover_segments(run_dir)

    def test_no_segment_01_raises(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "tts" / "outputs").mkdir(parents=True)
        with pytest.raises(AudioPrepStepError, match="No segment_01"):
            _discover_segments(run_dir)

    def test_finds_ordered_mp3(self, tmp_path: Path) -> None:
        run_dir = _run_dir(
            tmp_path,
            ["segment_01.mp3", "segment_02.mp3", "segment_03.mp3"],
        )
        segments, ext = _discover_segments(run_dir)
        assert len(segments) == 3
        assert ext == ".mp3"
        assert segments[0].name == "segment_01.mp3"
        assert segments[1].name == "segment_02.mp3"
        assert segments[2].name == "segment_03.mp3"

    def test_finds_ordered_wav(self, tmp_path: Path) -> None:
        run_dir = _run_dir(tmp_path, ["segment_01.wav", "segment_02.wav"])
        segments, ext = _discover_segments(run_dir)
        assert len(segments) == 2
        assert ext == ".wav"

    def test_stops_at_first_missing(self, tmp_path: Path) -> None:
        run_dir = _run_dir(
            tmp_path,
            ["segment_01.mp3", "segment_02.mp3"],
        )
        # segment_03 does not exist
        segments, ext = _discover_segments(run_dir)
        assert len(segments) == 2
        assert ext == ".mp3"

    def test_exactly_max_segments_allowed(self, tmp_path: Path) -> None:
        names = [f"segment_{i:02d}.mp3" for i in range(1, MAX_SEGMENTS + 1)]
        run_dir = _run_dir(tmp_path, names)
        segments, ext = _discover_segments(run_dir)
        assert len(segments) == MAX_SEGMENTS
        assert ext == ".mp3"


class TestResolveBgMusic:
    """Background music path resolution."""

    def test_app_assets_bg_music_any_ext(self, tmp_path: Path) -> None:
        base = tmp_path / "project"
        base.mkdir()
        (base / "apps" / "my_app" / "assets").mkdir(parents=True)
        bg = base / "apps" / "my_app" / "assets" / "bg-music.mp3"
        bg.write_bytes(b"")
        assert _resolve_bg_music(base, "my_app") == bg

    def test_app_assets_prefers_first_sorted(self, tmp_path: Path) -> None:
        base = tmp_path / "project"
        base.mkdir()
        (base / "apps" / "my_app" / "assets").mkdir(parents=True)
        (base / "apps" / "my_app" / "assets" / "bg-music.wav").write_bytes(b"")
        (base / "apps" / "my_app" / "assets" / "bg-music.mp3").write_bytes(b"")
        resolved = _resolve_bg_music(base, "my_app")
        # Glob bg-music.* returns both; sorted order is .mp3 before .wav
        assert resolved.suffix == ".mp3"

    def test_default_fallback(self, tmp_path: Path) -> None:
        base = tmp_path / "project"
        base.mkdir()
        (base / "assets").mkdir()
        default = base / "assets" / "default-bg-music.wav"
        default.write_bytes(b"")
        assert _resolve_bg_music(base, "no_app") == default

    def test_app_overrides_default(self, tmp_path: Path) -> None:
        base = tmp_path / "project"
        base.mkdir()
        (base / "apps" / "my_app" / "assets").mkdir(parents=True)
        (base / "apps" / "my_app" / "assets" / "bg-music.wav").write_bytes(b"")
        (base / "assets").mkdir()
        (base / "assets" / "default-bg-music.wav").write_bytes(b"")
        resolved = _resolve_bg_music(base, "my_app")
        assert "my_app" in str(resolved)
        assert resolved.name == "bg-music.wav"

    def test_missing_raises(self, tmp_path: Path) -> None:
        base = tmp_path / "project"
        base.mkdir()
        with pytest.raises(AudioPrepStepError, match="No background music found"):
            _resolve_bg_music(base, "no_app")


class TestExecuteAudioPrepStep:
    """Full step execution with mocked subprocess."""

    def test_stitch_and_mix_commands(self, tmp_path: Path) -> None:
        run_dir = _run_dir(tmp_path, ["segment_01.mp3", "segment_02.mp3"])
        base = tmp_path / "base"
        base.mkdir()
        (base / "assets").mkdir()
        (base / "assets" / "default-bg-music.wav").write_bytes(b"x")
        log_path = run_dir / "run.log"
        log_path.touch()
        logger = RunLogger(log_path)

        calls: list[list[str]] = []
        probe_returns = ["30.5", "10.0"]  # voice duration, bg duration

        def fake_run(cmd: list[str], *args: object, **kwargs: object) -> MagicMock:
            calls.append(cmd)
            out = MagicMock()
            out.returncode = 0
            out.stderr = ""
            if cmd[0] == "ffprobe":
                idx = len([c for c in calls if c[0] == "ffprobe"]) - 1
                out.stdout = probe_returns[idx % len(probe_returns)]
            else:
                out.stdout = ""
            # Create output files so step can continue and final artifact exists
            if cmd[0] == "ffmpeg" and len(cmd) >= 2:
                last = Path(cmd[-1])
                if (
                    "voiceover" in str(last)
                    or "narration-" in str(last)
                    or "bg_" in str(last)
                ):
                    last.parent.mkdir(parents=True, exist_ok=True)
                    last.write_bytes(b"x")
            return out

        with patch(
            "llm_storytell.steps.audio_prep.subprocess.run", side_effect=fake_run
        ):
            execute_audio_prep_step(run_dir, base, logger, app_name="example_app")

        ffmpeg_calls = [c for c in calls if c[0] == "ffmpeg"]
        ffprobe_calls = [c for c in calls if c[0] == "ffprobe"]
        assert len(ffprobe_calls) >= 2  # voiceover duration + bg duration
        assert len(ffmpeg_calls) >= 4  # stitch, loop, envelope, mix

        # Concat/stitch: -f concat -safe 0 -i ... -c copy
        stitch = next(
            (
                c
                for c in ffmpeg_calls
                if "concat" in " ".join(c) and "-c" in " ".join(c)
            ),
            None,
        )
        assert stitch is not None
        concat_idx = stitch.index("-f")
        assert stitch[concat_idx + 1] == "concat"
        assert "copy" in stitch

        # Mix: amix=inputs=2:duration=first
        mix = next(
            (c for c in ffmpeg_calls if "amix" in " ".join(c)),
            None,
        )
        assert mix is not None
        assert "duration=first" in " ".join(mix)

        # Output paths
        voiceover_dir = run_dir / "voiceover"
        assert voiceover_dir.is_dir()
        artifacts_dir = run_dir / "artifacts"
        narration = list(artifacts_dir.glob("narration-*.mp3"))
        assert len(narration) == 1
        assert narration[0].name == "narration-example_app.mp3"

    def test_volume_envelope_uses_voice_duration(self, tmp_path: Path) -> None:
        run_dir = _run_dir(tmp_path, ["segment_01.mp3"])
        base = tmp_path / "base"
        base.mkdir()
        (base / "assets").mkdir()
        (base / "assets" / "default-bg-music.wav").write_bytes(b"x")
        log_path = run_dir / "run.log"
        log_path.touch()
        logger = RunLogger(log_path)

        envelope_cmd: list[str] | None = None

        def fake_run(cmd: list[str], *args: object, **kwargs: object) -> MagicMock:
            nonlocal envelope_cmd
            if cmd[0] == "ffmpeg":
                # Envelope step uses -af volume=...; mix step uses -filter_complex (also has volume=1.5)
                if "volume=" in " ".join(cmd) and "-af" in cmd:
                    envelope_cmd = cmd
                Path(cmd[-1]).parent.mkdir(parents=True, exist_ok=True)
                Path(cmd[-1]).write_bytes(b"x")
            out = MagicMock()
            out.returncode = 0
            out.stdout = "12.0" if "ffprobe" in cmd else ""
            out.stderr = ""
            return out

        with patch(
            "llm_storytell.steps.audio_prep.subprocess.run", side_effect=fake_run
        ):
            execute_audio_prep_step(run_dir, base, logger, app_name="example_app")

        assert envelope_cmd is not None
        full = " ".join(envelope_cmd)
        # Envelope: 0-3s fade, 3 to 3+voice_duration flat, then 3s fade. For voice_duration=12: 3, 15, 18.
        assert "3" in full and "15" in full and "18" in full
        assert "0.75" in full
        assert "0.1" in full or "0.10" in full

    def test_loop_target_duration_voice_plus_six(self, tmp_path: Path) -> None:
        """Step runs and produces narration artifact when voice duration is 10s (loop target 16s)."""
        run_dir = _run_dir(tmp_path, ["segment_01.mp3"])
        base = tmp_path / "base"
        base.mkdir()
        (base / "assets").mkdir()
        (base / "assets" / "default-bg-music.wav").write_bytes(b"x")
        log_path = run_dir / "run.log"
        log_path.touch()
        logger = RunLogger(log_path)

        ffprobe_returns = ["10.0", "5.0"]  # voice duration, then bg duration
        probe_idx = [0]

        def fake_run(cmd: list[str], *args: object, **kwargs: object) -> MagicMock:
            out = MagicMock()
            out.returncode = 0
            out.stderr = ""
            if cmd[0] == "ffprobe":
                out.stdout = ffprobe_returns[probe_idx[0] % len(ffprobe_returns)]
                probe_idx[0] += 1
            else:
                out.stdout = ""
            if cmd[0] == "ffmpeg":
                Path(cmd[-1]).parent.mkdir(parents=True, exist_ok=True)
                Path(cmd[-1]).write_bytes(b"x")
            return out

        with patch(
            "llm_storytell.steps.audio_prep.subprocess.run", side_effect=fake_run
        ):
            execute_audio_prep_step(run_dir, base, logger, app_name="example_app")

        assert (run_dir / "artifacts" / "narration-example_app.mp3").exists()
        assert (run_dir / "voiceover" / "voiceover.mp3").exists()

    def test_app_name_from_inputs_when_not_passed(self, tmp_path: Path) -> None:
        run_dir = _run_dir(tmp_path, ["segment_01.mp3"], app_name="from_inputs")
        base = tmp_path / "base"
        base.mkdir()
        (base / "assets").mkdir()
        (base / "assets" / "default-bg-music.wav").write_bytes(b"x")
        log_path = run_dir / "run.log"
        log_path.touch()
        logger = RunLogger(log_path)

        def fake_run(cmd: list[str], *args: object, **kwargs: object) -> MagicMock:
            out = MagicMock()
            out.returncode = 0
            out.stdout = "5.0" if "ffprobe" in cmd else ""
            out.stderr = ""
            if cmd[0] == "ffmpeg":
                Path(cmd[-1]).parent.mkdir(parents=True, exist_ok=True)
                Path(cmd[-1]).write_bytes(b"x")
            return out

        with patch(
            "llm_storytell.steps.audio_prep.subprocess.run", side_effect=fake_run
        ):
            execute_audio_prep_step(run_dir, base, logger)

        out = run_dir / "artifacts" / "narration-from_inputs.mp3"
        assert out.exists()

    def test_ffprobe_failure_raises(self, tmp_path: Path) -> None:
        run_dir = _run_dir(tmp_path, ["segment_01.mp3"])
        base = tmp_path / "base"
        base.mkdir()
        (base / "assets").mkdir()
        (base / "assets" / "default-bg-music.wav").write_bytes(b"x")
        log_path = run_dir / "run.log"
        log_path.touch()
        logger = RunLogger(log_path)

        call_count = [0]

        def fail_ffprobe(cmd: list[str], *args: object, **kwargs: object) -> MagicMock:
            out = MagicMock()
            if cmd[0] == "ffmpeg":
                Path(cmd[-1]).parent.mkdir(parents=True, exist_ok=True)
                Path(cmd[-1]).write_bytes(b"x")
                out.returncode = 0
                out.stdout = ""
                out.stderr = ""
                return out
            # First ffprobe (voiceover duration) succeeds; second (bg) fails
            call_count[0] += 1
            if call_count[0] >= 2:
                out.returncode = 1
                out.stderr = "Invalid data"
                out.stdout = ""
                return out
            out.returncode = 0
            out.stdout = "10.0"
            out.stderr = ""
            return out

        with patch(
            "llm_storytell.steps.audio_prep.subprocess.run", side_effect=fail_ffprobe
        ):
            with pytest.raises(AudioPrepStepError, match="ffprobe exited 1"):
                execute_audio_prep_step(run_dir, base, logger, app_name="example_app")

    def test_ffmpeg_failure_raises(self, tmp_path: Path) -> None:
        run_dir = _run_dir(tmp_path, ["segment_01.mp3"])
        base = tmp_path / "base"
        base.mkdir()
        (base / "assets").mkdir()
        (base / "assets" / "default-bg-music.wav").write_bytes(b"x")
        log_path = run_dir / "run.log"
        log_path.touch()
        logger = RunLogger(log_path)

        call_count = [0]

        def fail_second_ffmpeg(
            cmd: list[str], *args: object, **kwargs: object
        ) -> MagicMock:
            out = MagicMock()
            out.stdout = "8.0" if "ffprobe" in cmd else ""
            out.stderr = ""
            if cmd[0] == "ffmpeg":
                Path(cmd[-1]).parent.mkdir(parents=True, exist_ok=True)
                Path(cmd[-1]).write_bytes(b"x")
                call_count[0] += 1
                if call_count[0] >= 2:
                    out.returncode = 1
                    out.stderr = "ffmpeg error"
                    return out
            out.returncode = 0
            return out

        with patch(
            "llm_storytell.steps.audio_prep.subprocess.run",
            side_effect=fail_second_ffmpeg,
        ):
            with pytest.raises(AudioPrepStepError, match="ffmpeg exited 1"):
                execute_audio_prep_step(run_dir, base, logger, app_name="example_app")
