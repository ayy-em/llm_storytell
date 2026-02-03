"""Run-scoped logging for the pipeline.

Provides a simple logger that writes timestamped entries to run.log.
"""

from datetime import datetime, timezone
from pathlib import Path


class RunLogger:
    """Logger that writes to a run's log file.

    All log entries are timestamped in ISO 8601 format (UTC).
    """

    def __init__(self, log_path: Path) -> None:
        """Initialize the logger.

        Args:
            log_path: Path to the log file (typically runs/<run_id>/run.log).
        """
        self._log_path = log_path

    @property
    def log_path(self) -> Path:
        """Return the path to the log file."""
        return self._log_path

    def _timestamp(self) -> str:
        """Return current UTC timestamp in ISO 8601 format."""
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _write(self, level: str, message: str) -> None:
        """Write a log entry to the log file.

        Args:
            level: Log level (INFO, ERROR, etc.).
            message: The message to log.
        """
        timestamp = self._timestamp()
        entry = f"[{timestamp}] [{level}] {message}\n"
        with self._log_path.open("a", encoding="utf-8") as f:
            f.write(entry)

    def info(self, message: str) -> None:
        """Log an INFO level message.

        Args:
            message: The message to log.
        """
        self._write("INFO", message)

    def error(self, message: str) -> None:
        """Log an ERROR level message.

        Args:
            message: The message to log.
        """
        self._write("ERROR", message)

    def warning(self, message: str) -> None:
        """Log a WARNING level message.

        Args:
            message: The message to log.
        """
        self._write("WARNING", message)

    def log_run_init(
        self,
        app_name: str,
        seed: str,
        context_dir: Path,
        prompts_dir: Path,
    ) -> None:
        """Log run initialization details.

        Args:
            app_name: Name of the app being run.
            seed: The story seed/description.
            context_dir: Path to the app's context directory.
            prompts_dir: Path to the app's prompts directory.
        """
        self.info(f"Run initialized for app: {app_name}")
        self.info(f"Seed: {seed}")
        self.info(f"Context directory: {context_dir}")
        self.info(f"Prompts directory: {prompts_dir}")

    def log_stage_start(self, stage_name: str) -> None:
        """Log the start of a pipeline stage.

        Args:
            stage_name: Name of the pipeline stage (e.g., "outline", "section_01").
        """
        self.info(f"Stage started: {stage_name}")

    def log_stage_end(self, stage_name: str, success: bool) -> None:
        """Log the end of a pipeline stage.

        Args:
            stage_name: Name of the pipeline stage.
            success: Whether the stage completed successfully.
        """
        status = "success" if success else "failure"
        self.info(f"Stage ended: {stage_name} ({status})")

    def log_artifact_write(self, file_path: Path, size_bytes: int) -> None:
        """Log the creation of an artifact file.

        Args:
            file_path: Path to the artifact file (relative to run directory).
            size_bytes: Size of the file in bytes.
        """
        self.info(f"Artifact written: {file_path} ({size_bytes} bytes)")

    def log_validation_failure(self, step: str, error: str) -> None:
        """Log a validation failure.

        Args:
            step: Name of the step that failed validation.
            error: Description of the validation error.
        """
        self.error(f"Validation failure in {step}: {error}")

    def log_token_usage(
        self,
        step: str,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
    ) -> None:
        """Log token usage for an LLM call.

        Args:
            step: Name of the pipeline step that made the call.
            provider: LLM provider name (e.g., "openai").
            model: Model name (e.g., "gpt-4").
            prompt_tokens: Number of prompt tokens used.
            completion_tokens: Number of completion tokens used.
            total_tokens: Total tokens used.
        """
        self.info(
            f"Token usage [{step}]: provider={provider}, model={model}, "
            f"prompt_tokens={prompt_tokens}, completion_tokens={completion_tokens}, "
            f"total_tokens={total_tokens}"
        )

    def log_tts_character_usage(
        self,
        step: str,
        provider: str,
        model: str,
        input_characters: int,
        cumulative_characters: int,
    ) -> None:
        """Log TTS character usage for a single call.

        Args:
            step: Name of the TTS step (e.g. tts_01).
            provider: TTS provider name (e.g. openai).
            model: TTS model name.
            input_characters: Character count for this call.
            cumulative_characters: Running total of TTS characters so far.
        """
        self.info(
            f"TTS character usage [{step}]: provider={provider}, model={model}, "
            f"input_characters={input_characters}, cumulative_characters={cumulative_characters}"
        )

    def log_tts_cumulative(
        self,
        response_prompt_tokens: int,
        response_completion_tokens: int,
        tts_prompt_tokens: int,
        total_text_tokens: int,
        total_tts_tokens: int,
        total_tokens: int,
    ) -> None:
        """Log cumulative token usage after TTS step (text + TTS breakdown).

        Args:
            response_prompt_tokens: Sum of prompt tokens from text/LLM steps.
            response_completion_tokens: Sum of completion tokens from text/LLM steps.
            tts_prompt_tokens: Sum of TTS input/prompt tokens.
            total_text_tokens: Total tokens from text pipeline steps.
            total_tts_tokens: Total tokens from TTS step.
            total_tokens: Combined total (text + TTS).
        """
        self.info(
            "Cumulative token usage: "
            f"response_prompt_tokens={response_prompt_tokens}, "
            f"response_completion_tokens={response_completion_tokens}, "
            f"tts_prompt_tokens={tts_prompt_tokens}, "
            f"total_text_tokens={total_text_tokens}, "
            f"total_tts_tokens={total_tts_tokens}, "
            f"total_tokens={total_tokens}"
        )

    def log_context_selection(
        self,
        always_loaded: list[str],
        selected_location: str | None,
        selected_characters: list[str],
        world_files: list[str] | None = None,
    ) -> None:
        """Log context file selections for a run.

        Args:
            always_loaded: List of relative paths to always-loaded files.
            selected_location: Relative path to selected location file, or None.
            selected_characters: List of relative paths to selected character files.
            world_files: List of relative paths to world/*.md files folded into lore.
        """
        self.info("Context selection:")
        self.info(f"  Always loaded: {', '.join(sorted(always_loaded))}")
        if selected_location:
            self.info(f"  Selected location: {selected_location}")
        else:
            self.info("  Selected location: (none)")
        if selected_characters:
            self.info(
                f"  Selected characters: {', '.join(sorted(selected_characters))}"
            )
        else:
            self.info("  Selected characters: (none)")
        if world_files:
            self.info(
                f"  World files (folded into lore): {', '.join(sorted(world_files))}"
            )
        else:
            self.info("  World files: (none)")
