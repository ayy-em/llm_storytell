"""Tests for section generation loop and summarization."""

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
SCHEMA_BASE = PROJECT_ROOT / "src" / "llm_storytell" / "schemas"

section_module = import_module("llm_storytell.steps.section")
summarize_module = import_module("llm_storytell.steps.summarize")
continuity_module = import_module("llm_storytell.continuity")
llm_module = import_module("llm_storytell.llm")
logging_module = import_module("llm_storytell.logging")

execute_section_step = section_module.execute_section_step
SectionStepError = section_module.SectionStepError
execute_summarize_step = summarize_module.execute_summarize_step
SummarizeStepError = summarize_module.SummarizeStepError
build_rolling_summary = continuity_module.build_rolling_summary
merge_continuity_updates = continuity_module.merge_continuity_updates
get_continuity_context = continuity_module.get_continuity_context
LLMResult = llm_module.LLMResult
LLMProvider = llm_module.LLMProvider
LLMProviderError = llm_module.LLMProviderError
RunLogger = logging_module.RunLogger


class _MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing."""

    def __init__(self, response_content: str | None = None) -> None:
        super().__init__(provider_name="mock")
        self._response_content = response_content or ""
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
def temp_run_dir_with_outline(tmp_path: Path) -> Path:
    """Create a temporary run directory with outline in state."""
    run_dir = tmp_path / "run-test-001"
    run_dir.mkdir()
    (run_dir / "artifacts").mkdir()

    # Create state with outline
    state = {
        "app": "grim-narrator",
        "seed": "A worker describes a day in a decaying city.",
        "selected_context": {
            "location": "terra.md",
            "characters": ["hero.md", "villain.md"],
        },
        "outline": [
            {"beat_id": 1, "title": "Beginning", "summary": "The story begins."},
            {"beat_id": 2, "title": "Middle", "summary": "The story develops."},
            {"beat_id": 3, "title": "End", "summary": "The story concludes."},
        ],
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
        "beats": 3,
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
    """Create a temporary prompts directory with section and summarize templates."""
    prompts_dir = tmp_path / "prompts" / "apps" / "grim-narrator"
    prompts_dir.mkdir(parents=True)

    # Create section prompt template
    section_template = """Generate section {section_id} for outline beat:
{outline_beat}

Rolling summary:
{rolling_summary}

Continuity:
{continuity_context}

Lore: {lore_bible}
Style: {style_rules}
Location: {location_context}
Characters: {character_context}

Generate section with YAML frontmatter.
"""
    (prompts_dir / "20_section.md").write_text(section_template)

    # Create summarize prompt template
    summarize_template = """Summarize section {section_id}:

{section_content}

Return JSON with summary and continuity_updates.
"""
    (prompts_dir / "21_summarize.md").write_text(summarize_template)

    return prompts_dir


@pytest.fixture
def valid_section_content() -> str:
    """Return valid section content with frontmatter."""
    return """---
section_id: 1
outline_id: beginning
pov: first_person
timeline: day_1
status: draft
local_summary: The worker wakes up in a decaying city. The morning fog clings to the riverbank as they begin their daily routine. This establishes the grim setting and introduces the protagonist's perspective on their world.
new_entities: [worker, factory]
new_locations: [apartment, factory]
unresolved_threads: [mystery, conflict]
---

## The Beginning

The fog clung to the riverbank as the worker woke up.
"""


@pytest.fixture
def valid_summary_json() -> str:
    """Return valid summary JSON for testing."""
    summary = {
        "section_id": 1,
        "summary": "The worker wakes up in a decaying city. The fog clings to the riverbank as they begin their day. This establishes the setting and introduces the protagonist. The narrative establishes a grim tone through the description of the decaying urban environment and the worker's perspective. The morning routine is interrupted by an underlying sense of unease that permeates the scene.",
        "continuity_updates": {
            "protagonist": "worker",
            "current_location": "apartment",
            "mood": "grim",
        },
    }
    return json.dumps(summary)


class TestContinuityFunctions:
    """Tests for continuity utility functions."""

    def test_build_rolling_summary_empty(self) -> None:
        """Returns default message for empty summaries."""
        result = build_rolling_summary([])
        assert result == "No previous sections."

    def test_build_rolling_summary_single(self) -> None:
        """Builds summary from single section."""
        summaries = [
            {
                "section_id": 1,
                "summary": "The worker wakes up in a decaying city.",
            }
        ]
        result = build_rolling_summary(summaries)
        assert "Section 01:" in result
        assert "The worker wakes up" in result

    def test_build_rolling_summary_multiple(self) -> None:
        """Builds summary from multiple sections."""
        summaries = [
            {"section_id": 1, "summary": "First section summary. " * 50},
            {"section_id": 2, "summary": "Second section summary. " * 50},
            {"section_id": 3, "summary": "Third section summary. " * 50},
        ]
        result = build_rolling_summary(summaries)
        assert "Section 01:" in result
        assert "Section 02:" in result
        assert "Section 03:" in result

    def test_merge_continuity_updates(self) -> None:
        """Merges continuity updates correctly."""
        ledger = {"key1": "value1", "key2": "value2"}
        updates = {"key2": "new_value2", "key3": "value3"}
        result = merge_continuity_updates(ledger, updates)
        assert result["key1"] == "value1"
        assert result["key2"] == "new_value2"
        assert result["key3"] == "value3"

    def test_get_continuity_context(self) -> None:
        """Formats continuity ledger for prompt inclusion."""
        ledger = {"protagonist": "worker", "location": "factory"}
        result = get_continuity_context(ledger)
        assert "protagonist: worker" in result
        assert "location: factory" in result


class TestExecuteSectionStepSuccess:
    """Tests for successful section step execution."""

    def test_generates_and_persists_section(
        self,
        temp_run_dir_with_outline: Path,
        temp_context_dir: Path,
        temp_prompts_dir: Path,
        valid_section_content: str,
    ) -> None:
        """Successfully generates section and persists to artifacts and state."""
        provider = _MockLLMProvider(response_content=valid_section_content)
        logger = RunLogger(temp_run_dir_with_outline / "run.log")

        execute_section_step(
            run_dir=temp_run_dir_with_outline,
            context_dir=temp_context_dir,
            prompts_dir=temp_prompts_dir,
            llm_provider=provider,
            logger=logger,
            section_index=0,
            schema_base=SCHEMA_BASE,
        )

        # Check artifact was created
        artifact_path = temp_run_dir_with_outline / "artifacts" / "20_section_01.md"
        assert artifact_path.exists()

        content = artifact_path.read_text(encoding="utf-8")
        assert "---" in content
        assert "section_id: 1" in content
        assert "The Beginning" in content

        # Check state was updated
        with (temp_run_dir_with_outline / "state.json").open(encoding="utf-8") as f:
            state = json.load(f)
        assert len(state["sections"]) == 1
        assert state["sections"][0]["section_id"] == 1
        assert len(state["token_usage"]) == 1
        assert state["token_usage"][0]["step"] == "section_00"

        # Check LLM was called
        assert len(provider.calls) == 1
        assert provider.calls[0]["step"] == "section_00"

    def test_section_loop_multiple_sections(
        self,
        temp_run_dir_with_outline: Path,
        temp_context_dir: Path,
        temp_prompts_dir: Path,
        valid_section_content: str,
    ) -> None:
        """Successfully generates multiple sections in sequence."""
        provider = _MockLLMProvider(response_content=valid_section_content)
        logger = RunLogger(temp_run_dir_with_outline / "run.log")

        # Generate 3 sections
        for i in range(3):
            # Update section_id in response for each section
            content = valid_section_content.replace(
                "section_id: 1", f"section_id: {i + 1}"
            )
            provider.set_response(content)

            execute_section_step(
                run_dir=temp_run_dir_with_outline,
                context_dir=temp_context_dir,
                prompts_dir=temp_prompts_dir,
                llm_provider=provider,
                logger=logger,
                section_index=i,
                schema_base=SCHEMA_BASE,
            )

        # Check all artifacts were created
        for i in range(1, 4):
            artifact_path = (
                temp_run_dir_with_outline / "artifacts" / f"20_section_{i:02d}.md"
            )
            assert artifact_path.exists()

        # Check state has all sections
        with (temp_run_dir_with_outline / "state.json").open(encoding="utf-8") as f:
            state = json.load(f)
        assert len(state["sections"]) == 3

    def test_uses_rolling_summary(
        self,
        temp_run_dir_with_outline: Path,
        temp_context_dir: Path,
        temp_prompts_dir: Path,
        valid_section_content: str,
    ) -> None:
        """Uses rolling summary from previous sections."""
        # Add summaries to state
        with (temp_run_dir_with_outline / "state.json").open(
            "r", encoding="utf-8"
        ) as f:
            state = json.load(f)
        state["summaries"] = [
            {"section_id": 1, "summary": "Previous section summary. " * 50}
        ]
        with (temp_run_dir_with_outline / "state.json").open(
            "w", encoding="utf-8"
        ) as f:
            json.dump(state, f)

        provider = _MockLLMProvider(response_content=valid_section_content)
        logger = RunLogger(temp_run_dir_with_outline / "run.log")

        execute_section_step(
            run_dir=temp_run_dir_with_outline,
            context_dir=temp_context_dir,
            prompts_dir=temp_prompts_dir,
            llm_provider=provider,
            logger=logger,
            section_index=1,
            schema_base=SCHEMA_BASE,
        )

        # Check prompt included rolling summary
        call = provider.calls[0]
        prompt = call["prompt"]
        assert "Previous section summary" in prompt


class TestExecuteSummarizeStepSuccess:
    """Tests for successful summarize step execution."""

    def test_summarizes_section_and_updates_state(
        self,
        temp_run_dir_with_outline: Path,
        temp_prompts_dir: Path,
        valid_section_content: str,
        valid_summary_json: str,
    ) -> None:
        """Successfully summarizes section and updates continuity ledger."""
        # Create section artifact first
        artifact_path = temp_run_dir_with_outline / "artifacts" / "20_section_01.md"
        artifact_path.write_text(valid_section_content)

        provider = _MockLLMProvider(response_content=valid_summary_json)
        logger = RunLogger(temp_run_dir_with_outline / "run.log")

        execute_summarize_step(
            run_dir=temp_run_dir_with_outline,
            prompts_dir=temp_prompts_dir,
            llm_provider=provider,
            logger=logger,
            section_index=0,
            schema_base=SCHEMA_BASE,
        )

        # Check state was updated
        with (temp_run_dir_with_outline / "state.json").open(encoding="utf-8") as f:
            state = json.load(f)
        assert len(state["summaries"]) == 1
        assert state["summaries"][0]["section_id"] == 1
        assert "continuity_ledger" in state
        assert state["continuity_ledger"]["protagonist"] == "worker"
        assert len(state["token_usage"]) == 1
        assert state["token_usage"][0]["step"] == "summarize_00"

        # Check LLM was called
        assert len(provider.calls) == 1
        assert provider.calls[0]["step"] == "summarize_00"

    def test_merges_continuity_updates(
        self,
        temp_run_dir_with_outline: Path,
        temp_prompts_dir: Path,
        valid_section_content: str,
        valid_summary_json: str,
    ) -> None:
        """Merges continuity updates into existing ledger."""
        # Set up existing continuity ledger
        with (temp_run_dir_with_outline / "state.json").open(
            "r", encoding="utf-8"
        ) as f:
            state = json.load(f)
        state["continuity_ledger"] = {"existing_key": "existing_value"}
        with (temp_run_dir_with_outline / "state.json").open(
            "w", encoding="utf-8"
        ) as f:
            json.dump(state, f)

        # Create section artifact
        artifact_path = temp_run_dir_with_outline / "artifacts" / "20_section_01.md"
        artifact_path.write_text(valid_section_content)

        provider = _MockLLMProvider(response_content=valid_summary_json)
        logger = RunLogger(temp_run_dir_with_outline / "run.log")

        execute_summarize_step(
            run_dir=temp_run_dir_with_outline,
            prompts_dir=temp_prompts_dir,
            llm_provider=provider,
            logger=logger,
            section_index=0,
            schema_base=SCHEMA_BASE,
        )

        # Check continuity ledger was merged
        with (temp_run_dir_with_outline / "state.json").open(encoding="utf-8") as f:
            state = json.load(f)
        assert state["continuity_ledger"]["existing_key"] == "existing_value"
        assert state["continuity_ledger"]["protagonist"] == "worker"


class TestSectionLoopIntegration:
    """Integration tests for section loop with summarization."""

    def test_full_section_loop_with_summarization(
        self,
        temp_run_dir_with_outline: Path,
        temp_context_dir: Path,
        temp_prompts_dir: Path,
        valid_section_content: str,
        valid_summary_json: str,
    ) -> None:
        """Tests complete section generation and summarization loop."""
        provider = _MockLLMProvider()
        logger = RunLogger(temp_run_dir_with_outline / "run.log")

        # Generate and summarize 3 sections
        for i in range(3):
            # Generate section
            section_content = valid_section_content.replace(
                "section_id: 1", f"section_id: {i + 1}"
            )
            provider.set_response(section_content)
            provider.set_failure(False)

            execute_section_step(
                run_dir=temp_run_dir_with_outline,
                context_dir=temp_context_dir,
                prompts_dir=temp_prompts_dir,
                llm_provider=provider,
                logger=logger,
                section_index=i,
                schema_base=SCHEMA_BASE,
            )

            # Summarize section
            summary_json = valid_summary_json.replace(
                '"section_id": 1', f'"section_id": {i + 1}'
            )
            provider.set_response(summary_json)
            provider.set_failure(False)

            execute_summarize_step(
                run_dir=temp_run_dir_with_outline,
                prompts_dir=temp_prompts_dir,
                llm_provider=provider,
                logger=logger,
                section_index=i,
                schema_base=SCHEMA_BASE,
            )

        # Verify all artifacts exist
        for i in range(1, 4):
            artifact_path = (
                temp_run_dir_with_outline / "artifacts" / f"20_section_{i:02d}.md"
            )
            assert artifact_path.exists()

        # Verify state has all sections and summaries
        with (temp_run_dir_with_outline / "state.json").open(encoding="utf-8") as f:
            state = json.load(f)
        assert len(state["sections"]) == 3
        assert len(state["summaries"]) == 3
        assert len(state["token_usage"]) == 6  # 3 sections + 3 summaries


class TestSectionStepErrors:
    """Tests for section step error handling."""

    def test_fails_when_outline_missing(
        self,
        temp_run_dir_with_outline: Path,
        temp_context_dir: Path,
        temp_prompts_dir: Path,
    ) -> None:
        """Fails when outline is missing from state."""
        # Remove outline from state
        with (temp_run_dir_with_outline / "state.json").open(
            "r", encoding="utf-8"
        ) as f:
            state = json.load(f)
        state["outline"] = []
        with (temp_run_dir_with_outline / "state.json").open(
            "w", encoding="utf-8"
        ) as f:
            json.dump(state, f)

        provider = _MockLLMProvider()
        logger = RunLogger(temp_run_dir_with_outline / "run.log")

        with pytest.raises(SectionStepError, match="Outline not found"):
            execute_section_step(
                run_dir=temp_run_dir_with_outline,
                context_dir=temp_context_dir,
                prompts_dir=temp_prompts_dir,
                llm_provider=provider,
                logger=logger,
                section_index=0,
                schema_base=SCHEMA_BASE,
            )

    def test_fails_when_section_index_out_of_range(
        self,
        temp_run_dir_with_outline: Path,
        temp_context_dir: Path,
        temp_prompts_dir: Path,
    ) -> None:
        """Fails when section index is out of range."""
        provider = _MockLLMProvider()
        logger = RunLogger(temp_run_dir_with_outline / "run.log")

        with pytest.raises(SectionStepError, match="out of range"):
            execute_section_step(
                run_dir=temp_run_dir_with_outline,
                context_dir=temp_context_dir,
                prompts_dir=temp_prompts_dir,
                llm_provider=provider,
                logger=logger,
                section_index=10,  # Out of range
                schema_base=SCHEMA_BASE,
            )


class TestSummarizeStepErrors:
    """Tests for summarize step error handling."""

    def test_fails_when_section_artifact_missing(
        self,
        temp_run_dir_with_outline: Path,
        temp_prompts_dir: Path,
        valid_summary_json: str,
    ) -> None:
        """Fails when section artifact file is missing."""
        provider = _MockLLMProvider(response_content=valid_summary_json)
        logger = RunLogger(temp_run_dir_with_outline / "run.log")

        with pytest.raises(SummarizeStepError, match="Section artifact not found"):
            execute_summarize_step(
                run_dir=temp_run_dir_with_outline,
                prompts_dir=temp_prompts_dir,
                llm_provider=provider,
                logger=logger,
                section_index=0,
                schema_base=SCHEMA_BASE,
            )
