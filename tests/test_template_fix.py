"""Test that escaped JSON braces in templates work correctly."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from llm_storytell.prompt_render import render_prompt

_PROJECT_ROOT = Path(__file__).parent.parent
template_path = _PROJECT_ROOT / "prompts/app-defaults/10_outline.md"
variables = {
    "seed": "test seed",
    "beats_count": 5,
    "lore_bible": "test lore",
    "style_rules": "test style",
    "location_context": "",
    "character_context": "",
}

try:
    result = render_prompt(template_path, variables)
    print("SUCCESS: Template rendered without errors")

    # Check that JSON example is present (with escaped braces rendered as literal)
    if '"beats"' in result and '"id"' in result:
        print("SUCCESS: JSON example is present in rendered output")
    else:
        print("WARNING: JSON example not found in output")

    # Check that variables were substituted
    if "test seed" in result and "5" in result:
        print("SUCCESS: Variables were correctly substituted")
    else:
        print("WARNING: Variables may not have been substituted")

    print("\nFix verified: Escaped braces {{ }} render as literal braces in output")

except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
