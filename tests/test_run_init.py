"""Tests for run initialization and state bootstrap."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

# Import from the package using the hyphenated name
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from importlib import import_module

run_dir_module = import_module("llm_storytell.run_dir")
logging_module = import_module("llm_storytell.logging")

initialize_run = run_dir_module.initialize_run
generate_run_id = run_dir_module.generate_run_id
get_run_logger = run_dir_module.get_run_logger
RunInitializationError = run_dir_module.RunInitializationError
RunLogger = logging_module.RunLogger


@pytest.fixture
def temp_project(tmp_path: Path) -> Path:
    """Create a temporary project structure."""
    # Create runs directory
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()

    # Create context directory for test app
    context_dir = tmp_path / "context" / "test-app"
    context_dir.mkdir(parents=True)

    # Create prompts directory for test app
    prompts_dir = tmp_path / "prompts" / "apps" / "test-app"
    prompts_dir.mkdir(parents=True)

    return tmp_path


class TestGenerateRunId:
    """Tests for run ID generation."""

    def test_format(self) -> None:
        """Run ID follows expected format."""
        run_id = generate_run_id()
        assert run_id.startswith("run-")
        # Format: run-YYYYMMDD-HHMMSS
        parts = run_id.split("-")
        assert len(parts) == 3
        assert len(parts[1]) == 8  # YYYYMMDD
        assert len(parts[2]) == 6  # HHMMSS

    def test_contains_date_and_time_components(self) -> None:
        """Run ID contains valid date and time components."""
        run_id = generate_run_id()
        # Format: run-YYYYMMDD-HHMMSS
        parts = run_id.split("-")
        date_part = parts[1]
        time_part = parts[2]

        # Validate date part (YYYYMMDD)
        year = int(date_part[:4])
        month = int(date_part[4:6])
        day = int(date_part[6:8])
        assert 2020 <= year <= 2100
        assert 1 <= month <= 12
        assert 1 <= day <= 31

        # Validate time part (HHMMSS)
        hour = int(time_part[:2])
        minute = int(time_part[2:4])
        second = int(time_part[4:6])
        assert 0 <= hour <= 23
        assert 0 <= minute <= 59
        assert 0 <= second <= 59


class TestInitializeRun:
    """Tests for run initialization."""

    def test_creates_run_directory(self, temp_project: Path) -> None:
        """Run directory is created successfully."""
        context_dir = temp_project / "context" / "test-app"
        prompts_dir = temp_project / "prompts" / "apps" / "test-app"

        run_dir = initialize_run(
            app_name="test-app",
            seed="A dark tale of mystery.",
            context_dir=context_dir,
            prompts_dir=prompts_dir,
            run_id="run-test-001",
            base_dir=temp_project,
        )

        assert run_dir.exists()
        assert run_dir.is_dir()
        assert run_dir.name == "run-test-001"

    def test_creates_inputs_json(self, temp_project: Path) -> None:
        """inputs.json is created with correct structure."""
        context_dir = temp_project / "context" / "test-app"
        prompts_dir = temp_project / "prompts" / "apps" / "test-app"

        run_dir = initialize_run(
            app_name="test-app",
            seed="A dark tale of mystery.",
            context_dir=context_dir,
            prompts_dir=prompts_dir,
            beats=5,
            run_id="run-test-002",
            base_dir=temp_project,
        )

        inputs_path = run_dir / "inputs.json"
        assert inputs_path.exists()

        with inputs_path.open() as f:
            inputs = json.load(f)

        assert inputs["app"] == "test-app"
        assert inputs["seed"] == "A dark tale of mystery."
        assert inputs["beats"] == 5
        assert inputs["run_id"] == "run-test-002"
        assert "timestamp" in inputs
        assert str(context_dir) in inputs["context_dir"]
        assert str(prompts_dir) in inputs["prompts_dir"]

    def test_creates_state_json(self, temp_project: Path) -> None:
        """state.json is created with correct initial structure."""
        context_dir = temp_project / "context" / "test-app"
        prompts_dir = temp_project / "prompts" / "apps" / "test-app"

        run_dir = initialize_run(
            app_name="test-app",
            seed="A dark tale of mystery.",
            context_dir=context_dir,
            prompts_dir=prompts_dir,
            run_id="run-test-003",
            base_dir=temp_project,
        )

        state_path = run_dir / "state.json"
        assert state_path.exists()

        with state_path.open() as f:
            state = json.load(f)

        assert state["app"] == "test-app"
        assert state["seed"] == "A dark tale of mystery."
        assert state["selected_context"] == {"location": None, "characters": []}
        assert state["outline"] == []
        assert state["sections"] == []
        assert state["summaries"] == []
        assert state["continuity_ledger"] == {}
        assert state["token_usage"] == []

    def test_creates_run_log(self, temp_project: Path) -> None:
        """run.log is created with initialization entries."""
        context_dir = temp_project / "context" / "test-app"
        prompts_dir = temp_project / "prompts" / "apps" / "test-app"

        run_dir = initialize_run(
            app_name="test-app",
            seed="A dark tale of mystery.",
            context_dir=context_dir,
            prompts_dir=prompts_dir,
            run_id="run-test-004",
            base_dir=temp_project,
        )

        log_path = run_dir / "run.log"
        assert log_path.exists()

        log_content = log_path.read_text()
        assert "test-app" in log_content
        assert "A dark tale of mystery." in log_content
        assert "[INFO]" in log_content

    def test_creates_artifacts_directory(self, temp_project: Path) -> None:
        """artifacts/ subdirectory is created."""
        context_dir = temp_project / "context" / "test-app"
        prompts_dir = temp_project / "prompts" / "apps" / "test-app"

        run_dir = initialize_run(
            app_name="test-app",
            seed="A dark tale.",
            context_dir=context_dir,
            prompts_dir=prompts_dir,
            run_id="run-test-005",
            base_dir=temp_project,
        )

        artifacts_dir = run_dir / "artifacts"
        assert artifacts_dir.exists()
        assert artifacts_dir.is_dir()

    def test_fails_if_run_already_exists(self, temp_project: Path) -> None:
        """Raises error if run directory already exists (exactly once constraint)."""
        context_dir = temp_project / "context" / "test-app"
        prompts_dir = temp_project / "prompts" / "apps" / "test-app"

        # First initialization succeeds
        initialize_run(
            app_name="test-app",
            seed="First run.",
            context_dir=context_dir,
            prompts_dir=prompts_dir,
            run_id="run-duplicate",
            base_dir=temp_project,
        )

        # Second initialization with same ID fails
        with pytest.raises(RunInitializationError) as exc_info:
            initialize_run(
                app_name="test-app",
                seed="Second run.",
                context_dir=context_dir,
                prompts_dir=prompts_dir,
                run_id="run-duplicate",
                base_dir=temp_project,
            )

        assert "already exists" in str(exc_info.value)

    def test_auto_generates_run_id(self, temp_project: Path) -> None:
        """Run ID is auto-generated if not provided."""
        context_dir = temp_project / "context" / "test-app"
        prompts_dir = temp_project / "prompts" / "apps" / "test-app"

        run_dir = initialize_run(
            app_name="test-app",
            seed="Auto ID test.",
            context_dir=context_dir,
            prompts_dir=prompts_dir,
            base_dir=temp_project,
        )

        assert run_dir.name.startswith("run-")

    def test_no_partial_state_on_failure(self, temp_project: Path) -> None:
        """Failed initialization leaves no partial state."""
        context_dir = temp_project / "context" / "test-app"
        prompts_dir = temp_project / "prompts" / "apps" / "test-app"
        runs_dir = temp_project / "runs"

        # Count existing items in runs directory
        initial_items = list(runs_dir.iterdir())

        # Mock json.dump to fail
        with patch("json.dump", side_effect=IOError("Simulated write failure")):
            with pytest.raises(RunInitializationError):
                initialize_run(
                    app_name="test-app",
                    seed="Should fail.",
                    context_dir=context_dir,
                    prompts_dir=prompts_dir,
                    run_id="run-should-not-exist",
                    base_dir=temp_project,
                )

        # Verify no new directories were created
        final_items = list(runs_dir.iterdir())
        # Filter out any temp directories that might not have been cleaned
        final_items = [
            item for item in final_items if not item.name.startswith(".tmp_")
        ]
        initial_items = [
            item for item in initial_items if not item.name.startswith(".tmp_")
        ]

        assert len(final_items) == len(initial_items)
        assert not (runs_dir / "run-should-not-exist").exists()

    def test_beats_none_when_not_provided(self, temp_project: Path) -> None:
        """beats is None in inputs.json when not provided."""
        context_dir = temp_project / "context" / "test-app"
        prompts_dir = temp_project / "prompts" / "apps" / "test-app"

        run_dir = initialize_run(
            app_name="test-app",
            seed="No beats specified.",
            context_dir=context_dir,
            prompts_dir=prompts_dir,
            run_id="run-no-beats",
            base_dir=temp_project,
        )

        inputs_path = run_dir / "inputs.json"
        with inputs_path.open() as f:
            inputs = json.load(f)

        assert inputs["beats"] is None


class TestRunLogger:
    """Tests for RunLogger."""

    def test_creates_log_entries(self, tmp_path: Path) -> None:
        """Logger writes entries to file."""
        log_path = tmp_path / "test.log"
        log_path.touch()

        logger = RunLogger(log_path)
        logger.info("Test message")

        content = log_path.read_text()
        assert "[INFO]" in content
        assert "Test message" in content

    def test_error_level(self, tmp_path: Path) -> None:
        """Logger writes ERROR level entries."""
        log_path = tmp_path / "test.log"
        log_path.touch()

        logger = RunLogger(log_path)
        logger.error("Something went wrong")

        content = log_path.read_text()
        assert "[ERROR]" in content
        assert "Something went wrong" in content

    def test_log_run_init(self, tmp_path: Path) -> None:
        """log_run_init writes all expected fields."""
        log_path = tmp_path / "test.log"
        log_path.touch()

        # Use paths relative to tmp_path for cross-platform compatibility
        context_dir = tmp_path / "context"
        prompts_dir = tmp_path / "prompts"

        logger = RunLogger(log_path)
        logger.log_run_init(
            app_name="my-app",
            seed="A mysterious story.",
            context_dir=context_dir,
            prompts_dir=prompts_dir,
        )

        content = log_path.read_text()
        assert "my-app" in content
        assert "A mysterious story." in content
        # Check for path components (works on both Windows and Unix)
        assert "context" in content
        assert "prompts" in content

    def test_timestamp_format(self, tmp_path: Path) -> None:
        """Log entries include ISO 8601 timestamps."""
        log_path = tmp_path / "test.log"
        log_path.touch()

        logger = RunLogger(log_path)
        logger.info("Timestamp test")

        content = log_path.read_text()
        # Check for ISO 8601 format markers
        assert "[20" in content  # Year starts with 20xx
        assert "T" in content  # ISO separator
        assert "+00:00" in content or "Z" in content  # UTC indicator


class TestGetRunLogger:
    """Tests for get_run_logger."""

    def test_returns_logger_for_existing_run(self, temp_project: Path) -> None:
        """Returns logger for an existing run directory."""
        context_dir = temp_project / "context" / "test-app"
        prompts_dir = temp_project / "prompts" / "apps" / "test-app"

        run_dir = initialize_run(
            app_name="test-app",
            seed="Test.",
            context_dir=context_dir,
            prompts_dir=prompts_dir,
            run_id="run-logger-test",
            base_dir=temp_project,
        )

        logger = get_run_logger(run_dir)
        assert isinstance(logger, RunLogger)
        assert logger.log_path == run_dir / "run.log"

    def test_fails_for_nonexistent_directory(self, tmp_path: Path) -> None:
        """Raises error for nonexistent run directory."""
        nonexistent = tmp_path / "runs" / "does-not-exist"

        with pytest.raises(RunInitializationError) as exc_info:
            get_run_logger(nonexistent)

        assert "does not exist" in str(exc_info.value)

    def test_fails_for_missing_log_file(self, tmp_path: Path) -> None:
        """Raises error if log file is missing."""
        run_dir = tmp_path / "runs" / "no-log"
        run_dir.mkdir(parents=True)

        with pytest.raises(RunInitializationError) as exc_info:
            get_run_logger(run_dir)

        assert "Log file does not exist" in str(exc_info.value)
