"""Tests for critic step."""

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
critic_module = import_module("llm-storytell.steps.critic")
llm_module = import_module("llm-storytell.llm")
logging_module = import_module("llm-storytell.logging")

execute_critic_step = critic_module.execute_critic_step
CriticStepError = critic_module.CriticStepError
LLMResult = llm_module.LLMResult
LLMProvider = llm_module.LLMProvider
LLMProviderError = llm_module.LLMProviderError
RunLogger = logging_module.RunLogger


class _MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing."""

    def __init__(self, response_content: str | None = None) -> None:
        super().__init__(provider_name="mock")
        self._response_content = (
            response_content or '{"final_script": "", "editor_report": {}}'
        )
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
def temp_run_dir_with_sections(tmp_path: Path) -> Path:
    """Create a temporary run directory with sections in artifacts."""
    run_dir = tmp_path / "run-test-001"
    run_dir.mkdir()
    artifacts_dir = run_dir / "artifacts"
    artifacts_dir.mkdir()

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
        "beats": 2,
    }
    with (run_dir / "inputs.json").open("w", encoding="utf-8") as f:
        json.dump(inputs, f)

    # Create run.log
    (run_dir / "run.log").touch()

    # Create section artifacts
    section1_content = """---
section_id: 1
local_summary: First section summary
new_entities: []
new_locations: []
unresolved_threads: []
---

## Section One

This is the first section content.
"""
    (artifacts_dir / "20_section_01.md").write_text(section1_content)

    section2_content = """---
section_id: 2
local_summary: Second section summary
new_entities: []
new_locations: []
unresolved_threads: []
---

## Section Two

This is the second section content.
"""
    (artifacts_dir / "20_section_02.md").write_text(section2_content)

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
    """Create a temporary prompts directory with critic template."""
    prompts_dir = tmp_path / "prompts" / "apps" / "grim-narrator"
    prompts_dir.mkdir(parents=True)

    # Create critic prompt template
    template_content = """Review and correct the full draft:

{full_draft}

Lore: {lore_bible}
Style: {style_rules}
Outline: {outline}
Location: {location_context}
Characters: {character_context}

Return JSON with final_script and editor_report.
"""
    (prompts_dir / "30_critic.md").write_text(template_content)

    return prompts_dir


@pytest.fixture
def valid_critic_response() -> str:
    """Return valid critic response JSON."""
    response = {
        "final_script": "# Final Script\n\nThis is the corrected final script.\n",
        "editor_report": {
            "issues_found": [
                "Minor tense inconsistency in section 1",
                "Overused phrase 'the worker' in section 2",
            ],
            "changes_applied": [
                "Fixed tense consistency throughout",
                "Replaced repetitive phrasing",
            ],
        },
    }
    return json.dumps(response)


class TestExecuteCriticStepSuccess:
    """Tests for successful critic step execution."""

    def test_generates_final_script_and_report(
        self,
        temp_run_dir_with_sections: Path,
        temp_context_dir: Path,
        temp_prompts_dir: Path,
        valid_critic_response: str,
    ) -> None:
        """Successfully generates final script and editor report."""
        provider = _MockLLMProvider(response_content=valid_critic_response)
        logger = RunLogger(temp_run_dir_with_sections / "run.log")

        execute_critic_step(
            run_dir=temp_run_dir_with_sections,
            context_dir=temp_context_dir,
            prompts_dir=temp_prompts_dir,
            llm_provider=provider,
            logger=logger,
            schema_base=SCHEMA_BASE,
        )

        # Check artifacts were created
        final_script_path = temp_run_dir_with_sections / "artifacts" / "final_script.md"
        assert final_script_path.exists()
        assert "# Final Script" in final_script_path.read_text()

        editor_report_path = (
            temp_run_dir_with_sections / "artifacts" / "editor_report.json"
        )
        assert editor_report_path.exists()
        with editor_report_path.open(encoding="utf-8") as f:
            report = json.load(f)
        assert "issues_found" in report
        assert "changes_applied" in report

        # Check state was updated
        with (temp_run_dir_with_sections / "state.json").open(encoding="utf-8") as f:
            state = json.load(f)
        # Paths should use forward slashes (normalized)
        assert state["final_script_path"] == "artifacts/final_script.md"
        assert state["editor_report_path"] == "artifacts/editor_report.json"
        assert len(state["token_usage"]) == 1
        assert state["token_usage"][0]["step"] == "critic"

        # Check LLM was called
        assert len(provider.calls) == 1
        assert provider.calls[0]["step"] == "critic"

    def test_loads_all_sections_and_combines(
        self,
        temp_run_dir_with_sections: Path,
        temp_context_dir: Path,
        temp_prompts_dir: Path,
        valid_critic_response: str,
    ) -> None:
        """Loads all sections and combines them into full draft."""
        provider = _MockLLMProvider(response_content=valid_critic_response)
        logger = RunLogger(temp_run_dir_with_sections / "run.log")

        execute_critic_step(
            run_dir=temp_run_dir_with_sections,
            context_dir=temp_context_dir,
            prompts_dir=temp_prompts_dir,
            llm_provider=provider,
            logger=logger,
            schema_base=SCHEMA_BASE,
        )

        # Check prompt included both sections
        call = provider.calls[0]
        prompt = call["prompt"]
        assert "Section One" in prompt
        assert "Section Two" in prompt
        assert "This is the first section content" in prompt
        assert "This is the second section content" in prompt

    def test_loads_all_context_files(
        self,
        temp_run_dir_with_sections: Path,
        temp_context_dir: Path,
        temp_prompts_dir: Path,
        valid_critic_response: str,
    ) -> None:
        """Loads all required context files for prompt rendering."""
        provider = _MockLLMProvider(response_content=valid_critic_response)
        logger = RunLogger(temp_run_dir_with_sections / "run.log")

        execute_critic_step(
            run_dir=temp_run_dir_with_sections,
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

    def test_strips_frontmatter_from_sections(
        self,
        temp_run_dir_with_sections: Path,
        temp_context_dir: Path,
        temp_prompts_dir: Path,
        valid_critic_response: str,
    ) -> None:
        """Strips frontmatter from sections before combining."""
        provider = _MockLLMProvider(response_content=valid_critic_response)
        logger = RunLogger(temp_run_dir_with_sections / "run.log")

        execute_critic_step(
            run_dir=temp_run_dir_with_sections,
            context_dir=temp_context_dir,
            prompts_dir=temp_prompts_dir,
            llm_provider=provider,
            logger=logger,
            schema_base=SCHEMA_BASE,
        )

        # Check prompt does not include frontmatter
        call = provider.calls[0]
        prompt = call["prompt"]
        assert "section_id: 1" not in prompt
        assert "local_summary" not in prompt
        assert "---" not in prompt or prompt.count("---") == 0  # No frontmatter markers

    def test_handles_single_section(
        self,
        tmp_path: Path,
        temp_context_dir: Path,
        temp_prompts_dir: Path,
        valid_critic_response: str,
    ) -> None:
        """Handles single section correctly."""
        run_dir = tmp_path / "run-test-single"
        run_dir.mkdir()
        artifacts_dir = run_dir / "artifacts"
        artifacts_dir.mkdir()

        # Create state with single section outline
        state = {
            "app": "grim-narrator",
            "seed": "A single section story.",
            "selected_context": {},
            "outline": [
                {"beat_id": 1, "title": "Only", "summary": "The only section."}
            ],
            "sections": [],
            "summaries": [],
            "continuity_ledger": {},
            "token_usage": [],
        }
        with (run_dir / "state.json").open("w", encoding="utf-8") as f:
            json.dump(state, f)

        # Create single section artifact
        section_content = """---
section_id: 1
local_summary: Only section
new_entities: []
new_locations: []
unresolved_threads: []
---

## The Only Section

This is the only section.
"""
        (artifacts_dir / "20_section_01.md").write_text(section_content)

        # Create run.log
        (run_dir / "run.log").touch()

        provider = _MockLLMProvider(response_content=valid_critic_response)
        logger = RunLogger(run_dir / "run.log")

        execute_critic_step(
            run_dir=run_dir,
            context_dir=temp_context_dir,
            prompts_dir=temp_prompts_dir,
            llm_provider=provider,
            logger=logger,
            schema_base=SCHEMA_BASE,
        )

        # Should succeed
        assert (run_dir / "artifacts" / "final_script.md").exists()


class TestExecuteCriticStepErrors:
    """Tests for error handling in critic step."""

    def test_fails_on_missing_state_file(
        self,
        temp_run_dir_with_sections: Path,
        temp_context_dir: Path,
        temp_prompts_dir: Path,
    ) -> None:
        """Fails if state.json is missing."""
        (temp_run_dir_with_sections / "state.json").unlink()

        provider = _MockLLMProvider()
        logger = RunLogger(temp_run_dir_with_sections / "run.log")

        with pytest.raises(CriticStepError) as exc_info:
            execute_critic_step(
                run_dir=temp_run_dir_with_sections,
                context_dir=temp_context_dir,
                prompts_dir=temp_prompts_dir,
                llm_provider=provider,
                logger=logger,
            )

        assert "State file not found" in str(exc_info.value)

    def test_fails_on_missing_outline(
        self,
        temp_run_dir_with_sections: Path,
        temp_context_dir: Path,
        temp_prompts_dir: Path,
    ) -> None:
        """Fails if outline is missing from state."""
        with (temp_run_dir_with_sections / "state.json").open(
            "r", encoding="utf-8"
        ) as f:
            state = json.load(f)
        state["outline"] = []
        with (temp_run_dir_with_sections / "state.json").open(
            "w", encoding="utf-8"
        ) as f:
            json.dump(state, f)

        provider = _MockLLMProvider()
        logger = RunLogger(temp_run_dir_with_sections / "run.log")

        with pytest.raises(CriticStepError) as exc_info:
            execute_critic_step(
                run_dir=temp_run_dir_with_sections,
                context_dir=temp_context_dir,
                prompts_dir=temp_prompts_dir,
                llm_provider=provider,
                logger=logger,
            )

        assert "Outline not found" in str(exc_info.value)

    def test_fails_on_missing_sections(
        self,
        tmp_path: Path,
        temp_context_dir: Path,
        temp_prompts_dir: Path,
    ) -> None:
        """Fails if no section artifacts exist."""
        run_dir = tmp_path / "run-test-no-sections"
        run_dir.mkdir()
        (run_dir / "artifacts").mkdir()

        state = {
            "app": "grim-narrator",
            "seed": "Test",
            "selected_context": {},
            "outline": [{"beat_id": 1, "title": "One", "summary": "First"}],
            "sections": [],
            "summaries": [],
            "continuity_ledger": {},
            "token_usage": [],
        }
        with (run_dir / "state.json").open("w", encoding="utf-8") as f:
            json.dump(state, f)
        (run_dir / "run.log").touch()

        provider = _MockLLMProvider()
        logger = RunLogger(run_dir / "run.log")

        with pytest.raises(CriticStepError) as exc_info:
            execute_critic_step(
                run_dir=run_dir,
                context_dir=temp_context_dir,
                prompts_dir=temp_prompts_dir,
                llm_provider=provider,
                logger=logger,
            )

        assert "No section artifacts found" in str(exc_info.value)
        assert "Pipeline step 'section'" in str(exc_info.value)

    def test_fails_on_missing_section_file(
        self,
        temp_run_dir_with_sections: Path,
        temp_context_dir: Path,
        temp_prompts_dir: Path,
    ) -> None:
        """Fails if a specific section file is missing."""
        # Delete one section file
        (temp_run_dir_with_sections / "artifacts" / "20_section_02.md").unlink()

        # Use valid response in case we get past section loading (shouldn't happen)
        valid_response = json.dumps(
            {
                "final_script": "test",
                "editor_report": {"issues_found": [], "changes_applied": []},
            }
        )
        provider = _MockLLMProvider(response_content=valid_response)
        logger = RunLogger(temp_run_dir_with_sections / "run.log")

        with pytest.raises(CriticStepError) as exc_info:
            execute_critic_step(
                run_dir=temp_run_dir_with_sections,
                context_dir=temp_context_dir,
                prompts_dir=temp_prompts_dir,
                llm_provider=provider,
                logger=logger,
            )

        assert "Section numbering has gaps" in str(exc_info.value)
        assert "Missing section indices: 2" in str(exc_info.value)

    def test_fails_on_gaps_in_section_numbering(
        self,
        tmp_path: Path,
        temp_context_dir: Path,
        temp_prompts_dir: Path,
    ) -> None:
        """Fails if section numbering has gaps."""
        run_dir = tmp_path / "run-test-gaps"
        run_dir.mkdir()
        artifacts_dir = run_dir / "artifacts"
        artifacts_dir.mkdir()

        state = {
            "app": "grim-narrator",
            "seed": "Test",
            "selected_context": {},
            "outline": [
                {"beat_id": 1, "title": "One", "summary": "First"},
                {"beat_id": 2, "title": "Two", "summary": "Second"},
                {"beat_id": 3, "title": "Three", "summary": "Third"},
            ],
            "sections": [],
            "summaries": [],
            "continuity_ledger": {},
            "token_usage": [],
        }
        with (run_dir / "state.json").open("w", encoding="utf-8") as f:
            json.dump(state, f)
        (run_dir / "run.log").touch()

        # Create sections 01 and 03, missing 02
        section1 = """---
section_id: 1
local_summary: First
new_entities: []
new_locations: []
unresolved_threads: []
---

## One

Content one.
"""
        (artifacts_dir / "20_section_01.md").write_text(section1)

        section3 = """---
section_id: 3
local_summary: Third
new_entities: []
new_locations: []
unresolved_threads: []
---

## Three

Content three.
"""
        (artifacts_dir / "20_section_03.md").write_text(section3)

        provider = _MockLLMProvider()
        logger = RunLogger(run_dir / "run.log")

        with pytest.raises(CriticStepError) as exc_info:
            execute_critic_step(
                run_dir=run_dir,
                context_dir=temp_context_dir,
                prompts_dir=temp_prompts_dir,
                llm_provider=provider,
                logger=logger,
            )

        assert "Section numbering has gaps" in str(exc_info.value)
        assert "Missing section indices: 2" in str(exc_info.value)

    def test_fails_on_malformed_frontmatter(
        self,
        tmp_path: Path,
        temp_context_dir: Path,
        temp_prompts_dir: Path,
    ) -> None:
        """Fails if section has malformed frontmatter."""
        run_dir = tmp_path / "run-test-malformed"
        run_dir.mkdir()
        artifacts_dir = run_dir / "artifacts"
        artifacts_dir.mkdir()

        state = {
            "app": "grim-narrator",
            "seed": "Test",
            "selected_context": {},
            "outline": [{"beat_id": 1, "title": "One", "summary": "First"}],
            "sections": [],
            "summaries": [],
            "continuity_ledger": {},
            "token_usage": [],
        }
        with (run_dir / "state.json").open("w", encoding="utf-8") as f:
            json.dump(state, f)
        (run_dir / "run.log").touch()

        # Create section with malformed frontmatter
        section_content = """---
section_id: 1
invalid: yaml: : : :
---

## One

Content.
"""
        (artifacts_dir / "20_section_01.md").write_text(section_content)

        provider = _MockLLMProvider()
        logger = RunLogger(run_dir / "run.log")

        with pytest.raises(CriticStepError) as exc_info:
            execute_critic_step(
                run_dir=run_dir,
                context_dir=temp_context_dir,
                prompts_dir=temp_prompts_dir,
                llm_provider=provider,
                logger=logger,
            )

        assert "Invalid YAML in frontmatter" in str(exc_info.value)

    def test_fails_on_missing_frontmatter(
        self,
        tmp_path: Path,
        temp_context_dir: Path,
        temp_prompts_dir: Path,
    ) -> None:
        """Fails if section has no frontmatter."""
        run_dir = tmp_path / "run-test-no-frontmatter"
        run_dir.mkdir()
        artifacts_dir = run_dir / "artifacts"
        artifacts_dir.mkdir()

        state = {
            "app": "grim-narrator",
            "seed": "Test",
            "selected_context": {},
            "outline": [{"beat_id": 1, "title": "One", "summary": "First"}],
            "sections": [],
            "summaries": [],
            "continuity_ledger": {},
            "token_usage": [],
        }
        with (run_dir / "state.json").open("w", encoding="utf-8") as f:
            json.dump(state, f)
        (run_dir / "run.log").touch()

        # Create section without frontmatter
        section_content = """## One

Content without frontmatter.
"""
        (artifacts_dir / "20_section_01.md").write_text(section_content)

        provider = _MockLLMProvider()
        logger = RunLogger(run_dir / "run.log")

        with pytest.raises(CriticStepError) as exc_info:
            execute_critic_step(
                run_dir=run_dir,
                context_dir=temp_context_dir,
                prompts_dir=temp_prompts_dir,
                llm_provider=provider,
                logger=logger,
            )

        assert "missing valid YAML frontmatter" in str(exc_info.value)

    def test_fails_on_missing_prompt_template(
        self,
        temp_run_dir_with_sections: Path,
        temp_context_dir: Path,
        temp_prompts_dir: Path,
    ) -> None:
        """Fails if prompt template is missing."""
        (temp_prompts_dir / "30_critic.md").unlink()

        provider = _MockLLMProvider()
        logger = RunLogger(temp_run_dir_with_sections / "run.log")

        with pytest.raises(CriticStepError) as exc_info:
            execute_critic_step(
                run_dir=temp_run_dir_with_sections,
                context_dir=temp_context_dir,
                prompts_dir=temp_prompts_dir,
                llm_provider=provider,
                logger=logger,
            )

        assert "Prompt template not found" in str(exc_info.value)

    def test_fails_on_llm_provider_error(
        self,
        temp_run_dir_with_sections: Path,
        temp_context_dir: Path,
        temp_prompts_dir: Path,
    ) -> None:
        """Fails if LLM provider raises an error."""
        provider = _MockLLMProvider()
        provider.set_failure(should_fail=True)

        logger = RunLogger(temp_run_dir_with_sections / "run.log")

        with pytest.raises(CriticStepError) as exc_info:
            execute_critic_step(
                run_dir=temp_run_dir_with_sections,
                context_dir=temp_context_dir,
                prompts_dir=temp_prompts_dir,
                llm_provider=provider,
                logger=logger,
            )

        assert "LLM provider error" in str(exc_info.value)

    def test_fails_on_invalid_json_response(
        self,
        temp_run_dir_with_sections: Path,
        temp_context_dir: Path,
        temp_prompts_dir: Path,
    ) -> None:
        """Fails if LLM response is not valid JSON."""
        provider = _MockLLMProvider(response_content="This is not JSON")

        logger = RunLogger(temp_run_dir_with_sections / "run.log")

        with pytest.raises(CriticStepError) as exc_info:
            execute_critic_step(
                run_dir=temp_run_dir_with_sections,
                context_dir=temp_context_dir,
                prompts_dir=temp_prompts_dir,
                llm_provider=provider,
                logger=logger,
            )

        assert "Invalid JSON in LLM response" in str(exc_info.value)

    def test_fails_on_missing_required_keys(
        self,
        temp_run_dir_with_sections: Path,
        temp_context_dir: Path,
        temp_prompts_dir: Path,
    ) -> None:
        """Fails if LLM response is missing required keys."""
        invalid_response = json.dumps({"final_script": "test"})  # Missing editor_report
        provider = _MockLLMProvider(response_content=invalid_response)

        logger = RunLogger(temp_run_dir_with_sections / "run.log")

        with pytest.raises(CriticStepError) as exc_info:
            execute_critic_step(
                run_dir=temp_run_dir_with_sections,
                context_dir=temp_context_dir,
                prompts_dir=temp_prompts_dir,
                llm_provider=provider,
                logger=logger,
            )

        assert "missing required keys" in str(exc_info.value)
        assert "editor_report" in str(exc_info.value)

    def test_fails_on_extra_keys(
        self,
        temp_run_dir_with_sections: Path,
        temp_context_dir: Path,
        temp_prompts_dir: Path,
    ) -> None:
        """Fails if LLM response contains extra keys."""
        invalid_response = json.dumps(
            {
                "final_script": "test",
                "editor_report": {},
                "extra_key": "not allowed",
            }
        )
        provider = _MockLLMProvider(response_content=invalid_response)

        logger = RunLogger(temp_run_dir_with_sections / "run.log")

        with pytest.raises(CriticStepError) as exc_info:
            execute_critic_step(
                run_dir=temp_run_dir_with_sections,
                context_dir=temp_context_dir,
                prompts_dir=temp_prompts_dir,
                llm_provider=provider,
                logger=logger,
            )

        assert "contains extra keys" in str(exc_info.value)
        assert "extra_key" in str(exc_info.value)

    def test_fails_on_wrong_type_for_final_script(
        self,
        temp_run_dir_with_sections: Path,
        temp_context_dir: Path,
        temp_prompts_dir: Path,
    ) -> None:
        """Fails if final_script is not a string."""
        invalid_response = json.dumps(
            {
                "final_script": 123,  # Should be string
                "editor_report": {},
            }
        )
        provider = _MockLLMProvider(response_content=invalid_response)

        logger = RunLogger(temp_run_dir_with_sections / "run.log")

        with pytest.raises(CriticStepError) as exc_info:
            execute_critic_step(
                run_dir=temp_run_dir_with_sections,
                context_dir=temp_context_dir,
                prompts_dir=temp_prompts_dir,
                llm_provider=provider,
                logger=logger,
            )

        assert "final_script must be a string" in str(exc_info.value)

    def test_fails_on_wrong_type_for_editor_report(
        self,
        temp_run_dir_with_sections: Path,
        temp_context_dir: Path,
        temp_prompts_dir: Path,
    ) -> None:
        """Fails if editor_report is not a dict."""
        invalid_response = json.dumps(
            {
                "final_script": "test",
                "editor_report": "not a dict",  # Should be dict
            }
        )
        provider = _MockLLMProvider(response_content=invalid_response)

        logger = RunLogger(temp_run_dir_with_sections / "run.log")

        with pytest.raises(CriticStepError) as exc_info:
            execute_critic_step(
                run_dir=temp_run_dir_with_sections,
                context_dir=temp_context_dir,
                prompts_dir=temp_prompts_dir,
                llm_provider=provider,
                logger=logger,
            )

        assert "editor_report must be a dictionary" in str(exc_info.value)

    def test_fails_on_schema_validation_error(
        self,
        temp_run_dir_with_sections: Path,
        temp_context_dir: Path,
        temp_prompts_dir: Path,
    ) -> None:
        """Fails if editor_report doesn't match schema."""
        invalid_response = json.dumps(
            {
                "final_script": "test",
                "editor_report": {
                    "issues_found": "should be array",  # Should be array
                    "changes_applied": [],
                },
            }
        )
        provider = _MockLLMProvider(response_content=invalid_response)

        logger = RunLogger(temp_run_dir_with_sections / "run.log")

        with pytest.raises(CriticStepError) as exc_info:
            execute_critic_step(
                run_dir=temp_run_dir_with_sections,
                context_dir=temp_context_dir,
                prompts_dir=temp_prompts_dir,
                llm_provider=provider,
                logger=logger,
                schema_base=SCHEMA_BASE,
            )

        assert "Schema validation failed" in str(exc_info.value)

    def test_logs_stage_start_and_end(
        self,
        temp_run_dir_with_sections: Path,
        temp_context_dir: Path,
        temp_prompts_dir: Path,
        valid_critic_response: str,
    ) -> None:
        """Logs stage start and end correctly."""
        provider = _MockLLMProvider(response_content=valid_critic_response)
        logger = RunLogger(temp_run_dir_with_sections / "run.log")

        execute_critic_step(
            run_dir=temp_run_dir_with_sections,
            context_dir=temp_context_dir,
            prompts_dir=temp_prompts_dir,
            llm_provider=provider,
            logger=logger,
            schema_base=SCHEMA_BASE,
        )

        log_content = (temp_run_dir_with_sections / "run.log").read_text()
        assert "Stage started: critic" in log_content
        assert "Stage ended: critic (success)" in log_content

    def test_logs_failure_on_error(
        self,
        temp_run_dir_with_sections: Path,
        temp_context_dir: Path,
        temp_prompts_dir: Path,
    ) -> None:
        """Logs failure when step errors."""
        provider = _MockLLMProvider()
        provider.set_failure(should_fail=True)

        logger = RunLogger(temp_run_dir_with_sections / "run.log")

        with pytest.raises(CriticStepError):
            execute_critic_step(
                run_dir=temp_run_dir_with_sections,
                context_dir=temp_context_dir,
                prompts_dir=temp_prompts_dir,
                llm_provider=provider,
                logger=logger,
            )

        log_content = (temp_run_dir_with_sections / "run.log").read_text()
        assert "Stage started: critic" in log_content
        assert "Stage ended: critic (failure)" in log_content
