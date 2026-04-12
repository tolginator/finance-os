"""Integration tests for Azure OpenAI provider and LLM gateway.

These tests call the real Azure OpenAI endpoint using Entra ID auth.
They are automatically skipped if the Azure endpoint is not configured.
"""

import pytest

from src.application.config import AppConfig
from src.application.llm.azure_openai_provider import AzureOpenAIProvider
from src.application.llm.gateway import create_gateway
from src.application.llm.types import LLMMessage, LLMResponse

_config = AppConfig()
_azure_configured = bool(_config.azure.endpoint and _config.azure.deployment)

requires_azure = pytest.mark.skipif(
    not _azure_configured,
    reason="Azure OpenAI not configured (azure.endpoint / azure.deployment empty)",
)


@pytest.mark.integration
@requires_azure
class TestAzureOpenAIProviderLive:
    """Integration tests for AzureOpenAIProvider against the real endpoint."""

    @pytest.fixture
    async def provider(self):
        p = AzureOpenAIProvider(
            endpoint=_config.azure.endpoint,
            deployment=_config.azure.deployment,
            api_version=_config.azure.api_version,
        )
        yield p
        await p.close()

    @pytest.mark.asyncio
    async def test_basic_completion(self, provider):
        """A simple prompt returns a non-empty response."""
        messages = [LLMMessage(role="user", content="Say hello in one word.")]
        response = await provider.complete(messages, max_tokens=10)

        assert isinstance(response, LLMResponse)
        assert len(response.content) > 0
        assert response.model == _config.azure.deployment

    @pytest.mark.asyncio
    async def test_completion_returns_usage(self, provider):
        """Response includes token usage statistics."""
        messages = [LLMMessage(role="user", content="What is 2+2?")]
        response = await provider.complete(messages, max_tokens=10)

        assert response.usage.get("prompt_tokens", 0) > 0
        assert response.usage.get("completion_tokens", 0) > 0
        assert response.usage.get("total_tokens", 0) > 0

    @pytest.mark.asyncio
    async def test_system_prompt_respected(self, provider):
        """System prompt influences the response."""
        messages = [
            LLMMessage(role="system", content="You are a calculator. Only respond with numbers."),
            LLMMessage(role="user", content="What is 5 + 3?"),
        ]
        response = await provider.complete(messages, max_tokens=10)

        assert "8" in response.content

    @pytest.mark.asyncio
    async def test_temperature_zero_is_deterministic(self, provider):
        """Two calls with temperature=0 should return the same result."""
        messages = [LLMMessage(role="user", content="What is the capital of France?")]
        r1 = await provider.complete(messages, temperature=0.0, max_tokens=10)
        r2 = await provider.complete(messages, temperature=0.0, max_tokens=10)

        assert r1.content == r2.content


@pytest.mark.integration
@requires_azure
class TestLLMGatewayLive:
    """Integration tests for the full gateway → Azure OpenAI path."""

    @pytest.fixture
    async def gateway(self):
        gw = create_gateway(
            provider_type="azure_openai",
            endpoint=_config.azure.endpoint,
            deployment=_config.azure.deployment,
            api_version=_config.azure.api_version,
        )
        yield gw
        await gw.provider.close()

    @pytest.mark.asyncio
    async def test_gateway_complete(self, gateway):
        """Gateway routes completion to Azure OpenAI."""
        messages = [LLMMessage(role="user", content="Say 'test' and nothing else.")]
        response = await gateway.complete(messages, max_tokens=10)

        assert isinstance(response, LLMResponse)
        assert len(response.content) > 0

    @pytest.mark.asyncio
    async def test_gateway_synthesize(self, gateway):
        """Gateway synthesize method produces a narrative from agent output."""
        agent_output = (
            "AAPL: Revenue $94.9B (+6% YoY), EPS $1.64 (beat by $0.04). "
            "Gross margin 46.2%. Services revenue $24.2B (record). "
            "iPhone revenue $46.2B. Guidance: Q1 revenue $123-127B."
        )
        response = await gateway.synthesize(
            system_prompt="You are a financial analyst. Summarize concisely.",
            agent_output=agent_output,
            model=_config.azure.deployment,
        )

        assert isinstance(response, LLMResponse)
        assert len(response.content) > 50
        assert response.usage.get("total_tokens", 0) > 0
