"""End-to-end tests for the complete pipeline execution."""

import json
from importlib import import_module
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import sys

# Import from the package
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

cli_module = import_module("llm_storytell.cli")
llm_module = import_module("llm_storytell.llm")

main = cli_module.main
LLMResult = llm_module.LLMResult
LLMProvider = llm_module.LLMProvider

# Get project root for schema resolution
PROJECT_ROOT = Path(__file__).parent.parent
SCHEMA_BASE = PROJECT_ROOT / "src" / "llm_storytell" / "schemas"


class MockLLMProvider(LLMProvider):
    """Mock LLM provider that returns deterministic responses for E2E testing."""

    def __init__(self) -> None:
        super().__init__(provider_name="mock")
        self.calls: list[dict[str, Any]] = []
        self._requested_beats: int | None = None

    def generate(
        self,
        prompt: str,
        *,
        step: str,
        model: str | None = None,
        **kwargs: Any,
    ) -> LLMResult:
        """Generate mock response based on step type."""
        self.calls.append({"prompt": prompt, "step": step, "model": model, **kwargs})

        # Return appropriate mock response based on step
        if step == "outline":
            # Extract beats_count from prompt (app-defaults uses "Beats count:\nN")
            beats_count = 3  # default
            import re

            match = re.search(r"Beats count:\s*(\d+)", prompt)
            if match:
                beats_count = int(match.group(1))
            else:
                match = re.search(r"Generate\s+(\d+)\s+beats", prompt)
                if match:
                    beats_count = int(match.group(1))
                else:
                    match = re.search(r"(\d+)\s+beats", prompt)
                    if match:
                        beats_count = int(match.group(1))
            self._requested_beats = beats_count

            # Return outline with requested number of beats
            beats = []
            for i in range(1, beats_count + 1):
                beats.append(
                    {
                        "beat_id": i,
                        "title": f"Beat {i}",
                        "summary": f"This is beat {i} of the story. Important events happen here.",
                    }
                )
            outline = {"beats": beats}
            content = json.dumps(outline)

        elif step.startswith("section_"):
            # Return section content with YAML frontmatter
            # Extract section index from step name (e.g., "section_00" -> 0)
            import re

            match = re.search(r"section_(\d+)", step)
            section_index = int(match.group(1)) if match else 0
            section_num = section_index + 1  # 1-based for display

            content = f"""---
section_id: {section_num}
local_summary: "Section {section_num} summary: The protagonist experiences significant events. This section develops key plot points and character relationships. Important narrative threads are advanced, and the story's central themes are explored through detailed scenes and interactions."
new_entities: []
new_locations: []
unresolved_threads: []
---

This is the content of section {section_num}. The protagonist experiences something significant here. The narrative continues with detailed descriptions and character development.

More content follows, building on previous sections and maintaining continuity with the overall story arc.
"""

        elif step.startswith("summarize_"):
            # Return summary JSON
            # Extract section index from step name (e.g., "summarize_00" -> 0)
            import re

            match = re.search(r"summarize_(\d+)", step)
            section_index = int(match.group(1)) if match else 0
            section_num = section_index + 1  # 1-based for display
            summary = {
                "summary": f"Section {section_num} summary: The protagonist experiences significant events. This section develops key plot points and character relationships. Important narrative threads are advanced, and the story's central themes are explored through detailed scenes and interactions.",
                "continuity_updates": {
                    "protagonist_state": "active",
                    "city_mood": "decaying",
                },
            }
            content = json.dumps(summary)

        elif step == "critic":
            # Return critic response in two-block format (required by critic step)
            # Count sections from previous calls
            section_calls = [c for c in self.calls if c["step"].startswith("section_")]
            num_sections = len(section_calls)
            # Use requested beats if available, otherwise use number of sections generated
            if self._requested_beats is not None:
                num_sections = self._requested_beats
            final_script = "\n\n".join(
                [
                    f"# Section {i + 1}\n\nThis is the final polished version of section {i + 1}."
                    for i in range(num_sections)
                ]
            )
            editor_report = {
                "issues_found": [],
                "changes_applied": [
                    "Minor grammar corrections",
                    "Consistency improvements",
                ],
            }
            content = (
                "===FINAL_SCRIPT===\n\n"
                + final_script
                + "\n===EDITOR_REPORT_JSON===\n\n"
                + json.dumps(editor_report, indent=2)
            )

        else:
            content = '{"result": "unknown step"}'

        return LLMResult(
            content=content,
            provider="mock",
            model=model or "mock-model",
            prompt_tokens=100,
            completion_tokens=200,
            total_tokens=300,
        )


@pytest.fixture
def temp_app_structure(tmp_path: Path) -> Path:
    """Create a temporary app structure for testing (apps/<app>/context/ + app-defaults)."""
    import shutil

    base_dir = tmp_path
    PROJECT_ROOT = Path(__file__).parent.parent

    # Create apps/test-app/context/
    context_dir = base_dir / "apps" / "test-app" / "context"
    context_dir.mkdir(parents=True)
    (context_dir / "lore_bible.md").write_text(
        "# Lore Bible\n\nThis is a test lore bible for E2E testing."
    )
    style_dir = context_dir / "style"
    style_dir.mkdir()
    (style_dir / "tone.md").write_text("# Tone\n\nDark and moody tone.")
    (style_dir / "narration.md").write_text("# Narration\n\nThird person limited.")
    locations_dir = context_dir / "locations"
    locations_dir.mkdir()
    (locations_dir / "city.md").write_text("# City\n\nA decaying urban environment.")
    characters_dir = context_dir / "characters"
    characters_dir.mkdir()
    (characters_dir / "protagonist.md").write_text(
        "# Protagonist\n\nA worker in the city."
    )
    (characters_dir / "antagonist.md").write_text(
        "# Antagonist\n\nA mysterious figure."
    )

    # Copy prompts/app-defaults so resolver uses them when app has no prompts/
    app_defaults_src = PROJECT_ROOT / "prompts" / "app-defaults"
    app_defaults_dest = base_dir / "prompts" / "app-defaults"
    app_defaults_dest.mkdir(parents=True)
    if app_defaults_src.exists():
        for f in app_defaults_src.glob("*.md"):
            shutil.copy2(f, app_defaults_dest / f.name)

    # Schemas (required for validation)
    SCHEMA_SOURCE = PROJECT_ROOT / "src" / "llm_storytell" / "schemas"
    SCHEMA_DEST = base_dir / "src" / "llm_storytell" / "schemas"
    SCHEMA_DEST.mkdir(parents=True)
    if SCHEMA_SOURCE.exists():
        for schema_file in SCHEMA_SOURCE.glob("*.json"):
            shutil.copy2(schema_file, SCHEMA_DEST / schema_file.name)

    return base_dir


def test_e2e_full_pipeline(
    temp_app_structure: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test complete end-to-end pipeline execution."""
    # Change to temp directory
    original_cwd = Path.cwd()
    try:
        monkeypatch.chdir(temp_app_structure)

        # Create mock provider
        mock_provider = MockLLMProvider()

        # Patch the LLM provider creation to use our mock
        def mock_create_provider(
            config_path: Path, default_model: str = "gpt-4"
        ) -> Any:
            return mock_provider

        # Run the CLI command
        # Patch the function using string path (more reliable for imported modules)
        with patch(
            "llm_storytell.cli._create_llm_provider_from_config", mock_create_provider
        ):
            exit_code = main(
                [
                    "run",
                    "--app",
                    "test-app",
                    "--seed",
                    "A worker describes a day in a decaying city.",
                    "--beats",
                    "3",
                    "--run-id",
                    "test-run-001",
                ]
            )

        # If test failed, print the run log for debugging
        run_dir = temp_app_structure / "runs" / "test-run-001"
        if exit_code != 0 and run_dir.exists():
            log_path = run_dir / "run.log"
            if log_path.exists():
                print("\n=== Run Log ===")
                print(log_path.read_text(encoding="utf-8"))
                print("===============\n")

        # Verify exit code
        assert exit_code == 0

        # Verify run directory was created
        run_dir = temp_app_structure / "runs" / "test-run-001"
        assert run_dir.exists()
        assert (run_dir / "artifacts").exists()

        # Verify inputs.json
        inputs_path = run_dir / "inputs.json"
        assert inputs_path.exists()
        with inputs_path.open(encoding="utf-8") as f:
            inputs = json.load(f)
        assert inputs["app"] == "test-app"
        assert inputs["seed"] == "A worker describes a day in a decaying city."
        assert inputs["beats"] == 3

        # Verify state.json
        state_path = run_dir / "state.json"
        assert state_path.exists()
        with state_path.open(encoding="utf-8") as f:
            state = json.load(f)
        assert state["app"] == "test-app"
        assert "selected_context" in state
        assert len(state["outline"]) == 3
        assert len(state["sections"]) == 3
        assert len(state["summaries"]) == 3
        assert "continuity_ledger" in state
        assert len(state["token_usage"]) > 0

        # Verify artifacts
        assert (run_dir / "artifacts" / "10_outline.json").exists()
        for i in range(1, 4):
            assert (run_dir / "artifacts" / f"20_section_{i:02d}.md").exists()
        assert (run_dir / "artifacts" / "final_script.md").exists()
        assert (run_dir / "artifacts" / "editor_report.json").exists()

        # Verify final script content
        final_script_path = run_dir / "artifacts" / "final_script.md"
        with final_script_path.open(encoding="utf-8") as f:
            final_script = f.read()
        assert "Section 1" in final_script
        assert "Section 2" in final_script
        assert "Section 3" in final_script

        # Verify editor report
        editor_report_path = run_dir / "artifacts" / "editor_report.json"
        with editor_report_path.open(encoding="utf-8") as f:
            editor_report = json.load(f)
            assert "issues_found" in editor_report
            assert "changes_applied" in editor_report

        # Verify run.log
        log_path = run_dir / "run.log"
        assert log_path.exists()
        log_content = log_path.read_text(encoding="utf-8")
        assert "Run initialized" in log_content
        assert "outline" in log_content
        assert "section" in log_content
        assert "critic" in log_content

    finally:
        monkeypatch.chdir(original_cwd)


def test_e2e_run_completion_prints_token_summary(
    temp_app_structure: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Successful run prints Run complete, Model, Tokens, and Artifacts line."""
    monkeypatch.chdir(temp_app_structure)
    mock_provider = MockLLMProvider()

    def mock_create_provider(config_path: Path, default_model: str = "gpt-4") -> Any:
        return mock_provider

    with patch(
        "llm_storytell.cli._create_llm_provider_from_config", mock_create_provider
    ):
        exit_code = main(
            [
                "run",
                "--app",
                "test-app",
                "--seed",
                "A worker describes a day in a decaying city.",
                "--beats",
                "2",
                "--run-id",
                "test-run-summary",
            ]
        )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Run complete." in out
    assert "Model:" in out
    assert "Tokens:" in out
    assert "Artifacts are in:" in out


def test_e2e_without_beats_override(
    temp_app_structure: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test E2E pipeline without beats override (uses default)."""
    original_cwd = Path.cwd()
    try:
        monkeypatch.chdir(temp_app_structure)

        mock_provider = MockLLMProvider()

        def mock_create_provider(
            config_path: Path, default_model: str = "gpt-4"
        ) -> Any:
            return mock_provider

        # Run without --beats (should use default or prompt-based)
        with patch(
            "llm_storytell.cli._create_llm_provider_from_config", mock_create_provider
        ):
            exit_code = main(
                [
                    "run",
                    "--app",
                    "test-app",
                    "--seed",
                    "A simple story.",
                    "--run-id",
                    "test-run-002",
                ]
            )

        assert exit_code == 0

        run_dir = temp_app_structure / "runs" / "test-run-002"
        assert run_dir.exists()

        # Verify state was updated
        state_path = run_dir / "state.json"
        with state_path.open(encoding="utf-8") as f:
            state = json.load(f)
        assert len(state["outline"]) > 0

    finally:
        monkeypatch.chdir(original_cwd)


def test_e2e_model_flag_passed_to_provider_and_used_for_all_calls(
    temp_app_structure: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When --model is set, that model is passed to the provider and used for all LLM calls in the run."""
    original_cwd = Path.cwd()
    try:
        monkeypatch.chdir(temp_app_structure)

        mock_provider = MockLLMProvider()
        provider_create_calls: list[tuple[Any, ...]] = []

        def spy_create_provider(
            config_path: Path, default_model: str = "gpt-4.1-mini"
        ) -> Any:
            provider_create_calls.append((config_path, default_model))
            return mock_provider

        with patch(
            "llm_storytell.cli._create_llm_provider_from_config", spy_create_provider
        ):
            exit_code = main(
                [
                    "run",
                    "--app",
                    "test-app",
                    "--seed",
                    "A worker describes a day.",
                    "--beats",
                    "2",
                    "--run-id",
                    "test-run-model-flag",
                    "--model",
                    "gpt-4.1-nano",
                ]
            )

        assert exit_code == 0
        assert len(provider_create_calls) == 1
        _, default_model = provider_create_calls[0]
        assert default_model == "gpt-4.1-nano"
        # Provider is created once; all steps use it without passing model=, so all calls use that model
        assert len(mock_provider.calls) > 0
    finally:
        monkeypatch.chdir(original_cwd)


def test_e2e_default_model_when_no_model_flag(
    temp_app_structure: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When --model is not set, default gpt-4.1-mini is passed to the provider."""
    original_cwd = Path.cwd()
    try:
        monkeypatch.chdir(temp_app_structure)

        mock_provider = MockLLMProvider()
        provider_create_calls: list[tuple[Any, ...]] = []

        def spy_create_provider(
            config_path: Path, default_model: str = "gpt-4.1-mini"
        ) -> Any:
            provider_create_calls.append((config_path, default_model))
            return mock_provider

        with patch(
            "llm_storytell.cli._create_llm_provider_from_config", spy_create_provider
        ):
            exit_code = main(
                [
                    "run",
                    "--app",
                    "test-app",
                    "--seed",
                    "A simple story.",
                    "--run-id",
                    "test-run-default-model",
                    "--beats",
                    "1",
                ]
            )

        assert exit_code == 0
        assert len(provider_create_calls) == 1
        _, default_model = provider_create_calls[0]
        assert default_model == "gpt-4.1-mini"
    finally:
        monkeypatch.chdir(original_cwd)


def test_e2e_validates_beats_range(
    temp_app_structure: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that invalid beats range is rejected."""
    original_cwd = Path.cwd()
    try:
        monkeypatch.chdir(temp_app_structure)

        # Test beats too high
        exit_code = main(
            [
                "run",
                "--app",
                "test-app",
                "--seed",
                "A story.",
                "--beats",
                "25",
            ]
        )
        assert exit_code == 1

        # Test beats too low
        exit_code = main(
            [
                "run",
                "--app",
                "test-app",
                "--seed",
                "A story.",
                "--beats",
                "0",
            ]
        )
        assert exit_code == 1

    finally:
        monkeypatch.chdir(original_cwd)


def test_e2e_requires_seed(
    temp_app_structure: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that --seed is required."""
    original_cwd = Path.cwd()
    try:
        monkeypatch.chdir(temp_app_structure)

        exit_code = main(
            [
                "run",
                "--app",
                "test-app",
            ]
        )
        assert exit_code == 1

    finally:
        monkeypatch.chdir(original_cwd)


def test_e2e_fails_when_lore_bible_missing(
    temp_app_structure: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Run fails early with explicit message if lore_bible.md is missing."""
    original_cwd = Path.cwd()
    try:
        monkeypatch.chdir(temp_app_structure)
        (
            temp_app_structure / "apps" / "test-app" / "context" / "lore_bible.md"
        ).unlink()

        # App resolution fails (sys.exit(1)), so main() does not return
        with pytest.raises(SystemExit) as exc_info:
            main(
                [
                    "run",
                    "--app",
                    "test-app",
                    "--seed",
                    "A story.",
                    "--beats",
                    "2",
                ]
            )
        assert exc_info.value.code == 1

    finally:
        monkeypatch.chdir(original_cwd)


def test_e2e_fails_when_characters_missing(
    temp_app_structure: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Run fails early with explicit message if characters directory is missing."""
    original_cwd = Path.cwd()
    try:
        monkeypatch.chdir(temp_app_structure)
        import shutil

        shutil.rmtree(
            temp_app_structure / "apps" / "test-app" / "context" / "characters"
        )

        exit_code = main(
            [
                "run",
                "--app",
                "test-app",
                "--seed",
                "A story.",
                "--beats",
                "2",
            ]
        )
        assert exit_code == 1

    finally:
        monkeypatch.chdir(original_cwd)


def test_e2e_fails_when_characters_empty(
    temp_app_structure: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Run fails early with explicit message if characters directory has no .md files."""
    original_cwd = Path.cwd()
    try:
        monkeypatch.chdir(temp_app_structure)
        for f in (
            temp_app_structure / "apps" / "test-app" / "context" / "characters"
        ).glob("*"):
            f.unlink()

        exit_code = main(
            [
                "run",
                "--app",
                "test-app",
                "--seed",
                "A story.",
                "--beats",
                "2",
            ]
        )
        assert exit_code == 1

    finally:
        monkeypatch.chdir(original_cwd)


def test_e2e_succeeds_when_optional_locations_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Run still succeeds when locations directory is missing (optional)."""
    import shutil

    base_dir = tmp_path
    project_root = Path(__file__).parent.parent

    # apps/minimal-app/context/ (no locations/)
    context_dir = base_dir / "apps" / "minimal-app" / "context"
    context_dir.mkdir(parents=True)
    (context_dir / "lore_bible.md").write_text("# Lore")
    (context_dir / "characters").mkdir()
    (context_dir / "characters" / "one.md").write_text("# One")

    # Copy prompts/app-defaults
    app_defaults_src = project_root / "prompts" / "app-defaults"
    app_defaults_dest = base_dir / "prompts" / "app-defaults"
    app_defaults_dest.mkdir(parents=True)
    if app_defaults_src.exists():
        for f in app_defaults_src.glob("*.md"):
            shutil.copy2(f, app_defaults_dest / f.name)

    schema_src = project_root / "src" / "llm_storytell" / "schemas"
    schema_dest = base_dir / "src" / "llm_storytell" / "schemas"
    schema_dest.mkdir(parents=True)
    if schema_src.exists():
        for f in schema_src.glob("*.json"):
            shutil.copy2(f, schema_dest / f.name)

    original_cwd = Path.cwd()
    try:
        monkeypatch.chdir(base_dir)
        mock_provider = MockLLMProvider()

        def mock_create_provider(
            config_path: Path, default_model: str = "gpt-4"
        ) -> Any:
            return mock_provider

        with patch(
            "llm_storytell.cli._create_llm_provider_from_config", mock_create_provider
        ):
            exit_code = main(
                [
                    "run",
                    "--app",
                    "minimal-app",
                    "--seed",
                    "A story.",
                    "--beats",
                    "1",
                    "--run-id",
                    "test-optional-loc",
                ]
            )
        assert exit_code == 0
        state_path = base_dir / "runs" / "test-optional-loc" / "state.json"
        assert state_path.exists()
        with state_path.open(encoding="utf-8") as f:
            state = json.load(f)
        assert state["selected_context"]["location"] is None
        assert "world_files" in state["selected_context"]
    finally:
        monkeypatch.chdir(original_cwd)
