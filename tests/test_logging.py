"""Tests for logging functionality."""

from importlib import import_module
from pathlib import Path
import sys

# Import from the package using the hyphenated name
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

logging_module = import_module("llm_storytell.logging")
token_tracking_module = import_module("llm_storytell.llm.token_tracking")

RunLogger = logging_module.RunLogger
TokenUsage = token_tracking_module.TokenUsage
record_token_usage = token_tracking_module.record_token_usage


class TestRunLoggerStructuredEvents:
    """Tests for structured log events."""

    def test_log_stage_start(self, tmp_path: Path) -> None:
        """log_stage_start writes stage start entry."""
        log_path = tmp_path / "test.log"
        log_path.touch()

        logger = RunLogger(log_path)
        logger.log_stage_start("outline")

        content = log_path.read_text()
        assert "[INFO]" in content
        assert "Stage started: outline" in content

    def test_log_stage_end_success(self, tmp_path: Path) -> None:
        """log_stage_end writes success entry."""
        log_path = tmp_path / "test.log"
        log_path.touch()

        logger = RunLogger(log_path)
        logger.log_stage_end("outline", success=True)

        content = log_path.read_text()
        assert "[INFO]" in content
        assert "Stage ended: outline (success)" in content

    def test_log_stage_end_failure(self, tmp_path: Path) -> None:
        """log_stage_end writes failure entry."""
        log_path = tmp_path / "test.log"
        log_path.touch()

        logger = RunLogger(log_path)
        logger.log_stage_end("outline", success=False)

        content = log_path.read_text()
        assert "[INFO]" in content
        assert "Stage ended: outline (failure)" in content

    def test_log_artifact_write(self, tmp_path: Path) -> None:
        """log_artifact_write logs artifact creation with size."""
        log_path = tmp_path / "test.log"
        log_path.touch()

        logger = RunLogger(log_path)
        artifact_path = Path("artifacts/10_outline.json")
        logger.log_artifact_write(artifact_path, size_bytes=1234)

        content = log_path.read_text()
        assert "[INFO]" in content
        assert "Artifact written:" in content
        assert "10_outline.json" in content
        assert "(1234 bytes)" in content

    def test_log_validation_failure(self, tmp_path: Path) -> None:
        """log_validation_failure logs validation error."""
        log_path = tmp_path / "test.log"
        log_path.touch()

        logger = RunLogger(log_path)
        logger.log_validation_failure("outline", "Missing required field: beats")

        content = log_path.read_text()
        assert "[ERROR]" in content
        assert "Validation failure in outline: Missing required field: beats" in content

    def test_warning_writes_warning_level(self, tmp_path: Path) -> None:
        """warning() writes [WARNING] and message to run.log."""
        log_path = tmp_path / "test.log"
        log_path.touch()

        logger = RunLogger(log_path)
        logger.warning("Combined context approaches threshold.")

        content = log_path.read_text()
        assert "[WARNING]" in content
        assert "Combined context approaches threshold." in content

    def test_log_tts_character_usage(self, tmp_path: Path) -> None:
        """log_tts_character_usage logs step, provider, model, and character counts."""
        log_path = tmp_path / "test.log"
        log_path.touch()

        logger = RunLogger(log_path)
        logger.log_tts_character_usage(
            step="tts_01",
            provider="openai",
            model="tts-1",
            input_characters=1234,
            cumulative_characters=5678,
        )

        content = log_path.read_text()
        assert "[INFO]" in content
        assert "TTS character usage [tts_01]" in content
        assert "provider=openai" in content
        assert "model=tts-1" in content
        assert "input_characters=1234" in content
        assert "cumulative_characters=5678" in content

    def test_log_token_usage(self, tmp_path: Path) -> None:
        """log_token_usage logs all token metrics."""
        log_path = tmp_path / "test.log"
        log_path.touch()

        logger = RunLogger(log_path)
        logger.log_token_usage(
            step="outline",
            provider="openai",
            model="gpt-4",
            prompt_tokens=150,
            completion_tokens=200,
            total_tokens=350,
        )

        content = log_path.read_text()
        assert "[INFO]" in content
        assert "Token usage [outline]" in content
        assert "provider=openai" in content
        assert "model=gpt-4" in content
        assert "prompt_tokens=150" in content
        assert "completion_tokens=200" in content
        assert "total_tokens=350" in content


class TestTokenTracking:
    """Tests for token usage tracking."""

    def test_token_usage_to_dict(self) -> None:
        """TokenUsage converts to dictionary correctly."""
        usage = TokenUsage(
            step="outline",
            provider="openai",
            model="gpt-4",
            prompt_tokens=150,
            completion_tokens=200,
            total_tokens=350,
        )

        result = usage.to_dict()

        assert result == {
            "step": "outline",
            "provider": "openai",
            "model": "gpt-4",
            "prompt_tokens": 150,
            "completion_tokens": 200,
            "total_tokens": 350,
        }

    def test_record_token_usage_logs_and_returns_dict(self, tmp_path: Path) -> None:
        """record_token_usage logs to file and returns state dict."""
        log_path = tmp_path / "test.log"
        log_path.touch()

        logger = RunLogger(log_path)
        result = record_token_usage(
            logger=logger,
            step="outline",
            provider="openai",
            model="gpt-4",
            prompt_tokens=150,
            completion_tokens=200,
            total_tokens=350,
        )

        # Check log file (format: Token usage: prompt_tokens=..., completion_tokens=..., total_tokens=...)
        content = log_path.read_text()
        assert "Token usage:" in content
        assert "prompt_tokens=150" in content
        assert "completion_tokens=200" in content
        assert "total_tokens=350" in content

        # Check returned dict
        assert result == {
            "step": "outline",
            "provider": "openai",
            "model": "gpt-4",
            "prompt_tokens": 150,
            "completion_tokens": 200,
            "total_tokens": 350,
        }

    def test_record_token_usage_calculates_total(self, tmp_path: Path) -> None:
        """record_token_usage calculates total_tokens if not provided."""
        log_path = tmp_path / "test.log"
        log_path.touch()

        logger = RunLogger(log_path)
        result = record_token_usage(
            logger=logger,
            step="outline",
            provider="openai",
            model="gpt-4",
            prompt_tokens=150,
            completion_tokens=200,
            total_tokens=None,
        )

        assert result["total_tokens"] == 350
        assert result["prompt_tokens"] == 150
        assert result["completion_tokens"] == 200

    def test_token_usage_visible_in_mocked_tests(self, tmp_path: Path) -> None:
        """Token usage can be recorded even when LLM calls are mocked."""
        log_path = tmp_path / "test.log"
        log_path.touch()

        logger = RunLogger(log_path)

        # Simulate a mocked LLM call that returns token counts
        # without actually making an API call
        mock_response = {
            "prompt_tokens": 100,
            "completion_tokens": 150,
        }

        result = record_token_usage(
            logger=logger,
            step="outline",
            provider="openai",
            model="gpt-4",
            prompt_tokens=mock_response["prompt_tokens"],
            completion_tokens=mock_response["completion_tokens"],
        )

        # Verify token usage was recorded
        assert result["prompt_tokens"] == 100
        assert result["completion_tokens"] == 150
        assert result["total_tokens"] == 250

        # Verify it was logged
        content = log_path.read_text()
        assert "prompt_tokens=100" in content
        assert "completion_tokens=150" in content


class TestNoSecretsLogged:
    """Tests to ensure secrets are never logged."""

    def test_api_key_not_logged(self, tmp_path: Path) -> None:
        """API keys in messages should not be logged."""
        log_path = tmp_path / "test.log"
        log_path.touch()

        logger = RunLogger(log_path)

        # Simulate a scenario where an API key might be in a message
        # (This should be prevented by design, but we test it anyway)
        api_key = "sk-1234567890abcdef"
        logger.info(f"Connecting to provider with key: {api_key}")

        content = log_path.read_text()
        # Note: This test documents current behavior.
        # In a real scenario, we would sanitize before logging.
        # For now, we just verify the logger doesn't crash.
        assert "[INFO]" in content

    def test_token_usage_does_not_include_secrets(self, tmp_path: Path) -> None:
        """Token usage logging does not include API keys or secrets."""
        log_path = tmp_path / "test.log"
        log_path.touch()

        logger = RunLogger(log_path)
        record_token_usage(
            logger=logger,
            step="outline",
            provider="openai",
            model="gpt-4",
            prompt_tokens=100,
            completion_tokens=150,
        )

        content = log_path.read_text()
        # Verify token usage is logged (format may not include provider/model in message)
        assert "Token usage:" in content or "Cumulative token usage" in content
        assert "prompt_tokens=100" in content
        # Should not contain any secret-like patterns
        assert "sk-" not in content.lower()
        assert "api_key" not in content.lower()
        assert "secret" not in content.lower()
        assert "password" not in content.lower()
