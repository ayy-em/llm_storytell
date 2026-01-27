"""LLM provider abstraction.

This module defines the public interface for invoking LLMs from the
pipeline, along with an initial OpenAI-backed implementation.

Design goals
------------

* Pipeline steps must not call vendor SDKs directly.
* Providers can be swapped without changing step code.
* Provider responses expose provider/model metadata and token usage so
  that callers can handle logging and state updates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping


@dataclass
class LLMResult:
    """Result of a single LLM generation call.

    Attributes:
        content:
            The primary text content returned by the model.
        provider:
            Provider identifier (e.g. ``\"openai\"``).
        model:
            Model identifier used for the call.
        prompt_tokens:
            Number of prompt tokens consumed by the call, if reported
            by the provider.
        completion_tokens:
            Number of completion tokens produced by the call, if
            reported by the provider.
        total_tokens:
            Total tokens consumed by the call, if reported by the
            provider. When not provided explicitly by the provider it
            may be derived as ``prompt_tokens + completion_tokens``.
        raw_response:
            Provider-specific raw response object, retained for
            debugging and future extension. Callers should not rely on
            its shape.
    """

    content: str
    provider: str
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    raw_response: Any | None = None


class LLMProviderError(RuntimeError):
    """Raised when an LLM provider call fails."""


class LLMProvider:
    """Abstract base class for LLM providers.

    Implementations must override :meth:`generate` and return
    :class:`LLMResult` instances. The interface is intentionally small
    and vendor-agnostic so that the orchestrator and pipeline steps
    do not depend on specific SDKs.
    """

    provider_name: str

    def __init__(self, provider_name: str) -> None:
        self.provider_name = provider_name

    def generate(
        self,
        prompt: str,
        *,
        step: str,
        model: str | None = None,
        **kwargs: Any,
    ) -> LLMResult:  # pragma: no cover - interface only
        """Generate content from the LLM.

        Args:
            prompt:
                Prompt text to send to the model.
            step:
                Name of the pipeline step invoking the provider,
                used for logging and token tracking by callers.
            model:
                Optional model identifier. If omitted, the provider's
                configured default model is used.
            **kwargs:
                Provider-specific generation parameters (e.g.
                ``temperature``, ``max_tokens``). Callers should pass
                only simple, serializable values.

        Returns:
            :class:`LLMResult` with generated content and metadata.
        """
        msg = f"{self.__class__.__name__}.generate() is not implemented"
        raise NotImplementedError(msg)


class OpenAIProvider(LLMProvider):
    """OpenAI-backed :class:`LLMProvider` implementation.

    This provider is intentionally decoupled from the OpenAI SDK so
    that unit tests can run without network access or additional
    dependencies. A minimal callable must be supplied that performs
    the underlying API call.

    The callable is expected to accept ``prompt`` and ``model`` as
    keyword arguments, along with any additional parameters, and return
    a mapping compatible with the Chat Completions response shape:

    .. code-block:: json

        {
          "choices": [
            {
              "message": {
                "content": "..."
              }
            }
          ],
          "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 8,
            "total_tokens": 18
          }
        }
    """

    def __init__(
        self,
        client: Callable[..., Mapping[str, Any]],
        *,
        default_model: str,
        max_retries: int = 2,
        **default_params: Any,
    ) -> None:
        """Create a new OpenAI provider.

        Args:
            client:
                Callable that performs the underlying OpenAI request
                (for example, a thin wrapper around
                ``OpenAI().chat.completions.create``) and returns a
                mapping with ``choices`` and optional ``usage`` keys.
            default_model:
                Default model identifier to use when ``model`` is not
                provided to :meth:`generate`.
            max_retries:
                Number of times to retry a failed call before raising
                :class:`LLMProviderError`. A value of ``0`` disables
                retries beyond the first attempt.
            **default_params:
                Default generation parameters (e.g. ``temperature``)
                that will be merged with per-call overrides.
        """
        super().__init__(provider_name="openai")
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative")

        self._client = client
        self._default_model = default_model
        self._max_retries = max_retries
        self._default_params = default_params

    def generate(
        self,
        prompt: str,
        *,
        step: str,  # noqa: ARG002 - reserved for callers
        model: str | None = None,
        **kwargs: Any,
    ) -> LLMResult:
        """Generate content using OpenAI Chat Completions."""
        del step  # not used here but reserved for callers

        effective_model = model or self._default_model
        params: dict[str, Any] = {**self._default_params, **kwargs}

        last_error: Exception | None = None
        attempts = 0
        max_attempts = self._max_retries + 1

        while attempts < max_attempts:
            try:
                response = self._client(
                    prompt=prompt,
                    model=effective_model,
                    **params,
                )
                break
            except Exception as exc:  # pragma: no cover - exercised via tests
                last_error = exc
                attempts += 1
                if attempts >= max_attempts:
                    msg = f"OpenAI call failed after {attempts} attempts"
                    raise LLMProviderError(msg) from last_error
        else:  # pragma: no cover - defensive, loop always breaks or raises
            msg = f"OpenAI call failed after {attempts} attempts"
            raise LLMProviderError(msg) from last_error

        content, prompt_tokens, completion_tokens, total_tokens = (
            self._extract_response(response)
        )

        return LLMResult(
            content=content,
            provider=self.provider_name,
            model=effective_model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            raw_response=response,
        )

    @staticmethod
    def _extract_response(
        response: Mapping[str, Any],
    ) -> tuple[str, int | None, int | None, int | None]:
        """Extract content and token usage from an OpenAI response."""
        try:
            choices = response["choices"]
        except KeyError as exc:  # pragma: no cover - defensive
            raise LLMProviderError("OpenAI response missing 'choices'") from exc

        if not choices:
            msg = "OpenAI response contained no choices"
            raise LLMProviderError(msg)

        first_choice = choices[0]
        message = first_choice.get("message", {})
        content = message.get("content")
        if not isinstance(content, str):
            msg = "OpenAI response missing assistant message content"
            raise LLMProviderError(msg)

        usage = response.get("usage") or {}
        prompt_tokens = usage.get("prompt_tokens")
        completion_tokens = usage.get("completion_tokens")
        total_tokens = usage.get("total_tokens")

        # Derive total_tokens if provider did not send it but both
        # components are present.
        if total_tokens is None and (
            isinstance(prompt_tokens, int) and isinstance(completion_tokens, int)
        ):
            total_tokens = prompt_tokens + completion_tokens

        return content, prompt_tokens, completion_tokens, total_tokens
