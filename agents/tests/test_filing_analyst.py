"""Tests for the filing analyst agent."""

import pytest

from src.agents.filing_analyst import (
    Filing,
    FilingAnalystAgent,
)
from src.core.agent import AgentResponse


class TestFilingAnalystAgent:
    """Tests for FilingAnalystAgent."""

    def test_instantiation(self) -> None:
        agent = FilingAnalystAgent()
        assert agent.name == "filing_analyst"
        assert "SEC" in agent.description

    def test_system_prompt_content(self) -> None:
        agent = FilingAnalystAgent()
        prompt = agent.system_prompt
        assert "risk" in prompt.lower()
        assert "MD&A" in prompt
        assert "CapEx" in prompt

    @pytest.mark.asyncio
    async def test_run_without_input(self) -> None:
        agent = FilingAnalystAgent()
        response = await agent.run("")
        assert isinstance(response, AgentResponse)
        assert len(response.content) > 0

    @pytest.mark.asyncio
    async def test_run_with_ticker(self) -> None:
        """Agent should return some response when given a ticker, even if network fails."""
        agent = FilingAnalystAgent()
        response = await agent.run("AAPL", ticker="AAPL")
        assert isinstance(response, AgentResponse)
        assert len(response.content) > 0


class TestFiling:
    """Tests for Filing dataclass."""

    def test_create_filing(self) -> None:
        filing = Filing(
            accession_number="0001234567-24-000001",
            form_type="10-K",
            filing_date="2024-03-15",
            primary_document="filing.htm",
            description="Annual report",
        )
        assert filing.form_type == "10-K"
        assert filing.filing_date == "2024-03-15"
