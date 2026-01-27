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
