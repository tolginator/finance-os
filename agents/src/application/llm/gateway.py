"""LLM gateway — routes inference requests to the configured provider."""

from typing import Any

from src.application.llm.providers import SkipProvider
from src.application.llm.types import LLMMessage, LLMProvider, LLMResponse


class LLMGateway:
    """Routes LLM requests to a configured provider.

    The gateway is the single entry point for all LLM inference in the
    application layer. CLI and web paths use it; MCP path can skip it.

    Supports per-operation model overrides and synthesis templates.
    """

    def __init__(self, provider: LLMProvider | None = None) -> None:
        self._provider = provider or SkipProvider()

    @property
    def provider(self) -> LLMProvider:
        """The current LLM provider."""
        return self._provider

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Route a completion request to the provider.

        Args:
            messages: Conversation messages.
            model: Model override for this request.
            temperature: Sampling temperature.
            max_tokens: Max tokens in response.
            **kwargs: Provider-specific options.

        Returns:
            LLMResponse from the provider.
        """
        return await self._provider.complete(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

    async def synthesize(
        self,
        system_prompt: str,
        agent_output: str,
        *,
        model: str | None = None,
        instruction: str = (
            "Synthesize the following agent output into a clear, actionable summary."
        ),
    ) -> LLMResponse:
        """Synthesize agent output into a narrative using LLM reasoning.

        This is the primary integration point for the direct path (CLI/web).
        Agents produce structured data; the gateway synthesizes it.

        Args:
            system_prompt: The agent's system prompt for context.
            agent_output: The structured output from the agent.
            model: Model override.
            instruction: Synthesis instruction.

        Returns:
            LLMResponse with synthesized narrative.
        """
        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=f"{instruction}\n\n{agent_output}"),
        ]
        return await self.complete(messages, model=model)


def create_gateway(provider_type: str = "skip", **kwargs: Any) -> LLMGateway:
    """Factory for creating configured gateways.

    Args:
        provider_type: One of "skip", "litellm".
        **kwargs: Provider-specific configuration.

    Returns:
        Configured LLMGateway.
    """
    if provider_type == "skip":
        return LLMGateway(SkipProvider())
    elif provider_type == "litellm":
        from src.application.llm.litellm_provider import LiteLLMProvider

        return LLMGateway(LiteLLMProvider(**kwargs))
    else:
        msg = f"Unknown provider type: {provider_type}"
        raise ValueError(msg)
