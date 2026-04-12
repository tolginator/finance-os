"""MockProvider — canned LLM responses for testing."""

from typing import Any

from src.application.llm.types import LLMMessage, LLMProvider, LLMResponse


class MockProvider:
    """LLM provider that returns canned responses for testing."""

    def __init__(self, response: str = "Mock LLM response") -> None:
        self._response = response
        self.calls: list[dict[str, Any]] = []

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Return a canned response and record the call."""
        self.calls.append({
            "messages": messages,
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        })
        return LLMResponse(
            content=self._response,
            model=model or "mock",
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        )


# Verify protocol conformance
_mock_check: type[LLMProvider] = MockProvider  # type: ignore[assignment]
