"""Load and validate pipeline configuration from YAML."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class PipelineConfigError(Exception):
    """Raised when pipeline configuration is invalid."""

    pass


@dataclass(frozen=True)
class LLMConfig:
    """LLM provider configuration.

    Attributes:
        provider: LLM provider name (e.g., "openai").
        model: Model identifier.
        temperature: Sampling temperature.
        max_tokens: Maximum tokens for completion (optional).
    """

    provider: str
    model: str
    temperature: float
    max_tokens: int | None = None


@dataclass(frozen=True)
class StepInput:
    """Input declaration for a pipeline step.

    Attributes:
        source: Input source (e.g., "seed", "state.outline", "loop.item").
    """

    source: str


@dataclass(frozen=True)
class StepValidate:
    """Validation configuration for a pipeline step.

    Attributes:
        schema: Schema filename.
        schema_base: Base path for schema resolution (optional).
    """

    schema: str
    schema_base: str | None = None


@dataclass(frozen=True)
class LoopConfig:
    """Loop configuration for iterative steps.

    Attributes:
        over: What to iterate over (e.g., "state.outline", "artifacts.match(...)").
        per_item: Whether to run once per item.
        vars: Loop variable templates (e.g., {"index": "{index:02d}"}).
    """

    over: str
    per_item: bool = True
    vars: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class OutputConfig:
    """Output configuration for a pipeline step.

    Attributes:
        name: Output name identifier.
        path: Output file path (supports templating).
        kind: Output kind ("artifact", "state", "state_append", "state_merge", "state_set").
        state_key: State key for state outputs (optional).
    """

    name: str
    path: str | None = None
    kind: str = "artifact"
    state_key: str | None = None


@dataclass(frozen=True)
class PipelineStep:
    """A single pipeline step definition.

    Attributes:
        id: Unique step identifier.
        type: Step type (e.g., "llm_step").
        prompt_path: Path to prompt template (relative to app prompts directory).
        inputs: List of input sources.
        validate: Validation configuration (optional).
        outputs: List of output configurations.
        loop: Loop configuration (optional).
        llm: LLM configuration override (optional).
    """

    id: str
    type: str
    prompt_path: str
    inputs: list[StepInput] = field(default_factory=list)
    validate: StepValidate | None = None
    outputs: list[OutputConfig] = field(default_factory=list)
    loop: LoopConfig | None = None
    llm: LLMConfig | None = None


@dataclass(frozen=True)
class PipelineDefaults:
    """Default configuration values.

    Attributes:
        validators_base: Base path for validators.
        artifacts_dir: Artifacts directory name.
        prompt_base: Base path for app prompts (supports {app} placeholder).
        shared_prompt_base: Base path for shared prompts.
        llm: Default LLM configuration.
    """

    validators_base: str
    artifacts_dir: str
    prompt_base: str
    shared_prompt_base: str
    llm: LLMConfig


@dataclass(frozen=True)
class PipelineConfig:
    """Complete pipeline configuration.

    Attributes:
        pipeline_version: Pipeline configuration version.
        description: Optional description.
        defaults: Default configuration values.
        steps: Ordered list of pipeline steps.
    """

    pipeline_version: int
    description: str | None
    defaults: PipelineDefaults
    steps: list[PipelineStep]


def _parse_llm_config(data: dict[str, Any]) -> LLMConfig:
    """Parse LLM configuration from YAML data."""
    return LLMConfig(
        provider=data["provider"],
        model=data["model"],
        temperature=float(data.get("temperature", 0.7)),
        max_tokens=data.get("max_tokens"),
    )


def _parse_step_input(data: str | dict[str, Any]) -> StepInput:
    """Parse step input from YAML data."""
    if isinstance(data, str):
        return StepInput(source=data)
    return StepInput(source=data["source"])


def _parse_step_validate(data: dict[str, Any]) -> StepValidate:
    """Parse validation configuration from YAML data."""
    return StepValidate(
        schema=data["schema"],
        schema_base=data.get("schema_base"),
    )


def _parse_loop_config(data: dict[str, Any]) -> LoopConfig:
    """Parse loop configuration from YAML data."""
    return LoopConfig(
        over=data["over"],
        per_item=data.get("per_item", True),
        vars=data.get("vars", {}),
    )


def _parse_output_config(data: dict[str, Any]) -> OutputConfig:
    """Parse output configuration from YAML data."""
    return OutputConfig(
        name=data["name"],
        path=data.get("path"),
        kind=data.get("kind", "artifact"),
        state_key=data.get("state_key"),
    )


def _parse_pipeline_step(data: dict[str, Any]) -> PipelineStep:
    """Parse a single pipeline step from YAML data."""
    # Validate required fields
    if "id" not in data:
        raise PipelineConfigError("Step missing required field: id")
    if "type" not in data:
        raise PipelineConfigError(f"Step '{data['id']}' missing required field: type")
    if "prompt_path" not in data:
        raise PipelineConfigError(
            f"Step '{data['id']}' missing required field: prompt_path"
        )

    # Parse inputs
    inputs = []
    if "inputs" in data:
        for input_data in data["inputs"]:
            inputs.append(_parse_step_input(input_data))

    # Parse validate
    validate = None
    if "validate" in data:
        validate = _parse_step_validate(data["validate"])

    # Parse outputs
    outputs = []
    if "outputs" in data:
        for output_data in data["outputs"]:
            outputs.append(_parse_output_config(output_data))

    # Parse loop
    loop = None
    if "loop" in data:
        loop = _parse_loop_config(data["loop"])

    # Parse LLM override
    llm = None
    if "llm" in data:
        llm = _parse_llm_config(data["llm"])

    return PipelineStep(
        id=data["id"],
        type=data["type"],
        prompt_path=data["prompt_path"],
        inputs=inputs,
        validate=validate,
        outputs=outputs,
        loop=loop,
        llm=llm,
    )


def _parse_defaults(data: dict[str, Any]) -> PipelineDefaults:
    """Parse defaults configuration from YAML data."""
    required_fields = [
        "validators_base",
        "artifacts_dir",
        "prompt_base",
        "shared_prompt_base",
    ]
    for field_name in required_fields:
        if field_name not in data:
            raise PipelineConfigError(f"Defaults missing required field: {field_name}")

    if "llm" not in data:
        raise PipelineConfigError("Defaults missing required field: llm")

    return PipelineDefaults(
        validators_base=data["validators_base"],
        artifacts_dir=data["artifacts_dir"],
        prompt_base=data["prompt_base"],
        shared_prompt_base=data["shared_prompt_base"],
        llm=_parse_llm_config(data["llm"]),
    )


def _validate_pipeline_config(config: PipelineConfig) -> None:
    """Validate pipeline configuration for consistency."""
    # Check for duplicate step IDs
    step_ids = [step.id for step in config.steps]
    if len(step_ids) != len(set(step_ids)):
        duplicates = [sid for sid in step_ids if step_ids.count(sid) > 1]
        raise PipelineConfigError(
            f"Duplicate step IDs found: {', '.join(set(duplicates))}"
        )

    # Validate loop references
    for step in config.steps:
        if step.loop:
            # Basic validation - loop.over can reference state, artifacts, etc.
            # We can't fully validate these until runtime, but we can check format
            if not step.loop.over or not isinstance(step.loop.over, str):
                raise PipelineConfigError(
                    f"Step '{step.id}' has invalid loop.over: {step.loop.over}"
                )

    # Validate outputs
    for step in config.steps:
        if not step.outputs:
            raise PipelineConfigError(f"Step '{step.id}' has no outputs defined")
        for output in step.outputs:
            if output.kind == "artifact" and not output.path:
                raise PipelineConfigError(
                    f"Step '{step.id}' output '{output.name}' (kind=artifact) "
                    "requires path"
                )
            if output.kind in ("state", "state_append", "state_merge", "state_set"):
                if not output.state_key:
                    raise PipelineConfigError(
                        f"Step '{step.id}' output '{output.name}' "
                        f"(kind={output.kind}) requires state_key"
                    )


def load_pipeline_config(config_path: Path) -> PipelineConfig:
    """Load and validate pipeline configuration from YAML file.

    Args:
        config_path: Path to pipeline.yaml file.

    Returns:
        Validated PipelineConfig.

    Raises:
        PipelineConfigError: If configuration is invalid or file cannot be read.
        FileNotFoundError: If config_path does not exist.
    """
    if not config_path.exists():
        raise FileNotFoundError(f"Pipeline config not found: {config_path}")

    try:
        with config_path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise PipelineConfigError(f"Invalid YAML in {config_path}: {e}") from e
    except OSError as e:
        raise PipelineConfigError(f"Error reading {config_path}: {e}") from e

    if not isinstance(data, dict):
        raise PipelineConfigError("Pipeline config must be a YAML mapping")

    # Parse pipeline_version (required)
    if "pipeline_version" not in data:
        raise PipelineConfigError(
            "Pipeline config missing required field: pipeline_version"
        )
    pipeline_version = int(data["pipeline_version"])

    # Parse description (optional)
    description = data.get("description")

    # Parse defaults (required)
    if "defaults" not in data:
        raise PipelineConfigError("Pipeline config missing required field: defaults")
    defaults = _parse_defaults(data["defaults"])

    # Parse steps (required, non-empty)
    if "steps" not in data:
        raise PipelineConfigError("Pipeline config missing required field: steps")
    if not isinstance(data["steps"], list):
        raise PipelineConfigError("Pipeline config 'steps' must be a list")
    if len(data["steps"]) == 0:
        raise PipelineConfigError("Pipeline config 'steps' must not be empty")

    steps = []
    for step_data in data["steps"]:
        steps.append(_parse_pipeline_step(step_data))

    config = PipelineConfig(
        pipeline_version=pipeline_version,
        description=description,
        defaults=defaults,
        steps=steps,
    )

    _validate_pipeline_config(config)

    return config
