"""Schema validation utilities for structured LLM outputs."""

import json
from pathlib import Path

import jsonschema

from llm_storytell.logging import RunLogger


class SchemaValidationError(Exception):
    """Raised when JSON data fails schema validation."""

    pass


def validate_json_schema(
    data: dict | list,
    schema_path: Path,
    logger: RunLogger | None = None,
) -> None:
    """Validate JSON data against a JSON schema.

    Args:
        data: The JSON data to validate (dict or list).
        schema_path: Path to the JSON schema file.
        logger: Optional logger for validation errors.

    Raises:
        SchemaValidationError: If validation fails or schema cannot be loaded.
        FileNotFoundError: If schema file does not exist.
    """
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    try:
        with schema_path.open(encoding="utf-8") as f:
            schema = json.load(f)
    except json.JSONDecodeError as e:
        msg = f"Invalid JSON in schema file {schema_path}: {e}"
        if logger:
            logger.error(msg)
        raise SchemaValidationError(msg) from e
    except OSError as e:
        msg = f"Error reading schema file {schema_path}: {e}"
        if logger:
            logger.error(msg)
        raise SchemaValidationError(msg) from e

    try:
        jsonschema.validate(instance=data, schema=schema)
    except jsonschema.ValidationError as e:
        error_msg = f"Schema validation failed: {e.message}"
        if e.path:
            error_msg += f" (at path: {'/'.join(str(p) for p in e.path)})"
        if logger:
            logger.log_validation_failure(step="schema_validation", error=error_msg)
        raise SchemaValidationError(error_msg) from e
    except jsonschema.SchemaError as e:
        msg = f"Invalid schema in {schema_path}: {e}"
        if logger:
            logger.error(msg)
        raise SchemaValidationError(msg) from e
