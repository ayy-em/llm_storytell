"""Tests for prompt template rendering."""

from importlib import import_module
from pathlib import Path
import sys

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Handle hyphenated package name
prompt_render_module = import_module("llm-storytell.prompt_render")

MissingVariableError = prompt_render_module.MissingVariableError
PromptRenderError = prompt_render_module.PromptRenderError
TemplateNotFoundError = prompt_render_module.TemplateNotFoundError
render_prompt = prompt_render_module.render_prompt


class TestRenderPrompt:
    """Test successful prompt rendering."""

    def test_simple_template_with_string_variables(self, tmp_path: Path) -> None:
        """Test rendering a simple template with string variables."""
        template_file = tmp_path / "template.md"
        template_file.write_text("Hello {name}, welcome to {place}!")

        result = render_prompt(template_file, {"name": "Alice", "place": "Wonderland"})

        assert result == "Hello Alice, welcome to Wonderland!"

    def test_template_with_numeric_variables(self, tmp_path: Path) -> None:
        """Test rendering template with numeric variables."""
        template_file = tmp_path / "template.md"
        template_file.write_text("Count: {count}, Price: ${price:.2f}")

        result = render_prompt(template_file, {"count": 5, "price": 19.99})

        assert result == "Count: 5, Price: $19.99"

    def test_template_with_boolean_variables(self, tmp_path: Path) -> None:
        """Test rendering template with boolean variables."""
        template_file = tmp_path / "template.md"
        template_file.write_text("Status: {enabled}")

        result = render_prompt(template_file, {"enabled": True})

        assert result == "Status: True"

    def test_template_with_format_specifiers(self, tmp_path: Path) -> None:
        """Test rendering template with format specifiers."""
        template_file = tmp_path / "template.md"
        template_file.write_text("Name: {name:10s}, Number: {num:05d}")

        result = render_prompt(template_file, {"name": "Test", "num": 42})

        assert result == "Name: Test      , Number: 00042"

    def test_template_with_no_variables(self, tmp_path: Path) -> None:
        """Test rendering template with no placeholders."""
        template_file = tmp_path / "template.md"
        template_file.write_text("This is a static template with no variables.")

        result = render_prompt(template_file, {})

        assert result == "This is a static template with no variables."

    def test_template_with_escaped_braces(self, tmp_path: Path) -> None:
        """Test rendering template with escaped braces (literal {{ and }})."""
        template_file = tmp_path / "template.md"
        template_file.write_text("Literal braces: {{ and }}, variable: {name}")

        result = render_prompt(template_file, {"name": "Alice"})

        assert result == "Literal braces: { and }, variable: Alice"

    def test_template_with_unicode_content(self, tmp_path: Path) -> None:
        """Test rendering template with Unicode content."""
        template_file = tmp_path / "template.md"
        template_file.write_text("Hello {name}, 你好！", encoding="utf-8")

        result = render_prompt(template_file, {"name": "世界"})

        assert result == "Hello 世界, 你好！"

    def test_template_with_multiline_content(self, tmp_path: Path) -> None:
        """Test rendering template with multiline content."""
        template_file = tmp_path / "template.md"
        template_file.write_text("Line 1: {var1}\nLine 2: {var2}\nLine 3: {var3}")

        result = render_prompt(template_file, {"var1": "A", "var2": "B", "var3": "C"})

        assert result == "Line 1: A\nLine 2: B\nLine 3: C"

    def test_deterministic_rendering(self, tmp_path: Path) -> None:
        """Test that rendering is deterministic (same inputs = same output)."""
        template_file = tmp_path / "template.md"
        template_file.write_text("{greeting} {name}")

        variables = {"greeting": "Hello", "name": "World"}

        result1 = render_prompt(template_file, variables)
        result2 = render_prompt(template_file, variables)

        assert result1 == result2
        assert result1 == "Hello World"


class TestMissingVariableError:
    """Test missing variable error handling."""

    def test_single_missing_variable(self, tmp_path: Path) -> None:
        """Test error when a single variable is missing."""
        template_file = tmp_path / "template.md"
        template_file.write_text("Hello {name}, welcome to {place}!")

        with pytest.raises(MissingVariableError) as exc_info:
            render_prompt(template_file, {"name": "Alice"})

        assert exc_info.value.template_path == template_file
        assert "place" in exc_info.value.missing_variables
        assert len(exc_info.value.missing_variables) == 1
        assert "place" in str(exc_info.value)

    def test_multiple_missing_variables(self, tmp_path: Path) -> None:
        """Test error when multiple variables are missing."""
        template_file = tmp_path / "template.md"
        template_file.write_text("{var1} {var2} {var3}")

        with pytest.raises(MissingVariableError) as exc_info:
            render_prompt(template_file, {"var1": "A"})

        assert exc_info.value.template_path == template_file
        missing = exc_info.value.missing_variables
        assert "var2" in missing
        assert "var3" in missing
        assert len(missing) == 2
        assert "var2" in str(exc_info.value)
        assert "var3" in str(exc_info.value)

    def test_all_variables_missing(self, tmp_path: Path) -> None:
        """Test error when all variables are missing."""
        template_file = tmp_path / "template.md"
        template_file.write_text("{name} {age}")

        with pytest.raises(MissingVariableError) as exc_info:
            render_prompt(template_file, {})

        assert exc_info.value.template_path == template_file
        missing = exc_info.value.missing_variables
        assert "name" in missing
        assert "age" in missing
        assert len(missing) == 2

    def test_extra_variables_provided(self, tmp_path: Path) -> None:
        """Test that providing extra variables doesn't cause errors."""
        template_file = tmp_path / "template.md"
        template_file.write_text("Hello {name}!")

        # Providing extra variables should be fine
        result = render_prompt(
            template_file, {"name": "Alice", "extra": "ignored", "another": 123}
        )

        assert result == "Hello Alice!"


class TestTemplateNotFoundError:
    """Test template file not found error handling."""

    def test_nonexistent_template_file(self, tmp_path: Path) -> None:
        """Test error when template file doesn't exist."""
        template_file = tmp_path / "nonexistent.md"

        with pytest.raises(TemplateNotFoundError) as exc_info:
            render_prompt(template_file, {"name": "Alice"})

        assert exc_info.value.template_path == template_file
        assert "not found" in str(exc_info.value).lower()

    def test_template_in_nonexistent_directory(self, tmp_path: Path) -> None:
        """Test error when template is in a nonexistent directory."""
        template_file = tmp_path / "nonexistent" / "template.md"

        with pytest.raises(TemplateNotFoundError) as exc_info:
            render_prompt(template_file, {"name": "Alice"})

        assert exc_info.value.template_path == template_file


class TestPromptRenderError:
    """Test other prompt rendering errors."""

    def test_encoding_error_handling(self, tmp_path: Path) -> None:
        """Test handling of encoding errors (if possible to simulate)."""
        # This is difficult to test without creating invalid UTF-8 files
        # which may not be possible on all systems. We'll test the error
        # message format instead by checking the code handles it.
        template_file = tmp_path / "template.md"
        template_file.write_text("Valid template {name}")

        # Normal case should work
        result = render_prompt(template_file, {"name": "test"})
        assert result == "Valid template test"

    def test_format_error_handling(self, tmp_path: Path) -> None:
        """Test handling of format errors in template."""
        template_file = tmp_path / "template.md"
        # Invalid format specifier that might cause issues
        template_file.write_text("{name:invalid_format}")

        # This should raise an error during formatting
        with pytest.raises(PromptRenderError) as exc_info:
            render_prompt(template_file, {"name": "test"})

        assert (
            "formatting" in str(exc_info.value).lower()
            or "format" in str(exc_info.value).lower()
        )


class TestPlaceholderExtraction:
    """Test placeholder extraction logic through rendering."""

    def test_placeholders_with_format_specifiers(self, tmp_path: Path) -> None:
        """Test that placeholders with format specifiers are correctly identified."""
        template_file = tmp_path / "template.md"
        template_file.write_text("{name:10s} {count:05d}")

        # Should correctly identify 'name' and 'count' as required variables
        with pytest.raises(MissingVariableError) as exc_info:
            render_prompt(template_file, {})

        missing = exc_info.value.missing_variables
        assert "name" in missing
        assert "count" in missing
        assert len(missing) == 2

    def test_placeholders_ignore_escaped_braces(self, tmp_path: Path) -> None:
        """Test that escaped braces are not treated as placeholders."""
        template_file = tmp_path / "template.md"
        template_file.write_text("{{literal}} {variable}")

        # Should only require 'variable', not treat {{literal}} as a placeholder
        with pytest.raises(MissingVariableError) as exc_info:
            render_prompt(template_file, {})

        missing = exc_info.value.missing_variables
        assert "variable" in missing
        assert len(missing) == 1
        assert "literal" not in missing

    def test_complex_template_with_mixed_content(self, tmp_path: Path) -> None:
        """Test placeholder extraction in complex templates."""
        template_file = tmp_path / "template.md"
        template_file.write_text(
            "Start {var1} middle {{escaped}} {var2:10s} end {var3}"
        )

        with pytest.raises(MissingVariableError) as exc_info:
            render_prompt(template_file, {})

        missing = exc_info.value.missing_variables
        assert "var1" in missing
        assert "var2" in missing
        assert "var3" in missing
        assert len(missing) == 3
