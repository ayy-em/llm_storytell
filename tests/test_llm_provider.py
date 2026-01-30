"""Tests for LLM provider abstraction and OpenAI implementation."""

import sys
from importlib import import_module
from pathlib import Path
from typing import Any, Mapping

import pytest


# Import from the package using the hyphenated name
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

llm_module = import_module("llm_storytell.llm")

LLMResult = llm_module.LLMResult
LLMProvider = llm_module.LLMProvider
LLMProviderError = llm_module.LLMProviderError
OpenAIProvider = llm_module.OpenAIProvider


class TestLLMResult:
    """Tests for the LLMResult dataclass."""

    def test_llm_result_holds_metadata(self) -> None:
        """LLMResult stores content and token metadata."""
        result = LLMResult(
            content="Hello world",
            provider="openai",
            model="gpt-4",
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
            raw_response={"some": "data"},
        )

        assert result.content == "Hello world"
        assert result.provider == "openai"
        assert result.model == "gpt-4"
        assert result.prompt_tokens == 10
        assert result.completion_tokens == 20
        assert result.total_tokens == 30
        assert result.raw_response == {"some": "data"}


class TestLLMProviderInterface:
    """Tests for the LLMProvider interface."""

    def test_generate_not_implemented(self) -> None:
        """Base LLMProvider.generate raises NotImplementedError."""
        provider = LLMProvider(provider_name="test-provider")

        try:
            provider.generate("prompt", step="outline")
        except NotImplementedError as exc:
            assert "generate() is not implemented" in str(exc)
        else:  # pragma: no cover - defensive
            assert False, "Expected NotImplementedError"


class _FakeOpenAIClient:
    """Test double for the OpenAI client callable."""

    def __init__(self, responses: list[Mapping[str, Any]] | None = None) -> None:
        self._responses = responses or []
        self.calls: list[dict[str, Any]] = []
        self._failures_before_success = 0

    def fail_n_times(self, n: int) -> None:
        """Configure the client to raise n times before succeeding."""
        self._failures_before_success = n

    def __call__(self, *_, **kwargs: Any) -> Mapping[str, Any]:
        self.calls.append(kwargs)

        if self._failures_before_success > 0:
            self._failures_before_success -= 1
            raise RuntimeError("temporary failure")

        if not self._responses:
            raise RuntimeError("no fake responses configured")

        return self._responses.pop(0)


class TestOpenAIProviderSuccess:
    """OpenAIProvider happy-path behaviour."""

    def test_generate_returns_llm_result_with_usage(self) -> None:
        """Successful call returns LLMResult with token usage."""
        response: Mapping[str, Any] = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Hello from OpenAI",
                    },
                }
            ],
            "usage": {
                "prompt_tokens": 12,
                "completion_tokens": 8,
                "total_tokens": 20,
            },
        }

        client = _FakeOpenAIClient(responses=[response])
        provider = OpenAIProvider(
            client,
            default_model="gpt-4",
            max_retries=2,
            temperature=0.1,
        )

        result = provider.generate("Hello", step="outline")

        # Result content and metadata
        assert isinstance(result, LLMResult)
        assert result.content == "Hello from OpenAI"
        assert result.provider == "openai"
        assert result.model == "gpt-4"
        assert result.prompt_tokens == 12
        assert result.completion_tokens == 8
        assert result.total_tokens == 20
        assert result.raw_response is not None

        # Underlying client called once with expected parameters
        assert len(client.calls) == 1
        call_kwargs = client.calls[0]
        assert call_kwargs["prompt"] == "Hello"
        assert call_kwargs["model"] == "gpt-4"
        assert call_kwargs["temperature"] == 0.1

    def test_generate_allows_model_override(self) -> None:
        """Caller can override the model per call."""
        response: Mapping[str, Any] = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Hi from another model",
                    },
                }
            ],
            "usage": {
                "prompt_tokens": 5,
                "completion_tokens": 7,
                "total_tokens": 12,
            },
        }

        client = _FakeOpenAIClient(responses=[response])
        provider = OpenAIProvider(
            client,
            default_model="gpt-4",
        )

        result = provider.generate(
            "Hi",
            step="outline",
            model="gpt-4o",
            temperature=0.5,
        )

        assert result.model == "gpt-4o"
        assert len(client.calls) == 1
        call_kwargs = client.calls[0]
        assert call_kwargs["model"] == "gpt-4o"
        assert call_kwargs["temperature"] == 0.5


class TestOpenAIProviderRetries:
    """Tests for retry behaviour."""

    def test_retries_then_succeeds(self) -> None:
        """Provider retries transient failures up to max_retries."""
        response: Mapping[str, Any] = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Recovered after retry",
                    },
                }
            ],
            "usage": {
                "prompt_tokens": 3,
                "completion_tokens": 4,
                "total_tokens": 7,
            },
        }

        client = _FakeOpenAIClient(responses=[response])
        client.fail_n_times(1)

        provider = OpenAIProvider(
            client,
            default_model="gpt-4",
            max_retries=2,
        )

        result = provider.generate("Hi", step="outline")

        assert result.content == "Recovered after retry"
        # One failure + one success
        assert len(client.calls) == 2

    def test_exhausts_retries_and_raises(self) -> None:
        """Provider raises LLMProviderError after exhausting retries."""
        response: Mapping[str, Any] = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Should never be returned",
                    },
                }
            ],
        }

        client = _FakeOpenAIClient(responses=[response])
        client.fail_n_times(3)

        provider = OpenAIProvider(
            client,
            default_model="gpt-4",
            max_retries=1,
        )

        try:
            provider.generate("Hi", step="outline")
        except LLMProviderError as exc:
            assert "failed after" in str(exc)
        else:  # pragma: no cover - defensive
            assert False, "Expected LLMProviderError"

        # Initial attempt + one retry
        assert len(client.calls) == 2


class TestOpenAIProviderUsageExtraction:
    """Tests around token usage extraction logic."""

    def test_total_tokens_can_be_derived(self) -> None:
        """total_tokens is derived when missing but components present."""
        response: Mapping[str, Any] = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Derived usage",
                    },
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                # total_tokens intentionally omitted
            },
        }

        client = _FakeOpenAIClient(responses=[response])
        provider = OpenAIProvider(
            client,
            default_model="gpt-4",
        )

        result = provider.generate("Hi", step="outline")

        assert result.prompt_tokens == 10
        assert result.completion_tokens == 5
        assert result.total_tokens == 15

    def test_missing_usage_is_tolerated(self) -> None:
        """Provider works even if usage block is absent."""
        response: Mapping[str, Any] = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "No usage information",
                    },
                }
            ],
            # no usage field
        }

        client = _FakeOpenAIClient(responses=[response])
        provider = OpenAIProvider(
            client,
            default_model="gpt-4",
        )

        result = provider.generate("Hi", step="outline")

        assert result.content == "No usage information"
        assert result.prompt_tokens is None
        assert result.completion_tokens is None
        assert result.total_tokens is None


class TestOpenAIProviderEmptyContent:
    """Provider boundary raises on None, empty, or whitespace-only content."""

    def test_content_none_raises_missing_assistant_content(self) -> None:
        """Provider returns content=None → raises LLMProviderError."""
        response: Mapping[str, Any] = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                    },
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 0, "total_tokens": 1},
        }

        client = _FakeOpenAIClient(responses=[response])
        provider = OpenAIProvider(client, default_model="gpt-4")

        with pytest.raises(LLMProviderError) as exc_info:
            provider.generate("Hi", step="outline")

        assert "Missing assistant content" in str(exc_info.value)

    def test_content_empty_string_raises_empty_assistant_content(self) -> None:
        """Provider returns content=\"\" → raises LLMProviderError."""
        response: Mapping[str, Any] = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                    },
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 0, "total_tokens": 1},
        }

        client = _FakeOpenAIClient(responses=[response])
        provider = OpenAIProvider(client, default_model="gpt-4")

        with pytest.raises(LLMProviderError) as exc_info:
            provider.generate("Hi", step="outline")

        assert "Empty assistant content" in str(exc_info.value)

    def test_content_whitespace_only_raises_empty_assistant_content(self) -> None:
        """Provider returns content=\"   \" → raises LLMProviderError."""
        response: Mapping[str, Any] = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "   ",
                    },
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 0, "total_tokens": 1},
        }

        client = _FakeOpenAIClient(responses=[response])
        provider = OpenAIProvider(client, default_model="gpt-4")

        with pytest.raises(LLMProviderError) as exc_info:
            provider.generate("Hi", step="outline")

        assert "Empty assistant content" in str(exc_info.value)


class TestOpenAIProviderModelNotRecognized:
    """Provider fails immediately when API does not identify the requested model."""

    def test_model_not_recognized_fails_immediately_without_retry(self) -> None:
        """When the client raises a model-not-found type error, fail immediately, no retries."""
        call_count = 0

        def client_that_raises_model_not_found(
            *_: Any, **kwargs: Any
        ) -> Mapping[str, Any]:
            nonlocal call_count
            call_count += 1
            raise ValueError(
                "The model 'gpt-4.1-nano' does not exist or you do not have access to it."
            )

        provider = OpenAIProvider(
            client_that_raises_model_not_found,
            default_model="gpt-4.1-nano",
            max_retries=2,
        )

        with pytest.raises(LLMProviderError) as exc_info:
            provider.generate("Hi", step="outline")

        msg = str(exc_info.value)
        assert "Provider API does not identify requested model" in msg
        assert "gpt-4.1-nano" in msg
        assert "does not exist" in msg
        # Must not retry: client called exactly once
        assert call_count == 1
