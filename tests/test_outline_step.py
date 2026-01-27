"""Tests for outline generation step."""

import json
from importlib import import_module
from pathlib import Path
from typing import Any

import pytest
import sys

# Import from the package using the hyphenated name
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Get project root for schema resolution
PROJECT_ROOT = Path(__file__).parent.parent
SCHEMA_BASE = PROJECT_ROOT / "src" / "llm-storytell" / "schemas"

# Handle hyphenated package name
outline_module = import_module("llm-storytell.steps.outline")
llm_module = import_module("llm-storytell.llm")
logging_module = import_module("llm-storytell.logging")
prompt_render_module = import_module("llm-storytell.prompt_render")

execute_outline_step = outline_module.execute_outline_step
OutlineStepError = outline_module.OutlineStepError
LLMResult = llm_module.LLMResult
LLMProvider = llm_module.LLMProvider
LLMProviderError = llm_module.LLMProviderError
RunLogger = logging_module.RunLogger


class _MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing."""

    def __init__(self, response_content: str | None = None) -> None:
        super().__init__(provider_name="mock")
        self._response_content = response_content or '{"beats": []}'
        self.calls: list[dict[str, Any]] = []
        self._should_fail = False

    def set_response(self, content: str) -> None:
        """Set the response content."""
        self._response_content = content

    def set_failure(self, should_fail: bool = True) -> None:
        """Configure provider to fail."""
        self._should_fail = should_fail

    def generate(
        self,
        prompt: str,
        *,
        step: str,
        model: str | None = None,
        **kwargs: Any,
    ) -> LLMResult:
        """Generate mock response."""
        self.calls.append({"prompt": prompt, "step": step, "model": model, **kwargs})

        if self._should_fail:
            raise LLMProviderError("Mock provider failure")

        return LLMResult(
            content=self._response_content,
            provider="mock",
            model=model or "mock-model",
            prompt_tokens=100,
            completion_tokens=200,
            total_tokens=300,
        )


@pytest.fixture
def temp_run_dir(tmp_path: Path) -> Path:
    """Create a temporary run directory with initial state."""
    run_dir = tmp_path / "run-test-001"
    run_dir.mkdir()
    (run_dir / "artifacts").mkdir()

    # Create initial state.json
    state = {
        "app": "grim-narrator",
        "seed": "A worker describes a day in a decaying city.",
        "selected_context": {
            "location": "terra.md",
            "characters": ["hero.md", "villain.md"],
        },
        "outline": [],
        "sections": [],
        "summaries": [],
        "continuity_ledger": {},
        "token_usage": [],
    }
    with (run_dir / "state.json").open("w", encoding="utf-8") as f:
        json.dump(state, f)

    # Create inputs.json
    inputs = {
        "run_id": "run-test-001",
        "app": "grim-narrator",
        "seed": "A worker describes a day in a decaying city.",
        "beats": 5,
    }
    with (run_dir / "inputs.json").open("w", encoding="utf-8") as f:
        json.dump(inputs, f)

    # Create run.log
    (run_dir / "run.log").touch()

    return run_dir


@pytest.fixture
def temp_context_dir(tmp_path: Path) -> Path:
    """Create a temporary context directory structure."""
    context_dir = tmp_path / "context" / "grim-narrator"
    context_dir.mkdir(parents=True)

    # Create lore_bible.md
    (context_dir / "lore_bible.md").write_text("# Lore Bible\n\nTest lore content.")

    # Create style directory
    style_dir = context_dir / "style"
    style_dir.mkdir()
    (style_dir / "tone.md").write_text("# Tone\n\nDark and moody.")
    (style_dir / "narration.md").write_text("# Narration\n\nFirst person.")

    # Create locations directory
    locations_dir = context_dir / "locations"
    locations_dir.mkdir()
    (locations_dir / "terra.md").write_text("# Terra\n\nA decaying city.")

    # Create characters directory
    characters_dir = context_dir / "characters"
    characters_dir.mkdir()
    (characters_dir / "hero.md").write_text("# Hero\n\nA brave hero.")
    (characters_dir / "villain.md").write_text("# Villain\n\nAn evil villain.")

    return context_dir


@pytest.fixture
def temp_prompts_dir(tmp_path: Path) -> Path:
    """Create a temporary prompts directory with outline template."""
    prompts_dir = tmp_path / "prompts" / "apps" / "grim-narrator"
    prompts_dir.mkdir(parents=True)

    # Create outline prompt template
    template_content = """Generate outline for: {seed}

Lore: {lore_bible}
Style: {style_rules}
Location: {location_context}
Characters: {character_context}

Generate {beats_count} beats.
"""
    (prompts_dir / "10_outline.md").write_text(template_content)

    return prompts_dir


@pytest.fixture
def valid_outline_json() -> str:
    """Return valid outline JSON for testing."""
    outline = {
        "beats": [
            {
                "beat_id": 1,
                "title": "Beginning",
                "summary": "The story begins with the worker waking up.",
            },
            {
                "beat_id": 2,
                "title": "Morning",
                "summary": "The worker goes to work in the factory.",
            },
            {
                "beat_id": 3,
                "title": "Incident",
                "summary": "Something unexpected happens at work.",
            },
            {
                "beat_id": 4,
                "title": "Discovery",
                "summary": "The worker discovers something important.",
            },
            {
                "beat_id": 5,
                "title": "End",
                "summary": "The story concludes with a grim realization.",
            },
        ]
    }
    return json.dumps(outline)


class TestExecuteOutlineStepSuccess:
    """Tests for successful outline step execution."""

    def test_generates_and_persists_outline(
        self,
        temp_run_dir: Path,
        temp_context_dir: Path,
        temp_prompts_dir: Path,
        valid_outline_json: str,
    ) -> None:
        """Successfully generates outline and persists to artifacts and state."""
        provider = _MockLLMProvider(response_content=valid_outline_json)
        logger = RunLogger(temp_run_dir / "run.log")

        execute_outline_step(
            run_dir=temp_run_dir,
            context_dir=temp_context_dir,
            prompts_dir=temp_prompts_dir,
            llm_provider=provider,
            logger=logger,
            schema_base=SCHEMA_BASE,
        )

        # Check artifact was created
        artifact_path = temp_run_dir / "artifacts" / "10_outline.json"
        assert artifact_path.exists()

        with artifact_path.open(encoding="utf-8") as f:
            artifact_data = json.load(f)
        assert "beats" in artifact_data
        assert len(artifact_data["beats"]) == 5

        # Check state was updated
        with (temp_run_dir / "state.json").open(encoding="utf-8") as f:
            state = json.load(f)
        assert len(state["outline"]) == 5
        assert len(state["token_usage"]) == 1
        assert state["token_usage"][0]["step"] == "outline"

        # Check LLM was called
        assert len(provider.calls) == 1
        assert provider.calls[0]["step"] == "outline"

    def test_loads_all_context_files(
        self,
        temp_run_dir: Path,
        temp_context_dir: Path,
        temp_prompts_dir: Path,
        valid_outline_json: str,
    ) -> None:
        """Loads all required context files for prompt rendering."""
        provider = _MockLLMProvider(response_content=valid_outline_json)
        logger = RunLogger(temp_run_dir / "run.log")

        execute_outline_step(
            run_dir=temp_run_dir,
            context_dir=temp_context_dir,
            prompts_dir=temp_prompts_dir,
            llm_provider=provider,
            logger=logger,
            schema_base=SCHEMA_BASE,
        )

        # Check prompt was rendered with context
        call = provider.calls[0]
        prompt = call["prompt"]
        assert "Test lore content" in prompt  # lore_bible
        assert "Dark and moody" in prompt  # style/tone.md
        assert "First person" in prompt  # style/narration.md
        assert "A decaying city" in prompt  # location
        assert "A brave hero" in prompt  # character
        assert "An evil villain" in prompt  # character

    def test_handles_missing_location_context(
        self,
        temp_run_dir: Path,
        temp_context_dir: Path,
        temp_prompts_dir: Path,
        valid_outline_json: str,
    ) -> None:
        """Handles missing location context gracefully."""
        # Update state to have no location
        with (temp_run_dir / "state.json").open("r", encoding="utf-8") as f:
            state = json.load(f)
        state["selected_context"]["location"] = None
        with (temp_run_dir / "state.json").open("w", encoding="utf-8") as f:
            json.dump(state, f)

        provider = _MockLLMProvider(response_content=valid_outline_json)
        logger = RunLogger(temp_run_dir / "run.log")

        # Should not raise error
        execute_outline_step(
            run_dir=temp_run_dir,
            context_dir=temp_context_dir,
            prompts_dir=temp_prompts_dir,
            llm_provider=provider,
            logger=logger,
            schema_base=SCHEMA_BASE,
        )

    def test_handles_missing_character_context(
        self,
        temp_run_dir: Path,
        temp_context_dir: Path,
        temp_prompts_dir: Path,
        valid_outline_json: str,
    ) -> None:
        """Handles missing character context gracefully."""
        # Update state to have no characters
        with (temp_run_dir / "state.json").open("r", encoding="utf-8") as f:
            state = json.load(f)
        state["selected_context"]["characters"] = []
        with (temp_run_dir / "state.json").open("w", encoding="utf-8") as f:
            json.dump(state, f)

        provider = _MockLLMProvider(response_content=valid_outline_json)
        logger = RunLogger(temp_run_dir / "run.log")

        # Should not raise error
        execute_outline_step(
            run_dir=temp_run_dir,
            context_dir=temp_context_dir,
            prompts_dir=temp_prompts_dir,
            llm_provider=provider,
            logger=logger,
            schema_base=SCHEMA_BASE,
        )


class TestExecuteOutlineStepErrors:
    """Tests for error handling in outline step."""

    def test_fails_on_missing_state_file(
        self,
        temp_run_dir: Path,
        temp_context_dir: Path,
        temp_prompts_dir: Path,
    ) -> None:
        """Fails if state.json is missing."""
        (temp_run_dir / "state.json").unlink()

        provider = _MockLLMProvider()
        logger = RunLogger(temp_run_dir / "run.log")

        with pytest.raises(OutlineStepError) as exc_info:
            execute_outline_step(
                run_dir=temp_run_dir,
                context_dir=temp_context_dir,
                prompts_dir=temp_prompts_dir,
                llm_provider=provider,
                logger=logger,
            )

        assert "State file not found" in str(exc_info.value)

    def test_fails_on_missing_inputs_file(
        self,
        temp_run_dir: Path,
        temp_context_dir: Path,
        temp_prompts_dir: Path,
    ) -> None:
        """Fails if inputs.json is missing."""
        (temp_run_dir / "inputs.json").unlink()

        provider = _MockLLMProvider()
        logger = RunLogger(temp_run_dir / "run.log")

        with pytest.raises(OutlineStepError) as exc_info:
            execute_outline_step(
                run_dir=temp_run_dir,
                context_dir=temp_context_dir,
                prompts_dir=temp_prompts_dir,
                llm_provider=provider,
                logger=logger,
            )

        assert "Inputs file not found" in str(exc_info.value)

    def test_fails_on_missing_seed(
        self,
        temp_run_dir: Path,
        temp_context_dir: Path,
        temp_prompts_dir: Path,
    ) -> None:
        """Fails if seed is missing from state."""
        with (temp_run_dir / "state.json").open("r", encoding="utf-8") as f:
            state = json.load(f)
        del state["seed"]
        with (temp_run_dir / "state.json").open("w", encoding="utf-8") as f:
            json.dump(state, f)

        provider = _MockLLMProvider()
        logger = RunLogger(temp_run_dir / "run.log")

        with pytest.raises(OutlineStepError) as exc_info:
            execute_outline_step(
                run_dir=temp_run_dir,
                context_dir=temp_context_dir,
                prompts_dir=temp_prompts_dir,
                llm_provider=provider,
                logger=logger,
            )

        assert "Seed not found" in str(exc_info.value)

    def test_fails_on_invalid_beats_count(
        self,
        temp_run_dir: Path,
        temp_context_dir: Path,
        temp_prompts_dir: Path,
    ) -> None:
        """Fails if beats count is invalid."""
        with (temp_run_dir / "inputs.json").open("r", encoding="utf-8") as f:
            inputs = json.load(f)
        inputs["beats"] = 25  # Invalid: > 20
        with (temp_run_dir / "inputs.json").open("w", encoding="utf-8") as f:
            json.dump(inputs, f)

        provider = _MockLLMProvider()
        logger = RunLogger(temp_run_dir / "run.log")

        with pytest.raises(OutlineStepError) as exc_info:
            execute_outline_step(
                run_dir=temp_run_dir,
                context_dir=temp_context_dir,
                prompts_dir=temp_prompts_dir,
                llm_provider=provider,
                logger=logger,
            )

        assert "Invalid beats count" in str(exc_info.value)

    def test_fails_on_missing_lore_bible(
        self,
        temp_run_dir: Path,
        temp_context_dir: Path,
        temp_prompts_dir: Path,
    ) -> None:
        """Fails if lore_bible.md is missing."""
        (temp_context_dir / "lore_bible.md").unlink()

        provider = _MockLLMProvider()
        logger = RunLogger(temp_run_dir / "run.log")

        with pytest.raises(OutlineStepError) as exc_info:
            execute_outline_step(
                run_dir=temp_run_dir,
                context_dir=temp_context_dir,
                prompts_dir=temp_prompts_dir,
                llm_provider=provider,
                logger=logger,
            )

        assert "Lore bible not found" in str(exc_info.value)

    def test_fails_on_missing_prompt_template(
        self,
        temp_run_dir: Path,
        temp_context_dir: Path,
        temp_prompts_dir: Path,
    ) -> None:
        """Fails if prompt template is missing."""
        (temp_prompts_dir / "10_outline.md").unlink()

        provider = _MockLLMProvider()
        logger = RunLogger(temp_run_dir / "run.log")

        with pytest.raises(OutlineStepError) as exc_info:
            execute_outline_step(
                run_dir=temp_run_dir,
                context_dir=temp_context_dir,
                prompts_dir=temp_prompts_dir,
                llm_provider=provider,
                logger=logger,
            )

        assert "Prompt template not found" in str(exc_info.value)

    def test_fails_on_llm_provider_error(
        self,
        temp_run_dir: Path,
        temp_context_dir: Path,
        temp_prompts_dir: Path,
    ) -> None:
        """Fails if LLM provider raises an error."""
        provider = _MockLLMProvider()
        provider.set_failure(should_fail=True)

        logger = RunLogger(temp_run_dir / "run.log")

        with pytest.raises(OutlineStepError) as exc_info:
            execute_outline_step(
                run_dir=temp_run_dir,
                context_dir=temp_context_dir,
                prompts_dir=temp_prompts_dir,
                llm_provider=provider,
                logger=logger,
            )

        assert "LLM provider error" in str(exc_info.value)

    def test_fails_on_invalid_json_response(
        self,
        temp_run_dir: Path,
        temp_context_dir: Path,
        temp_prompts_dir: Path,
    ) -> None:
        """Fails if LLM response is not valid JSON."""
        provider = _MockLLMProvider(response_content="This is not JSON")

        logger = RunLogger(temp_run_dir / "run.log")

        with pytest.raises(OutlineStepError) as exc_info:
            execute_outline_step(
                run_dir=temp_run_dir,
                context_dir=temp_context_dir,
                prompts_dir=temp_prompts_dir,
                llm_provider=provider,
                logger=logger,
            )

        assert "Invalid JSON" in str(exc_info.value)

    def test_fails_on_schema_validation_error(
        self,
        temp_run_dir: Path,
        temp_context_dir: Path,
        temp_prompts_dir: Path,
    ) -> None:
        """Fails if outline doesn't match schema."""
        # Invalid outline: missing required fields
        invalid_outline = json.dumps(
            {"beats": [{"beat_id": 1}]}
        )  # Missing title and summary
        provider = _MockLLMProvider(response_content=invalid_outline)

        logger = RunLogger(temp_run_dir / "run.log")

        with pytest.raises(OutlineStepError) as exc_info:
            execute_outline_step(
                run_dir=temp_run_dir,
                context_dir=temp_context_dir,
                prompts_dir=temp_prompts_dir,
                llm_provider=provider,
                logger=logger,
            )

        assert "Schema validation failed" in str(exc_info.value)

    def test_fails_on_wrong_beat_count(
        self,
        temp_run_dir: Path,
        temp_context_dir: Path,
        temp_prompts_dir: Path,
    ) -> None:
        """Fails if outline has wrong number of beats."""
        # Outline with 3 beats but 5 were requested
        wrong_count_outline = {
            "beats": [
                {"beat_id": 1, "title": "One", "summary": "First beat summary here"},
                {"beat_id": 2, "title": "Two", "summary": "Second beat summary here"},
                {"beat_id": 3, "title": "Three", "summary": "Third beat summary here"},
            ]
        }
        provider = _MockLLMProvider(response_content=json.dumps(wrong_count_outline))

        logger = RunLogger(temp_run_dir / "run.log")

        with pytest.raises(OutlineStepError) as exc_info:
            execute_outline_step(
                run_dir=temp_run_dir,
                context_dir=temp_context_dir,
                prompts_dir=temp_prompts_dir,
                llm_provider=provider,
                logger=logger,
            )

        assert "but 5 were requested" in str(exc_info.value)

    def test_logs_stage_start_and_end(
        self,
        temp_run_dir: Path,
        temp_context_dir: Path,
        temp_prompts_dir: Path,
        valid_outline_json: str,
    ) -> None:
        """Logs stage start and end correctly."""
        provider = _MockLLMProvider(response_content=valid_outline_json)
        logger = RunLogger(temp_run_dir / "run.log")

        execute_outline_step(
            run_dir=temp_run_dir,
            context_dir=temp_context_dir,
            prompts_dir=temp_prompts_dir,
            llm_provider=provider,
            logger=logger,
            schema_base=SCHEMA_BASE,
        )

        log_content = (temp_run_dir / "run.log").read_text()
        assert "Stage started: outline" in log_content
        assert "Stage ended: outline (success)" in log_content

    def test_logs_failure_on_error(
        self,
        temp_run_dir: Path,
        temp_context_dir: Path,
        temp_prompts_dir: Path,
    ) -> None:
        """Logs failure when step errors."""
        provider = _MockLLMProvider()
        provider.set_failure(should_fail=True)

        logger = RunLogger(temp_run_dir / "run.log")

        with pytest.raises(OutlineStepError):
            execute_outline_step(
                run_dir=temp_run_dir,
                context_dir=temp_context_dir,
                prompts_dir=temp_prompts_dir,
                llm_provider=provider,
                logger=logger,
            )

        log_content = (temp_run_dir / "run.log").read_text()
        assert "Stage started: outline" in log_content
        assert "Stage ended: outline (failure)" in log_content
