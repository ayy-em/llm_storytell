"""Tests for the audio-prep pipeline step (stitching + background music)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from llm_storytell.logging import RunLogger
from llm_storytell.steps.audio_prep import (
    ALBUM_COVER_FILENAME,
    MAX_SEGMENTS,
    AudioPrepStepError,
    VOICEOVER_POLISH_AF,
    _app_prefix_four_chars,
    _bg_envelope_levels,
    _default_audio_title_from_seed,
    _discover_segments,
    _get_app_name,
    _load_audio_metadata_from_app_config,
    _resolve_album_cover,
    _resolve_bg_music,
    _resolve_existing_voiceover,
    _voiceover_artifact_filename,
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


class TestVoiceoverPolishFilter:
    """Regression: broken afade=out:st=0 silences everything after the fade window."""

    def test_polish_chain_has_no_start_aligned_fade_out(self) -> None:
        assert "afade=t=out:st=0" not in VOICEOVER_POLISH_AF


class TestVoiceoverArtifactFilename:
    """Final artifact: story-{app4}-{llm}-{tts_model}-{tts_voice}-{DD-MM}.ext (CET date)."""

    def test_app_prefix_four_chars(self) -> None:
        assert _app_prefix_four_chars("my_app") == "my_a"
        assert _app_prefix_four_chars("grim-narrator") == "grim"
        assert _app_prefix_four_chars("ab") == "ab"

    def test_default_audio_title_from_seed(self) -> None:
        assert _default_audio_title_from_seed("  hello  world  ", "fb") == "hello world"
        long_seed = "x" * 40
        assert len(_default_audio_title_from_seed(long_seed, "fb")) == 30
        assert _default_audio_title_from_seed(None, "fb") == "fb"
        assert _default_audio_title_from_seed("", "fb") == "fb"

    def test_voiceover_artifact_filename_from_inputs_and_state(
        self, tmp_path: Path
    ) -> None:
        run_dir = tmp_path / "run-20260209-120000"
        run_dir.mkdir()
        (run_dir / "inputs.json").write_text(
            json.dumps(
                {
                    "app": "my_app",
                    "run_id": "run-20260209-120000",
                    "model": "gpt-4.1-mini",
                }
            ),
            encoding="utf-8",
        )
        (run_dir / "state.json").write_text(
            json.dumps(
                {
                    "tts_config": {
                        "tts_model": "eleven_multilingual_v2",
                        "tts_voice": "6FiCmD8eY5VyjOdG5Zjk",
                    },
                }
            ),
            encoding="utf-8",
        )
        with patch(
            "llm_storytell.steps.audio_prep._cet_dd_mm_stamp", return_value="09-02"
        ):
            name = _voiceover_artifact_filename(run_dir, "my_app", ".mp3")
        assert (
            name
            == "story-my_a-gpt-4.1-mini-eleven_multilingual_v2-6FiCmD8eY5VyjOdG5Zjk-09-02.mp3"
        )

    def test_voiceover_artifact_filename_fallback_when_missing_inputs_state(
        self, tmp_path: Path
    ) -> None:
        run_dir = tmp_path / "run-001"
        run_dir.mkdir()
        (run_dir / "inputs.json").write_text(
            json.dumps({"app": "example_app", "run_id": "run-001"}), encoding="utf-8"
        )
        with patch(
            "llm_storytell.steps.audio_prep._cet_dd_mm_stamp", return_value="00-00"
        ):
            name = _voiceover_artifact_filename(run_dir, "example_app", ".mp3")
        assert name == "story-exam-unknown-unknown-unknown-00-00.mp3"


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


class TestLoadAudioMetadataFromAppConfig:
    """ID3 defaults: title from truncated seed unless YAML overrides."""

    def test_title_from_seed_when_no_config(self, tmp_path: Path) -> None:
        base = tmp_path / "proj"
        base.mkdir()
        with patch(
            "llm_storytell.steps.audio_prep._cet_dd_mm_dot_title_prefix",
            return_value="15.06",
        ):
            meta = _load_audio_metadata_from_app_config(
                base, "app1", "stem", story_seed="hello world"
            )
        assert meta["title"] == "15.06 - hello world"
        assert meta["artist"] == "app1"

    def test_yaml_audio_title_overrides_seed(self, tmp_path: Path) -> None:
        base = tmp_path / "proj"
        (base / "apps").mkdir(parents=True)
        (base / "apps" / "default_config.yaml").write_text(
            "audio_title: Custom\n",
            encoding="utf-8",
        )
        with patch(
            "llm_storytell.steps.audio_prep._cet_dd_mm_dot_title_prefix",
            return_value="15.06",
        ):
            meta = _load_audio_metadata_from_app_config(
                base, "app1", "stem", story_seed="ignored"
            )
        assert meta["title"] == "15.06 - Custom"


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


class TestResolveExistingVoiceover:
    """Using a pre-stitched voiceover file under voiceover/."""

    def test_finds_voiceover_mp3(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run-1"
        vo = run_dir / "voiceover"
        vo.mkdir(parents=True)
        (vo / "voiceover.mp3").write_bytes(b"x")
        path, ext = _resolve_existing_voiceover(run_dir)
        assert path.name == "voiceover.mp3"
        assert ext == ".mp3"

    def test_missing_dir_raises(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run-1"
        run_dir.mkdir()
        with pytest.raises(AudioPrepStepError, match="Voiceover directory not found"):
            _resolve_existing_voiceover(run_dir)

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run-1"
        run_dir.mkdir()
        (run_dir / "voiceover").mkdir()
        with pytest.raises(AudioPrepStepError, match="No voiceover"):
            _resolve_existing_voiceover(run_dir)


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


class TestResolveAlbumCover:
    """Album cover path resolution: app-specific first, then repo default."""

    def test_returns_none_when_both_missing(self, tmp_path: Path) -> None:
        base = tmp_path / "project"
        base.mkdir()
        assert _resolve_album_cover(base, "my_app") is None

    def test_returns_none_when_assets_dir_exists_but_no_cover(
        self, tmp_path: Path
    ) -> None:
        base = tmp_path / "project"
        base.mkdir()
        (base / "apps" / "my_app" / "assets").mkdir(parents=True)
        assert _resolve_album_cover(base, "my_app") is None

    def test_app_specific_cover_when_present(self, tmp_path: Path) -> None:
        base = tmp_path / "project"
        base.mkdir()
        (base / "apps" / "my_app" / "assets").mkdir(parents=True)
        app_cover = base / "apps" / "my_app" / "assets" / ALBUM_COVER_FILENAME
        app_cover.write_bytes(b"\x89PNG\r\n")
        assert _resolve_album_cover(base, "my_app") == app_cover

    def test_default_cover_when_app_has_none(self, tmp_path: Path) -> None:
        base = tmp_path / "project"
        base.mkdir()
        (base / "assets").mkdir()
        default_cover = base / "assets" / ALBUM_COVER_FILENAME
        default_cover.write_bytes(b"\x89PNG\r\n")
        assert _resolve_album_cover(base, "no_app") == default_cover

    def test_app_cover_overrides_default(self, tmp_path: Path) -> None:
        base = tmp_path / "project"
        base.mkdir()
        (base / "apps" / "my_app" / "assets").mkdir(parents=True)
        (base / "assets").mkdir()
        app_cover = base / "apps" / "my_app" / "assets" / ALBUM_COVER_FILENAME
        app_cover.write_bytes(b"app")
        (base / "assets" / ALBUM_COVER_FILENAME).write_bytes(b"default")
        assert _resolve_album_cover(base, "my_app") == app_cover


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
                    or "story-" in str(last)
                    or "bg_" in str(last)
                ):
                    last.parent.mkdir(parents=True, exist_ok=True)
                    last.write_bytes(b"x")
            return out

        with (
            patch(
                "llm_storytell.steps.audio_prep.subprocess.run",
                side_effect=fake_run,
            ),
            patch(
                "llm_storytell.steps.audio_prep._cet_dd_mm_stamp",
                return_value="00-00",
            ),
        ):
            execute_audio_prep_step(run_dir, base, logger, app_name="example_app")

        ffmpeg_calls = [c for c in calls if c[0] == "ffmpeg"]
        ffprobe_calls = [c for c in calls if c[0] == "ffprobe"]
        assert len(ffprobe_calls) >= 2  # voiceover duration + bg duration
        assert len(ffmpeg_calls) >= 5  # stitch, polish, loop, envelope, mix

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

        # Polish: -af with highpass, alimiter (clean, reverb, de-ess)
        polish = next(
            (
                c
                for c in ffmpeg_calls
                if "-af" in c
                and "highpass" in " ".join(c)
                and "alimiter" in " ".join(c)
            ),
            None,
        )
        assert polish is not None

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
        story = list(artifacts_dir.glob("story-*.mp3"))
        assert len(story) == 1
        assert story[0].name == "story-exam-unknown-unknown-unknown-00-00.mp3"

    def test_mix_ffmpeg_includes_truncated_seed_as_title(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run-meta"
        run_dir.mkdir()
        seed = "S" * 45
        (run_dir / "inputs.json").write_text(
            json.dumps(
                {"app": "example_app", "run_id": "run-001", "model": "m", "seed": seed}
            ),
            encoding="utf-8",
        )
        (run_dir / "state.json").write_text(
            json.dumps({"tts_config": {"tts_model": "tm", "tts_voice": "v"}}),
            encoding="utf-8",
        )
        outputs = run_dir / "tts" / "outputs"
        outputs.mkdir(parents=True)
        (outputs / "segment_01.mp3").write_bytes(b"f")
        base = tmp_path / "base"
        base.mkdir()
        (base / "assets").mkdir()
        (base / "assets" / "default-bg-music.wav").write_bytes(b"x")
        log_path = run_dir / "run.log"
        log_path.touch()
        logger = RunLogger(log_path)

        calls: list[list[str]] = []

        def fake_run(cmd: list[str], *args: object, **kwargs: object) -> MagicMock:
            calls.append(cmd)
            out = MagicMock()
            out.returncode = 0
            out.stderr = ""
            if cmd[0] == "ffprobe":
                out.stdout = "10.0"
            else:
                out.stdout = ""
            if cmd[0] == "ffmpeg" and len(cmd) >= 2:
                last = Path(cmd[-1])
                if (
                    "voiceover" in str(last)
                    or "story-" in str(last)
                    or "bg_" in str(last)
                ):
                    last.parent.mkdir(parents=True, exist_ok=True)
                    last.write_bytes(b"x")
            return out

        with (
            patch(
                "llm_storytell.steps.audio_prep.subprocess.run",
                side_effect=fake_run,
            ),
            patch(
                "llm_storytell.steps.audio_prep._cet_dd_mm_stamp",
                return_value="00-00",
            ),
            patch(
                "llm_storytell.steps.audio_prep._cet_dd_mm_dot_title_prefix",
                return_value="00.00",
            ),
        ):
            execute_audio_prep_step(run_dir, base, logger, app_name="example_app")

        mix = next(
            (c for c in calls if c[0] == "ffmpeg" and "amix" in " ".join(c)), None
        )
        assert mix is not None
        expected_title = f"00.00 - {'S' * 30}"
        assert "-metadata" in mix
        title_meta = next(
            (
                mix[i + 1]
                for i, x in enumerate(mix)
                if x == "-metadata"
                and i + 1 < len(mix)
                and mix[i + 1].startswith("title=")
            ),
            None,
        )
        assert title_meta == f"title={expected_title}"

    def test_mix_includes_album_cover_when_present(self, tmp_path: Path) -> None:
        """When app or default has album-cover.png, mix ffmpeg call embeds it (MP3)."""
        run_dir = _run_dir(tmp_path, ["segment_01.mp3", "segment_02.mp3"])
        base = tmp_path / "base"
        base.mkdir()
        (base / "assets").mkdir()
        (base / "assets" / "default-bg-music.wav").write_bytes(b"x")
        (base / "assets" / ALBUM_COVER_FILENAME).write_bytes(b"\x89PNG\r\n")
        log_path = run_dir / "run.log"
        log_path.touch()
        logger = RunLogger(log_path)

        all_calls: list[list[str]] = []
        probe_returns = ["30.5", "10.0"]

        def fake_run(cmd: list[str], *args: object, **kwargs: object) -> MagicMock:
            all_calls.append(list(cmd))
            out = MagicMock()
            out.returncode = 0
            out.stderr = ""
            if cmd[0] == "ffprobe":
                idx = len([c for c in all_calls if c[0] == "ffprobe"]) - 1
                out.stdout = probe_returns[idx % len(probe_returns)]
            else:
                out.stdout = ""
            if cmd[0] == "ffmpeg":
                Path(cmd[-1]).parent.mkdir(parents=True, exist_ok=True)
                Path(cmd[-1]).write_bytes(b"x")
            return out

        with (
            patch(
                "llm_storytell.steps.audio_prep.subprocess.run",
                side_effect=fake_run,
            ),
            patch(
                "llm_storytell.steps.audio_prep._cet_dd_mm_stamp",
                return_value="00-00",
            ),
        ):
            execute_audio_prep_step(run_dir, base, logger, app_name="example_app")

        mix = next((c for c in all_calls if "amix" in " ".join(c)), None)
        assert mix is not None
        cmd_str = " ".join(mix)
        # Three inputs: voice, bg, cover
        assert mix.count("-i") == 3
        assert ALBUM_COVER_FILENAME in cmd_str
        assert "-map" in cmd_str and "2:0" in mix
        assert "-c:v" in mix and "mjpeg" in cmd_str
        assert "Cover (front)" in cmd_str

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

        with (
            patch(
                "llm_storytell.steps.audio_prep.subprocess.run",
                side_effect=fake_run,
            ),
            patch(
                "llm_storytell.steps.audio_prep._cet_dd_mm_stamp",
                return_value="00-00",
            ),
        ):
            execute_audio_prep_step(run_dir, base, logger, app_name="example_app")

        assert envelope_cmd is not None
        full = " ".join(envelope_cmd)
        # Envelope: 0-3s fade, 3 to 3+voice_duration flat, then 3s fade. For voice_duration=12: 3, 15, 18.
        assert "3" in full and "15" in full and "18" in full
        # BG envelope levels from audio_prep (BG_VOLUME_SCALE and _BG_*); keep in sync with implementation.
        from llm_storytell.steps.audio_prep import _BG_DUCK, _BG_INTRO_START

        assert str(_BG_DUCK) in full
        assert str(_BG_INTRO_START) in full

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

        with (
            patch(
                "llm_storytell.steps.audio_prep.subprocess.run",
                side_effect=fake_run,
            ),
            patch(
                "llm_storytell.steps.audio_prep._cet_dd_mm_stamp",
                return_value="00-00",
            ),
        ):
            execute_audio_prep_step(run_dir, base, logger, app_name="example_app")

        assert (
            run_dir / "artifacts" / "story-exam-unknown-unknown-unknown-00-00.mp3"
        ).exists()
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

        with (
            patch(
                "llm_storytell.steps.audio_prep.subprocess.run",
                side_effect=fake_run,
            ),
            patch(
                "llm_storytell.steps.audio_prep._cet_dd_mm_stamp",
                return_value="00-00",
            ),
        ):
            execute_audio_prep_step(run_dir, base, logger)

        out = run_dir / "artifacts" / "story-from-unknown-unknown-unknown-00-00.mp3"
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


class TestAudioPrepOverrides:
    """Optional tuning parameters for manual iteration (scripts/audio_tweak.py)."""

    def test_voiceover_mix_gain_in_final_mix(self, tmp_path: Path) -> None:
        run_dir = _run_dir(tmp_path, ["segment_01.mp3"])
        base = tmp_path / "base"
        base.mkdir()
        (base / "assets").mkdir()
        bg = base / "assets" / "default-bg-music.wav"
        bg.write_bytes(b"x")
        log_path = run_dir / "run.log"
        log_path.touch()
        logger = RunLogger(log_path)

        mix_cmd: list[str] | None = None

        def fake_run(cmd: list[str], *args: object, **kwargs: object) -> MagicMock:
            nonlocal mix_cmd
            if cmd[0] == "ffmpeg":
                if "-filter_complex" in cmd:
                    joined = " ".join(cmd)
                    if "amix" in joined and "volume=" in joined:
                        mix_cmd = cmd
                Path(cmd[-1]).parent.mkdir(parents=True, exist_ok=True)
                Path(cmd[-1]).write_bytes(b"x")
            out = MagicMock()
            out.returncode = 0
            out.stdout = "12.0" if "ffprobe" in cmd else ""
            out.stderr = ""
            return out

        with (
            patch(
                "llm_storytell.steps.audio_prep.subprocess.run",
                side_effect=fake_run,
            ),
            patch(
                "llm_storytell.steps.audio_prep._cet_dd_mm_stamp",
                return_value="00-00",
            ),
        ):
            execute_audio_prep_step(
                run_dir,
                base,
                logger,
                app_name="example_app",
                voiceover_mix_gain=2.0,
            )

        assert mix_cmd is not None
        assert "volume=2" in " ".join(mix_cmd)

    def test_bg_volume_scale_in_envelope(self, tmp_path: Path) -> None:
        run_dir = _run_dir(tmp_path, ["segment_01.mp3"])
        base = tmp_path / "base"
        base.mkdir()
        (base / "assets").mkdir()
        (base / "assets" / "default-bg-music.wav").write_bytes(b"x")
        log_path = run_dir / "run.log"
        log_path.touch()
        logger = RunLogger(log_path)

        envelope_cmd: list[str] | None = None
        scale = 0.5
        _, _, duck, _, _ = _bg_envelope_levels(scale)

        def fake_run(cmd: list[str], *args: object, **kwargs: object) -> MagicMock:
            nonlocal envelope_cmd
            if cmd[0] == "ffmpeg":
                if "volume=" in " ".join(cmd) and "-af" in cmd:
                    envelope_cmd = cmd
                Path(cmd[-1]).parent.mkdir(parents=True, exist_ok=True)
                Path(cmd[-1]).write_bytes(b"x")
            out = MagicMock()
            out.returncode = 0
            out.stdout = "12.0" if "ffprobe" in cmd else ""
            out.stderr = ""
            return out

        with (
            patch(
                "llm_storytell.steps.audio_prep.subprocess.run",
                side_effect=fake_run,
            ),
            patch(
                "llm_storytell.steps.audio_prep._cet_dd_mm_stamp",
                return_value="00-00",
            ),
        ):
            execute_audio_prep_step(
                run_dir,
                base,
                logger,
                app_name="example_app",
                bg_volume_scale=scale,
            )

        assert envelope_cmd is not None
        assert str(duck) in " ".join(envelope_cmd)

    def test_explicit_bg_music_path(self, tmp_path: Path) -> None:
        run_dir = _run_dir(tmp_path, ["segment_01.mp3"])
        base = tmp_path / "base"
        base.mkdir()
        custom_bg = base / "my_theme.wav"
        custom_bg.write_bytes(b"x")
        log_path = run_dir / "run.log"
        log_path.touch()
        logger = RunLogger(log_path)

        custom_bg_seen = False
        custom_s = str(custom_bg.resolve())

        def fake_run(cmd: list[str], *args: object, **kwargs: object) -> MagicMock:
            nonlocal custom_bg_seen
            if cmd[0] == "ffmpeg" and custom_s in cmd:
                custom_bg_seen = True
            if cmd[0] == "ffmpeg":
                Path(cmd[-1]).parent.mkdir(parents=True, exist_ok=True)
                Path(cmd[-1]).write_bytes(b"x")
            out = MagicMock()
            out.returncode = 0
            out.stdout = "12.0" if "ffprobe" in cmd else ""
            out.stderr = ""
            return out

        with (
            patch(
                "llm_storytell.steps.audio_prep.subprocess.run",
                side_effect=fake_run,
            ),
            patch(
                "llm_storytell.steps.audio_prep._cet_dd_mm_stamp",
                return_value="00-00",
            ),
        ):
            execute_audio_prep_step(
                run_dir,
                base,
                logger,
                app_name="example_app",
                bg_music_path=custom_bg,
            )

        assert custom_bg_seen

    def test_use_existing_voiceover_no_tts_outputs(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run-x"
        run_dir.mkdir()
        (run_dir / "inputs.json").write_text(
            json.dumps({"app": "example_app", "run_id": "run-x"}),
            encoding="utf-8",
        )
        vo = run_dir / "voiceover"
        vo.mkdir(parents=True)
        (vo / "voiceover.mp3").write_bytes(b"x")
        base = tmp_path / "base"
        base.mkdir()
        (base / "assets").mkdir()
        (base / "assets" / "default-bg-music.wav").write_bytes(b"x")
        log_path = run_dir / "run.log"
        log_path.touch()
        logger = RunLogger(log_path)

        def fake_run(cmd: list[str], *args: object, **kwargs: object) -> MagicMock:
            if cmd[0] == "ffmpeg":
                Path(cmd[-1]).parent.mkdir(parents=True, exist_ok=True)
                Path(cmd[-1]).write_bytes(b"x")
            out = MagicMock()
            out.returncode = 0
            out.stdout = "12.0" if "ffprobe" in cmd else ""
            out.stderr = ""
            return out

        with (
            patch(
                "llm_storytell.steps.audio_prep.subprocess.run",
                side_effect=fake_run,
            ),
            patch(
                "llm_storytell.steps.audio_prep._cet_dd_mm_stamp",
                return_value="00-00",
            ),
        ):
            execute_audio_prep_step(
                run_dir,
                base,
                logger,
                use_existing_voiceover=True,
                apply_voiceover_polish=False,
            )

        assert (
            run_dir / "artifacts" / "story-exam-unknown-unknown-unknown-00-00.mp3"
        ).exists()
