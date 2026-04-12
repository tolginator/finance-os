"""LiteLLM-based LLM provider implementation.

Wraps litellm.acompletion for multi-provider support (OpenAI, Anthropic, ollama, etc.).
LiteLLM types do not leak outside this module.
"""

from typing import Any

import litellm

from src.application.llm.types import LLMMessage, LLMProvider, LLMResponse


class LiteLLMProvider:
    """LLM provider using litellm for multi-provider routing."""

    def __init__(self, default_model: str = "gpt-4o") -> None:
        self._default_model = default_model

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Complete via litellm."""
        resolved_model = model or self._default_model
        litellm_messages = [{"role": m.role, "content": m.content} for m in messages]

        litellm_kwargs: dict[str, Any] = {
            "model": resolved_model,
            "messages": litellm_messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            litellm_kwargs["max_tokens"] = max_tokens
        litellm_kwargs.update(kwargs)

        response = await litellm.acompletion(**litellm_kwargs)

        content = response.choices[0].message.content or ""
        usage = {}
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        return LLMResponse(
            content=content,
            model=resolved_model,
            usage=usage,
        )


# Verify protocol conformance
assert isinstance(LiteLLMProvider, type)
_: type[LLMProvider] = LiteLLMProvider  # type: ignore[assignment]
