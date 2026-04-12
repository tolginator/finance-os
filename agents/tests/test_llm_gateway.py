"""Tests for the LLM gateway and providers."""

import pytest

from src.application.llm.gateway import LLMGateway, create_gateway
from src.application.llm.providers import SkipProvider
from src.application.llm.types import LLMMessage, LLMProvider
from tests.support.mock_provider import MockProvider


class TestMockProvider:
    @pytest.mark.asyncio
    async def test_returns_canned_response(self):
        provider = MockProvider(response="Test output")
        messages = [LLMMessage(role="user", content="Hello")]
        result = await provider.complete(messages)
        assert result.content == "Test output"
        assert result.model == "mock"

    @pytest.mark.asyncio
    async def test_records_calls(self):
        provider = MockProvider()
        messages = [LLMMessage(role="user", content="Query")]
        await provider.complete(messages, model="gpt-4o")
        assert len(provider.calls) == 1
        assert provider.calls[0]["model"] == "gpt-4o"

    @pytest.mark.asyncio
    async def test_multiple_calls_recorded(self):
        provider = MockProvider()
        msg = [LLMMessage(role="user", content="A")]
        await provider.complete(msg)
        await provider.complete(msg)
        assert len(provider.calls) == 2

    def test_conforms_to_protocol(self):
        assert isinstance(MockProvider(), LLMProvider)


class TestSkipProvider:
    @pytest.mark.asyncio
    async def test_returns_last_user_message(self):
        provider = SkipProvider()
        messages = [
            LLMMessage(role="system", content="You are helpful"),
            LLMMessage(role="user", content="Agent output data"),
        ]
        result = await provider.complete(messages)
        assert result.content == "Agent output data"
        assert result.model == "skip"

    @pytest.mark.asyncio
    async def test_empty_messages_returns_empty(self):
        provider = SkipProvider()
        result = await provider.complete([])
        assert result.content == ""

    @pytest.mark.asyncio
    async def test_no_user_messages_returns_empty(self):
        provider = SkipProvider()
        messages = [LLMMessage(role="system", content="sys")]
        result = await provider.complete(messages)
        assert result.content == ""

    def test_conforms_to_protocol(self):
        assert isinstance(SkipProvider(), LLMProvider)


class TestLLMGateway:
    @pytest.mark.asyncio
    async def test_default_uses_skip_provider(self):
        gateway = LLMGateway()
        messages = [LLMMessage(role="user", content="Pass through")]
        result = await gateway.complete(messages)
        assert result.content == "Pass through"

    @pytest.mark.asyncio
    async def test_with_mock_provider(self):
        provider = MockProvider(response="Mocked")
        gateway = LLMGateway(provider)
        messages = [LLMMessage(role="user", content="Q")]
        result = await gateway.complete(messages)
        assert result.content == "Mocked"

    @pytest.mark.asyncio
    async def test_synthesize_sends_system_and_user(self):
        provider = MockProvider(response="Synthesized summary")
        gateway = LLMGateway(provider)
        result = await gateway.synthesize(
            system_prompt="You are a financial analyst",
            agent_output="Revenue up 15%, margins stable",
        )
        assert result.content == "Synthesized summary"
        assert len(provider.calls) == 1
        messages = provider.calls[0]["messages"]
        assert messages[0].role == "system"
        assert messages[1].role == "user"
        assert "Revenue up 15%" in messages[1].content

    @pytest.mark.asyncio
    async def test_synthesize_custom_instruction(self):
        provider = MockProvider(response="Custom")
        gateway = LLMGateway(provider)
        result = await gateway.synthesize(
            system_prompt="Analyst",
            agent_output="Data",
            instruction="Summarize in one sentence",
        )
        assert result.content == "Custom"
        messages = provider.calls[0]["messages"]
        assert "Summarize in one sentence" in messages[1].content

    @pytest.mark.asyncio
    async def test_model_override_forwarded(self):
        provider = MockProvider()
        gateway = LLMGateway(provider)
        messages = [LLMMessage(role="user", content="Q")]
        await gateway.complete(messages, model="claude-sonnet-4")
        assert provider.calls[0]["model"] == "claude-sonnet-4"


class TestCreateGateway:
    def test_skip_provider(self):
        gateway = create_gateway("skip")
        assert isinstance(gateway.provider, SkipProvider)

    def test_mock_provider_via_constructor(self):
        provider = MockProvider(response="Hello")
        gateway = LLMGateway(provider)
        assert isinstance(gateway.provider, MockProvider)

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            create_gateway("nonexistent")

    def test_litellm_provider(self):
        gateway = create_gateway("litellm", default_model="gpt-4o-mini")
        from src.application.llm.litellm_provider import LiteLLMProvider

        assert isinstance(gateway.provider, LiteLLMProvider)
