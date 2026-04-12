"""LLM gateway — pluggable inference for direct-path (CLI/web) usage.

MCP path: host LLM reasons, gateway is skipped.
Direct path: gateway calls a provider for synthesis/reasoning.
"""

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class LLMMessage:
    """A message in an LLM conversation."""

    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class LLMResponse:
    """Response from an LLM provider."""

    content: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol for LLM inference providers."""

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Send messages to an LLM and get a completion.

        Args:
            messages: Conversation messages.
            model: Model override (uses provider default if None).
            temperature: Sampling temperature.
            max_tokens: Max tokens in response.
            **kwargs: Provider-specific options.

        Returns:
            LLMResponse with the completion.
        """
        ...
