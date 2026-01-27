# LLM-Storytell: Tech Stack
- Python 3.12 because latest stable LTS version
- OpenAI's API was chosen for all LLM prompts (both text-based content and voice-to-text prompts) for simplicity
- ruff for linting is a personal preference
- PyYAML (>=6.0) for parsing pipeline configuration YAML files. Python standard library does not include YAML support, and PyYAML is the de facto standard for YAML parsing in Python. Required for T0005 pipeline definition loader.
- jsonschema (>=4.0.0) for validating structured LLM outputs against JSON schemas. Python standard library does not include JSON Schema validation. jsonschema is the standard library for JSON Schema validation in Python and is required to ensure LLM outputs match expected schemas before persisting to state or artifacts. Required for T0020 outline stage and subsequent validation steps.