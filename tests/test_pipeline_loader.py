"""Tests for pipeline configuration loading and validation."""

import sys
from pathlib import Path

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from importlib import import_module

pipeline_module = import_module("llm_storytell.pipeline.loader")

load_pipeline_config = pipeline_module.load_pipeline_config
PipelineConfigError = pipeline_module.PipelineConfigError
PipelineConfig = pipeline_module.PipelineConfig
PipelineDefaults = pipeline_module.PipelineDefaults
PipelineStep = pipeline_module.PipelineStep
LLMConfig = pipeline_module.LLMConfig
LoopConfig = pipeline_module.LoopConfig
OutputConfig = pipeline_module.OutputConfig
StepInput = pipeline_module.StepInput
StepValidate = pipeline_module.StepValidate


class TestLoadPipelineConfig:
    """Tests for load_pipeline_config function."""

    def test_valid_minimal_config(self, tmp_path: Path) -> None:
        """Test loading a valid minimal pipeline configuration."""
        config_file = tmp_path / "pipeline.yaml"
        config_file.write_text(
            """
pipeline_version: 1
defaults:
  validators_base: src/llm_storytell/schemas
  artifacts_dir: artifacts
  prompt_base: prompts/apps/{app}
  shared_prompt_base: prompts/shared
  llm:
    provider: openai
    model: gpt-4
    temperature: 0.7
steps:
  - id: outline
    type: llm_step
    prompt_path: 10_outline.md
    outputs:
      - name: outline_json
        path: 10_outline.json
        kind: artifact
"""
        )

        config = load_pipeline_config(config_file)

        assert config.pipeline_version == 1
        assert config.description is None
        assert isinstance(config.defaults, PipelineDefaults)
        assert len(config.steps) == 1
        assert config.steps[0].id == "outline"

    def test_valid_full_config(self, tmp_path: Path) -> None:
        """Test loading a valid full-featured pipeline configuration."""
        config_file = tmp_path / "pipeline.yaml"
        config_file.write_text(
            """
pipeline_version: 1
description: Test pipeline configuration
defaults:
  validators_base: src/llm_storytell/schemas
  artifacts_dir: artifacts
  prompt_base: prompts/apps/{app}
  shared_prompt_base: prompts/shared
  llm:
    provider: openai
    model: gpt-4
    temperature: 0.7
    max_tokens: 2000
steps:
  - id: outline
    type: llm_step
    prompt_path: 10_outline.md
    inputs:
      - seed
      - context.lore_bible
    validate:
      schema: outline.schema.json
      schema_base: src/llm_storytell/schemas
    outputs:
      - name: outline_json
        path: 10_outline.json
        kind: artifact
      - name: outline_state
        state_key: outline
        kind: state
    llm:
      provider: openai
      model: gpt-4
      temperature: 0.4
  - id: section
    type: llm_step
    prompt_path: 20_section.md
    inputs:
      - loop.item
      - loop.index
    validate:
      schema: section.schema.json
    loop:
      over: state.outline
      per_item: true
      vars:
        index: "{index:02d}"
    outputs:
      - name: section_md
        path: "20_section_{index:02d}.md"
        kind: artifact
"""
        )

        config = load_pipeline_config(config_file)

        assert config.pipeline_version == 1
        assert config.description == "Test pipeline configuration"
        assert len(config.steps) == 2

        # Check first step
        outline_step = config.steps[0]
        assert outline_step.id == "outline"
        assert outline_step.type == "llm_step"
        assert len(outline_step.inputs) == 2
        assert outline_step.inputs[0].source == "seed"
        assert outline_step.validate is not None
        assert outline_step.validate.schema == "outline.schema.json"
        assert outline_step.llm is not None
        assert outline_step.llm.temperature == 0.4

        # Check second step
        section_step = config.steps[1]
        assert section_step.id == "section"
        assert section_step.loop is not None
        assert section_step.loop.over == "state.outline"
        assert section_step.loop.per_item is True
        assert section_step.loop.vars["index"] == "{index:02d}"

    def test_missing_file_raises_error(self, tmp_path: Path) -> None:
        """Test that missing config file raises FileNotFoundError."""
        config_file = tmp_path / "nonexistent.yaml"

        with pytest.raises(FileNotFoundError):
            load_pipeline_config(config_file)

    def test_invalid_yaml_raises_error(self, tmp_path: Path) -> None:
        """Test that invalid YAML raises PipelineConfigError."""
        config_file = tmp_path / "pipeline.yaml"
        config_file.write_text("invalid: yaml: [unclosed")

        with pytest.raises(PipelineConfigError) as exc_info:
            load_pipeline_config(config_file)

        assert "Invalid YAML" in str(exc_info.value)

    def test_missing_pipeline_version_raises_error(self, tmp_path: Path) -> None:
        """Test that missing pipeline_version raises error."""
        config_file = tmp_path / "pipeline.yaml"
        config_file.write_text(
            """
defaults:
  validators_base: src/llm_storytell/schemas
  artifacts_dir: artifacts
  prompt_base: prompts/apps/{app}
  shared_prompt_base: prompts/shared
  llm:
    provider: openai
    model: gpt-4
    temperature: 0.7
steps: []
"""
        )

        with pytest.raises(PipelineConfigError) as exc_info:
            load_pipeline_config(config_file)

        assert "pipeline_version" in str(exc_info.value)

    def test_missing_defaults_raises_error(self, tmp_path: Path) -> None:
        """Test that missing defaults raises error."""
        config_file = tmp_path / "pipeline.yaml"
        config_file.write_text(
            """
pipeline_version: 1
steps: []
"""
        )

        with pytest.raises(PipelineConfigError) as exc_info:
            load_pipeline_config(config_file)

        assert "defaults" in str(exc_info.value)

    def test_missing_steps_raises_error(self, tmp_path: Path) -> None:
        """Test that missing steps raises error."""
        config_file = tmp_path / "pipeline.yaml"
        config_file.write_text(
            """
pipeline_version: 1
defaults:
  validators_base: src/llm_storytell/schemas
  artifacts_dir: artifacts
  prompt_base: prompts/apps/{app}
  shared_prompt_base: prompts/shared
  llm:
    provider: openai
    model: gpt-4
    temperature: 0.7
"""
        )

        with pytest.raises(PipelineConfigError) as exc_info:
            load_pipeline_config(config_file)

        assert "steps" in str(exc_info.value)

    def test_empty_steps_raises_error(self, tmp_path: Path) -> None:
        """Test that empty steps list raises error."""
        config_file = tmp_path / "pipeline.yaml"
        config_file.write_text(
            """
pipeline_version: 1
defaults:
  validators_base: src/llm_storytell/schemas
  artifacts_dir: artifacts
  prompt_base: prompts/apps/{app}
  shared_prompt_base: prompts/shared
  llm:
    provider: openai
    model: gpt-4
    temperature: 0.7
steps: []
"""
        )

        with pytest.raises(PipelineConfigError) as exc_info:
            load_pipeline_config(config_file)

        assert "must not be empty" in str(exc_info.value)

    def test_missing_step_id_raises_error(self, tmp_path: Path) -> None:
        """Test that step without id raises error."""
        config_file = tmp_path / "pipeline.yaml"
        config_file.write_text(
            """
pipeline_version: 1
defaults:
  validators_base: src/llm_storytell/schemas
  artifacts_dir: artifacts
  prompt_base: prompts/apps/{app}
  shared_prompt_base: prompts/shared
  llm:
    provider: openai
    model: gpt-4
    temperature: 0.7
steps:
  - type: llm_step
    prompt_path: 10_outline.md
    outputs:
      - name: outline_json
        path: 10_outline.json
        kind: artifact
"""
        )

        with pytest.raises(PipelineConfigError) as exc_info:
            load_pipeline_config(config_file)

        assert "missing required field: id" in str(exc_info.value)

    def test_missing_step_prompt_path_raises_error(self, tmp_path: Path) -> None:
        """Test that step without prompt_path raises error."""
        config_file = tmp_path / "pipeline.yaml"
        config_file.write_text(
            """
pipeline_version: 1
defaults:
  validators_base: src/llm_storytell/schemas
  artifacts_dir: artifacts
  prompt_base: prompts/apps/{app}
  shared_prompt_base: prompts/shared
  llm:
    provider: openai
    model: gpt-4
    temperature: 0.7
steps:
  - id: outline
    type: llm_step
    outputs:
      - name: outline_json
        path: 10_outline.json
        kind: artifact
"""
        )

        with pytest.raises(PipelineConfigError) as exc_info:
            load_pipeline_config(config_file)

        assert "missing required field: prompt_path" in str(exc_info.value)

    def test_duplicate_step_ids_raises_error(self, tmp_path: Path) -> None:
        """Test that duplicate step IDs raise error."""
        config_file = tmp_path / "pipeline.yaml"
        config_file.write_text(
            """
pipeline_version: 1
defaults:
  validators_base: src/llm_storytell/schemas
  artifacts_dir: artifacts
  prompt_base: prompts/apps/{app}
  shared_prompt_base: prompts/shared
  llm:
    provider: openai
    model: gpt-4
    temperature: 0.7
steps:
  - id: outline
    type: llm_step
    prompt_path: 10_outline.md
    outputs:
      - name: outline_json
        path: 10_outline.json
        kind: artifact
  - id: outline
    type: llm_step
    prompt_path: 20_section.md
    outputs:
      - name: section_md
        path: 20_section.md
        kind: artifact
"""
        )

        with pytest.raises(PipelineConfigError) as exc_info:
            load_pipeline_config(config_file)

        assert "Duplicate step IDs" in str(exc_info.value)
        assert "outline" in str(exc_info.value)

    def test_step_without_outputs_raises_error(self, tmp_path: Path) -> None:
        """Test that step without outputs raises error."""
        config_file = tmp_path / "pipeline.yaml"
        config_file.write_text(
            """
pipeline_version: 1
defaults:
  validators_base: src/llm_storytell/schemas
  artifacts_dir: artifacts
  prompt_base: prompts/apps/{app}
  shared_prompt_base: prompts/shared
  llm:
    provider: openai
    model: gpt-4
    temperature: 0.7
steps:
  - id: outline
    type: llm_step
    prompt_path: 10_outline.md
"""
        )

        with pytest.raises(PipelineConfigError) as exc_info:
            load_pipeline_config(config_file)

        assert "has no outputs defined" in str(exc_info.value)

    def test_artifact_output_without_path_raises_error(self, tmp_path: Path) -> None:
        """Test that artifact output without path raises error."""
        config_file = tmp_path / "pipeline.yaml"
        config_file.write_text(
            """
pipeline_version: 1
defaults:
  validators_base: src/llm_storytell/schemas
  artifacts_dir: artifacts
  prompt_base: prompts/apps/{app}
  shared_prompt_base: prompts/shared
  llm:
    provider: openai
    model: gpt-4
    temperature: 0.7
steps:
  - id: outline
    type: llm_step
    prompt_path: 10_outline.md
    outputs:
      - name: outline_json
        kind: artifact
"""
        )

        with pytest.raises(PipelineConfigError) as exc_info:
            load_pipeline_config(config_file)

        assert "requires path" in str(exc_info.value)

    def test_state_output_without_state_key_raises_error(self, tmp_path: Path) -> None:
        """Test that state output without state_key raises error."""
        config_file = tmp_path / "pipeline.yaml"
        config_file.write_text(
            """
pipeline_version: 1
defaults:
  validators_base: src/llm_storytell/schemas
  artifacts_dir: artifacts
  prompt_base: prompts/apps/{app}
  shared_prompt_base: prompts/shared
  llm:
    provider: openai
    model: gpt-4
    temperature: 0.7
steps:
  - id: outline
    type: llm_step
    prompt_path: 10_outline.md
    outputs:
      - name: outline_state
        kind: state
"""
        )

        with pytest.raises(PipelineConfigError) as exc_info:
            load_pipeline_config(config_file)

        assert "requires state_key" in str(exc_info.value)

    def test_step_ordering_preserved(self, tmp_path: Path) -> None:
        """Test that step ordering is preserved from YAML."""
        config_file = tmp_path / "pipeline.yaml"
        config_file.write_text(
            """
pipeline_version: 1
defaults:
  validators_base: src/llm_storytell/schemas
  artifacts_dir: artifacts
  prompt_base: prompts/apps/{app}
  shared_prompt_base: prompts/shared
  llm:
    provider: openai
    model: gpt-4
    temperature: 0.7
steps:
  - id: first
    type: llm_step
    prompt_path: first.md
    outputs:
      - name: first_out
        path: first.json
        kind: artifact
  - id: second
    type: llm_step
    prompt_path: second.md
    outputs:
      - name: second_out
        path: second.json
        kind: artifact
  - id: third
    type: llm_step
    prompt_path: third.md
    outputs:
      - name: third_out
        path: third.json
        kind: artifact
"""
        )

        config = load_pipeline_config(config_file)

        assert len(config.steps) == 3
        assert config.steps[0].id == "first"
        assert config.steps[1].id == "second"
        assert config.steps[2].id == "third"

    def test_missing_defaults_llm_raises_error(self, tmp_path: Path) -> None:
        """Test that missing LLM in defaults raises error."""
        config_file = tmp_path / "pipeline.yaml"
        config_file.write_text(
            """
pipeline_version: 1
defaults:
  validators_base: src/llm_storytell/schemas
  artifacts_dir: artifacts
  prompt_base: prompts/apps/{app}
  shared_prompt_base: prompts/shared
steps:
  - id: outline
    type: llm_step
    prompt_path: 10_outline.md
    outputs:
      - name: outline_json
        path: 10_outline.json
        kind: artifact
"""
        )

        with pytest.raises(PipelineConfigError) as exc_info:
            load_pipeline_config(config_file)

        assert "llm" in str(exc_info.value)

    def test_missing_defaults_field_raises_error(self, tmp_path: Path) -> None:
        """Test that missing required defaults field raises error."""
        config_file = tmp_path / "pipeline.yaml"
        config_file.write_text(
            """
pipeline_version: 1
defaults:
  validators_base: src/llm_storytell/schemas
  artifacts_dir: artifacts
  prompt_base: prompts/apps/{app}
  llm:
    provider: openai
    model: gpt-4
    temperature: 0.7
steps:
  - id: outline
    type: llm_step
    prompt_path: 10_outline.md
    outputs:
      - name: outline_json
        path: 10_outline.json
        kind: artifact
"""
        )

        with pytest.raises(PipelineConfigError) as exc_info:
            load_pipeline_config(config_file)

        assert "shared_prompt_base" in str(exc_info.value)

    def test_non_dict_config_raises_error(self, tmp_path: Path) -> None:
        """Test that non-dict root raises error."""
        config_file = tmp_path / "pipeline.yaml"
        config_file.write_text("- not a dict")

        with pytest.raises(PipelineConfigError) as exc_info:
            load_pipeline_config(config_file)

        assert "must be a YAML mapping" in str(exc_info.value)

    def test_non_list_steps_raises_error(self, tmp_path: Path) -> None:
        """Test that non-list steps raises error."""
        config_file = tmp_path / "pipeline.yaml"
        config_file.write_text(
            """
pipeline_version: 1
defaults:
  validators_base: src/llm_storytell/schemas
  artifacts_dir: artifacts
  prompt_base: prompts/apps/{app}
  shared_prompt_base: prompts/shared
  llm:
    provider: openai
    model: gpt-4
    temperature: 0.7
steps: not a list
"""
        )

        with pytest.raises(PipelineConfigError) as exc_info:
            load_pipeline_config(config_file)

        assert "must be a list" in str(exc_info.value)

    def test_multiple_outputs_per_step(self, tmp_path: Path) -> None:
        """Test that steps can have multiple outputs."""
        config_file = tmp_path / "pipeline.yaml"
        config_file.write_text(
            """
pipeline_version: 1
defaults:
  validators_base: src/llm_storytell/schemas
  artifacts_dir: artifacts
  prompt_base: prompts/apps/{app}
  shared_prompt_base: prompts/shared
  llm:
    provider: openai
    model: gpt-4
    temperature: 0.7
steps:
  - id: critic
    type: llm_step
    prompt_path: 30_critic.md
    outputs:
      - name: final_script
        path: final_script.md
        kind: artifact
      - name: editor_report
        path: editor_report.json
        kind: artifact
"""
        )

        config = load_pipeline_config(config_file)

        assert len(config.steps) == 1
        assert len(config.steps[0].outputs) == 2
        assert config.steps[0].outputs[0].name == "final_script"
        assert config.steps[0].outputs[1].name == "editor_report"

    def test_loop_configuration_parsed(self, tmp_path: Path) -> None:
        """Test that loop configuration is properly parsed."""
        config_file = tmp_path / "pipeline.yaml"
        config_file.write_text(
            """
pipeline_version: 1
defaults:
  validators_base: src/llm_storytell/schemas
  artifacts_dir: artifacts
  prompt_base: prompts/apps/{app}
  shared_prompt_base: prompts/shared
  llm:
    provider: openai
    model: gpt-4
    temperature: 0.7
steps:
  - id: section
    type: llm_step
    prompt_path: 20_section.md
    loop:
      over: state.outline
      per_item: false
      vars:
        index: "{index:02d}"
        item_id: "{item.id}"
    outputs:
      - name: section_md
        path: "20_section_{index:02d}.md"
        kind: artifact
"""
        )

        config = load_pipeline_config(config_file)

        assert config.steps[0].loop is not None
        assert config.steps[0].loop.over == "state.outline"
        assert config.steps[0].loop.per_item is False
        assert config.steps[0].loop.vars["index"] == "{index:02d}"
        assert config.steps[0].loop.vars["item_id"] == "{item.id}"

    def test_string_input_parsed(self, tmp_path: Path) -> None:
        """Test that string inputs are parsed correctly."""
        config_file = tmp_path / "pipeline.yaml"
        config_file.write_text(
            """
pipeline_version: 1
defaults:
  validators_base: src/llm_storytell/schemas
  artifacts_dir: artifacts
  prompt_base: prompts/apps/{app}
  shared_prompt_base: prompts/shared
  llm:
    provider: openai
    model: gpt-4
    temperature: 0.7
steps:
  - id: outline
    type: llm_step
    prompt_path: 10_outline.md
    inputs:
      - seed
      - context.lore_bible
    outputs:
      - name: outline_json
        path: 10_outline.json
        kind: artifact
"""
        )

        config = load_pipeline_config(config_file)

        assert len(config.steps[0].inputs) == 2
        assert config.steps[0].inputs[0].source == "seed"
        assert config.steps[0].inputs[1].source == "context.lore_bible"
