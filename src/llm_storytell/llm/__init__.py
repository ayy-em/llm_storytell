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


# Phrases that indicate the requested model id is unknown / unavailable.
# Kept deliberately narrow: generic words like "invalid" or "not found" also
# appear in unrelated 400s (bad params, prompt too long) and must not be
# misreported as an unknown model.
_MODEL_NOT_RECOGNIZED_PHRASES = (
    "model_not_found",
    "invalid_model",
    "unknown model",
    "no such model",
    "could not find model",
    "model does not exist",
    "does not exist or you do not have access",
)

# Sampling parameters some models reject (e.g. Claude Opus 4.7+/Sonnet 5+,
# OpenAI gpt-5/-mini/-nano and o-series only accept the default temperature).
_SAMPLING_PARAMS = ("temperature", "top_p", "top_k")
_SAMPLING_REJECTED_PHRASES = (
    "deprecated",
    "unsupported",
    "not supported",
    "does not support",
)

# HTTP statuses worth retrying; any other 4xx is a request problem that a
# retry cannot fix.
_RETRYABLE_STATUS = frozenset({408, 409, 429})


def _is_model_not_recognized(exc: Exception) -> bool:
    msg = str(exc).lower()
    if any(phrase in msg for phrase in _MODEL_NOT_RECOGNIZED_PHRASES):
        return True
    return getattr(exc, "status_code", None) == 404 and "model" in msg


def _rejected_sampling_params(exc: Exception, params: Mapping[str, Any]) -> list[str]:
    """Return sampling params present in *params* that the API rejected."""
    msg = str(exc).lower()
    if not any(phrase in msg for phrase in _SAMPLING_REJECTED_PHRASES):
        return []
    return [p for p in _SAMPLING_PARAMS if p in params and p in msg]


def _is_non_retryable(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None)
    return (
        isinstance(status, int)
        and 400 <= status < 500
        and status not in _RETRYABLE_STATUS
    )


def _call_with_retries(
    client: Callable[..., Mapping[str, Any]],
    *,
    label: str,
    prompt: str,
    model: str,
    params: dict[str, Any],
    max_retries: int,
    dropped_params: set[str],
) -> Mapping[str, Any]:
    """Invoke *client* with retry and error classification shared by providers.

    * Unknown model -> fail immediately with a clear message.
    * A sampling param rejected by the model (e.g. ``temperature``) -> drop it,
      remember that in *dropped_params* (so later calls skip it) and retry
      without consuming a retry attempt.
    * Other non-retryable 4xx -> fail immediately.
    * Anything else -> retry up to *max_retries* times.
    """
    attempts = 0
    max_attempts = max_retries + 1
    while True:
        call_params = {k: v for k, v in params.items() if k not in dropped_params}
        try:
            return client(prompt=prompt, model=model, **call_params)
        except Exception as exc:  # noqa: BLE001 - classified below
            if _is_model_not_recognized(exc):
                raise LLMProviderError(
                    f"Provider API does not identify requested model: {model}. {exc!s}"
                ) from exc
            rejected = _rejected_sampling_params(exc, call_params)
            if rejected:
                dropped_params.update(rejected)
                continue
            attempts += 1
            if _is_non_retryable(exc) or attempts >= max_attempts:
                raise LLMProviderError(
                    f"{label} call failed after {attempts} attempt(s): {exc!s}"
                ) from exc


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
        # Sampling params the API rejected for this provider's model(s).
        self._dropped_params: set[str] = set()

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

        response = _call_with_retries(
            self._client,
            label="OpenAI",
            prompt=prompt,
            model=effective_model,
            params=params,
            max_retries=self._max_retries,
            dropped_params=self._dropped_params,
        )

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
        if content is None:
            raise LLMProviderError("Missing assistant content")
        if not isinstance(content, str):
            raise LLMProviderError("Missing assistant content")
        if content == "" or content.strip() == "":
            raise LLMProviderError("Empty assistant content")

        if first_choice.get("finish_reason") == "length":
            raise LLMProviderError(
                "OpenAI response truncated (finish_reason=length); output is incomplete"
            )

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


class ClaudeProvider(LLMProvider):
    """Anthropic Claude-backed :class:`LLMProvider` implementation.

    Uses the same injectable-client pattern as :class:`OpenAIProvider` so
    tests can run without network access. The callable should perform a
    Messages API call and return a mapping with:

    * ``content`` (str): assistant text
    * ``usage`` (optional dict): ``input_tokens``, ``output_tokens``
    """

    def __init__(
        self,
        client: Callable[..., Mapping[str, Any]],
        *,
        default_model: str,
        max_retries: int = 2,
        default_max_tokens: int = 16384,
        **default_params: Any,
    ) -> None:
        """Create a new Claude provider.

        Args:
            client:
                Callable invoked as ``client(prompt=..., model=..., **params)``
                returning a mapping with ``content`` and optional ``usage``.
            default_model:
                Default model id when :meth:`generate` receives ``model=None``.
            max_retries:
                Retries for transient failures (not for unknown-model errors).
            default_max_tokens:
                Default ``max_tokens`` for Anthropic Messages API when not
                overridden per call.
            **default_params:
                Extra default kwargs merged into each call (e.g. ``temperature``).
        """
        super().__init__(provider_name="claude")
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative")

        self._client = client
        self._default_model = default_model
        self._max_retries = max_retries
        self._default_max_tokens = default_max_tokens
        self._default_params = default_params
        # Sampling params the API rejected for this provider's model(s).
        self._dropped_params: set[str] = set()

    def generate(
        self,
        prompt: str,
        *,
        step: str,  # noqa: ARG002 - reserved for callers
        model: str | None = None,
        **kwargs: Any,
    ) -> LLMResult:
        """Generate content using Claude Messages API."""
        del step

        effective_model = model or self._default_model
        params: dict[str, Any] = {**self._default_params, **kwargs}
        params["max_tokens"] = int(params.pop("max_tokens", self._default_max_tokens))

        response = _call_with_retries(
            self._client,
            label="Claude",
            prompt=prompt,
            model=effective_model,
            params=params,
            max_retries=self._max_retries,
            dropped_params=self._dropped_params,
        )

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
        """Extract assistant text and token usage from a normalized response."""
        stop_reason = response.get("stop_reason")
        if stop_reason == "max_tokens":
            raise LLMProviderError(
                "Claude response truncated (stop_reason=max_tokens); output is incomplete"
            )
        if stop_reason == "refusal":
            raise LLMProviderError(
                "Claude declined the request (stop_reason=refusal); see llm_io for the prompt"
            )
        content = response.get("content")
        if content is None:
            raise LLMProviderError("Missing assistant content")
        if not isinstance(content, str):
            raise LLMProviderError("Missing assistant content")
        if content == "" or content.strip() == "":
            raise LLMProviderError("Empty assistant content")

        usage = response.get("usage") or {}
        prompt_tokens = usage.get("input_tokens")
        completion_tokens = usage.get("output_tokens")
        total_tokens: int | None = None
        if isinstance(prompt_tokens, int) and isinstance(completion_tokens, int):
            total_tokens = prompt_tokens + completion_tokens

        return content, prompt_tokens, completion_tokens, total_tokens
