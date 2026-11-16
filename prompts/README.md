# Prompting rules
- Every prompt must specify required inputs and output format
- Output must include structured fields for continuity and summaries
- No “creative freedom” language
- Hard length targets
- Put run-constant context first and end it with a `<!-- cache-break -->` line; keep that block byte-identical across templates so one prompt-cache entry serves every call (see SPEC.md → Prompt caching)

TTS (v1.1+): The TTS step does not use prompt templates from app-defaults; it chunks the final script and sends each segment to the TTS provider. Segment text is written under `runs/<run_id>/tts/prompts/` for inspection.