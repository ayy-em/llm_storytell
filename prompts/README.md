# Prompting rules
- Every prompt must specify required inputs and output format
- Output must include structured fields for continuity and summaries
- No “creative freedom” language
- Hard length targets

TTS (v1.1+): The TTS step does not use prompt templates from app-defaults; it chunks the final script and sends each segment to the TTS provider. Segment text is written under `runs/<run_id>/tts/prompts/` for inspection.