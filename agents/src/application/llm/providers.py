"""SkipProvider — pass-through LLM provider for the MCP path."""

from typing import Any

from src.application.llm.types import LLMMessage, LLMProvider, LLMResponse


class SkipProvider:
    """LLM provider that returns agent output unchanged.

    Used in MCP path where the host LLM does reasoning.
    """

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Return the last user message content as-is."""
        user_content = ""
        for msg in reversed(messages):
            if msg.role == "user":
                user_content = msg.content
                break
        return LLMResponse(
            content=user_content,
            model="skip",
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        )


# Verify protocol conformance
_skip_check: type[LLMProvider] = SkipProvider  # type: ignore[assignment]
