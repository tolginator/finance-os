"""Tests for application services — agent, pipeline, and digest."""

from decimal import Decimal
from unittest.mock import patch

import pytest

from src.application.config import AppConfig
from src.application.contracts.agents import (
    AnalyzeEarningsRequest,
    AssessRiskRequest,
    ChallengeThesisRequest,
    GenerateSignalsRequest,
    RunDigestRequest,
    RunPipelineRequest,
)
from src.application.services.agent_service import AgentService
from src.application.services.digest_service import DigestService
from src.application.services.pipeline_service import PipelineService
from src.core.agent import AgentResponse, BaseAgent
from src.pipelines.research_digest import DataSource

# --- Test helpers ---


class StubAgent(BaseAgent):
    """Agent that returns a fixed response for testing services."""

    def __init__(self, name: str = "stub", response_content: str = "stub output",
                 metadata: dict | None = None):
        super().__init__(name=name, description="Stub agent")
        self._response_content = response_content
        self._metadata = metadata or {}

    @property
    def system_prompt(self) -> str:
        return "Stub"

    async def run(self, prompt: str, **kwargs) -> AgentResponse:
        return AgentResponse(
            content=self._response_content,
            metadata=self._metadata,
        )


class CapturingAgent(BaseAgent):
    """Agent that captures kwargs passed to run() for assertion."""

    def __init__(self, name: str = "capturing", response_content: str = "captured",
                 metadata: dict | None = None):
        super().__init__(name=name, description="Capturing agent")
        self._response_content = response_content
        self._metadata = metadata or {}
        self.captured_kwargs: dict = {}

    @property
    def system_prompt(self) -> str:
        return "Capturing"

    async def run(self, prompt: str, **kwargs) -> AgentResponse:
        self.captured_kwargs = dict(kwargs)
        return AgentResponse(
            content=self._response_content,
            metadata=self._metadata,
        )


# --- AgentService tests ---


class TestAgentServiceEarnings:
    @pytest.mark.asyncio
    async def test_analyze_earnings_maps_response(self):
        service = AgentService()
        request = AnalyzeEarningsRequest(
            transcript="Revenue increased 15% year over year. We expect continued growth."
        )
        result = await service.analyze_earnings(request)
        assert result.content  # agent produces a report
        assert result.tone  # tone is classified
        assert isinstance(result.net_sentiment, float)
        assert isinstance(result.confidence, str)
        assert isinstance(result.guidance_count, int)


class TestAgentServiceSignals:
    @pytest.mark.asyncio
    async def test_generate_signals_with_sentiment(self):
        service = AgentService()
        request = GenerateSignalsRequest(sentiment=Decimal("0.75"))
        result = await service.generate_signals(request)
        assert result.content
        assert result.agent == "quant_signal"


class TestAgentServiceChallenge:
    @pytest.mark.asyncio
    async def test_challenge_with_claims(self):
        service = AgentService()
        request = ChallengeThesisRequest(
            claims=["Revenue will grow 20% annually for 5 years"]
        )
        result = await service.challenge_thesis(request)
        assert result.content
        assert isinstance(result.counter_count, int)
        assert isinstance(result.blind_spot_count, int)


class TestAgentServiceRisk:
    @pytest.mark.asyncio
    async def test_assess_risk_with_returns(self):
        service = AgentService()
        returns = [Decimal(str(x)) for x in [0.02, -0.01, 0.03, -0.02, 0.01,
                                               0.015, -0.005, 0.02, -0.01, 0.01]]
        request = AssessRiskRequest(returns=returns)
        result = await service.assess_risk(request)
        assert result.content


# --- PipelineService tests ---


class TestPipelineService:
    @pytest.mark.asyncio
    async def test_run_pipeline_with_registered_agents(self):
        stub = StubAgent(
            name="test-agent",
            response_content="Result",
            metadata={"key": "value"},
        )
        service = PipelineService()
        service.register_agent(stub)

        request = RunPipelineRequest(tasks=[
            {"agent_name": "test-agent", "prompt": "Do work"},
        ])
        result = await service.run_pipeline(request)
        assert result.successful == 1
        assert result.failed == 0
        assert len(result.results) == 1
        assert result.results[0]["content"] == "Result"

    @pytest.mark.asyncio
    async def test_pipeline_skips_unregistered_agents(self):
        service = PipelineService()
        request = RunPipelineRequest(tasks=[
            {"agent_name": "nonexistent", "prompt": "Do work"},
        ])
        result = await service.run_pipeline(request)
        assert result.successful == 0
        assert result.failed == 0
        assert len(result.results) == 0

    @pytest.mark.asyncio
    async def test_pipeline_with_task_ids(self):
        stub = StubAgent(name="agent-a", response_content="A output")
        service = PipelineService()
        service.register_agent(stub)

        request = RunPipelineRequest(tasks=[
            {"agent_name": "agent-a", "prompt": "Task 1", "task_id": "task-1"},
            {"agent_name": "agent-a", "prompt": "Task 2", "task_id": "task-2"},
        ])
        result = await service.run_pipeline(request)
        assert result.successful == 2
        task_ids = [r["task_id"] for r in result.results]
        assert "task-1" in task_ids
        assert "task-2" in task_ids

    @pytest.mark.asyncio
    async def test_pipeline_with_dependencies(self):
        stub_a = StubAgent(name="first", response_content="First")
        stub_b = StubAgent(name="second", response_content="Second")
        service = PipelineService()
        service.register_agent(stub_a)
        service.register_agent(stub_b)

        request = RunPipelineRequest(tasks=[
            {"agent_name": "first", "prompt": "Go"},
            {"agent_name": "second", "prompt": "After first", "depends_on": ["first"]},
        ])
        result = await service.run_pipeline(request)
        assert result.successful == 2

    @pytest.mark.asyncio
    async def test_pipeline_with_memo(self):
        stub = StubAgent(name="analyst", response_content="Analysis done")
        service = PipelineService()
        service.register_agent(stub)

        request = RunPipelineRequest(tasks=[
            {"agent_name": "analyst", "prompt": "Analyze"},
        ])
        result = await service.run_pipeline(request, ticker="AAPL", date="2026-04-12")
        assert result.memo is not None
        assert result.memo["ticker"] == "AAPL"
        assert "analyst" in result.memo["sources"]


class TestPipelineContextPropagation:
    """Test that pipeline propagates context between dependent tasks."""

    async def test_regime_flows_to_downstream(self) -> None:
        macro = StubAgent(
            name="macro_regime",
            response_content="EXPANSION",
            metadata={"regime": "EXPANSION", "indicators_fetched": 5},
        )
        consumer = CapturingAgent(name="quant_signal")
        service = PipelineService()
        service.register_agent(macro)
        service.register_agent(consumer)

        request = RunPipelineRequest(tasks=[
            {"agent_name": "macro_regime", "prompt": "Go", "task_id": "macro"},
            {
                "agent_name": "quant_signal",
                "prompt": "Signals",
                "task_id": "signals",
                "depends_on": ["macro"],
            },
        ])
        result = await service.run_pipeline(request)
        assert result.successful == 2
        assert consumer.captured_kwargs.get("regime") == "EXPANSION"

    async def test_sentiment_and_direction_flow(self) -> None:
        earnings = StubAgent(
            name="earnings_interpreter",
            response_content="Bullish",
            metadata={
                "net_sentiment": 0.8,
                "guidance_direction": "raised",
            },
        )
        consumer = CapturingAgent(name="quant_signal")
        service = PipelineService()
        service.register_agent(earnings)
        service.register_agent(consumer)

        request = RunPipelineRequest(tasks=[
            {"agent_name": "earnings_interpreter", "prompt": "Analyze", "task_id": "earnings"},
            {
                "agent_name": "quant_signal",
                "prompt": "Signals",
                "task_id": "signals",
                "depends_on": ["earnings"],
            },
        ])
        result = await service.run_pipeline(request)
        assert result.successful == 2
        assert consumer.captured_kwargs["sentiment"] == 0.8
        assert consumer.captured_kwargs["direction"] == "raised"

    async def test_context_from_multiple_producers(self) -> None:
        macro = StubAgent(
            name="macro_regime",
            response_content="EXPANSION",
            metadata={"regime": "EXPANSION"},
        )
        earnings = StubAgent(
            name="earnings_interpreter",
            response_content="Bullish",
            metadata={"net_sentiment": 0.6, "guidance_direction": "maintained"},
        )
        consumer = CapturingAgent(name="quant_signal")
        service = PipelineService()
        service.register_agent(macro)
        service.register_agent(earnings)
        service.register_agent(consumer)

        request = RunPipelineRequest(tasks=[
            {"agent_name": "macro_regime", "prompt": "Go", "task_id": "macro"},
            {"agent_name": "earnings_interpreter", "prompt": "Go", "task_id": "earnings"},
            {
                "agent_name": "quant_signal",
                "prompt": "Signals",
                "task_id": "signals",
                "depends_on": ["macro", "earnings"],
            },
        ])
        result = await service.run_pipeline(request)
        assert result.successful == 3
        assert consumer.captured_kwargs["regime"] == "EXPANSION"
        assert consumer.captured_kwargs["sentiment"] == 0.6
        assert consumer.captured_kwargs["direction"] == "maintained"


class TestPipelineSoftFailure:
    """Test that soft failures are properly detected and block dependents."""

    async def test_soft_failure_counted_as_failed(self) -> None:
        soft_fail = StubAgent(
            name="macro_regime",
            response_content="API key required",
            metadata={"error": "missing_api_key"},
        )
        service = PipelineService()
        service.register_agent(soft_fail)

        request = RunPipelineRequest(tasks=[
            {"agent_name": "macro_regime", "prompt": "Go", "task_id": "macro"},
        ])
        result = await service.run_pipeline(request)
        assert result.successful == 0
        assert result.failed == 1

    async def test_soft_failure_blocks_dependents(self) -> None:
        soft_fail = StubAgent(
            name="macro_regime",
            response_content="API key required",
            metadata={"error": "missing_api_key"},
        )
        consumer = StubAgent(name="quant_signal", response_content="Signals")
        service = PipelineService()
        service.register_agent(soft_fail)
        service.register_agent(consumer)

        request = RunPipelineRequest(tasks=[
            {"agent_name": "macro_regime", "prompt": "Go", "task_id": "macro"},
            {
                "agent_name": "quant_signal",
                "prompt": "Signals",
                "task_id": "signals",
                "depends_on": ["macro"],
            },
        ])
        result = await service.run_pipeline(request)
        assert result.successful == 0
        assert result.failed == 2

    async def test_soft_failure_excluded_from_memo(self) -> None:
        soft_fail = StubAgent(
            name="macro_regime",
            response_content="API key required",
            metadata={"error": "missing_api_key"},
        )
        good = StubAgent(
            name="filing_analyst",
            response_content="Filings found",
            metadata={"filing_count": 3},
        )
        service = PipelineService()
        service.register_agent(soft_fail)
        service.register_agent(good)

        request = RunPipelineRequest(tasks=[
            {"agent_name": "macro_regime", "prompt": "Go", "task_id": "macro"},
            {"agent_name": "filing_analyst", "prompt": "Search", "task_id": "filings"},
        ])
        result = await service.run_pipeline(request, ticker="MSFT", date="2026-04-13")
        assert result.memo is not None
        assert "macro_regime" not in result.memo["sources"]
        assert "filing_analyst" in result.memo["sources"]


# --- DigestService tests ---


class TestDigestService:
    async def test_empty_digest_with_no_sources_and_no_api(self) -> None:
        """Digest with no sources and no API access returns empty."""
        config = AppConfig(fred_api_key="")
        service = DigestService(config)
        request = RunDigestRequest(tickers=["ZZZZZ"])
        with patch(
            "src.application.services.digest_service._fetch_filing_sources",
            return_value=[],
        ):
            result = await service.run_digest(request)
        assert result.ticker_count == 1
        assert result.entry_count == 0

    async def test_digest_with_explicit_sources(self) -> None:
        """Digest with explicit sources skips auto-fetch."""
        service = DigestService()
        request = RunDigestRequest(
            tickers=["AAPL"],
            sources=[{
                "source_type": "filing",
                "ticker": "AAPL",
                "date": "2026-04-01",
                "content": "Revenue increased significantly",
                "metadata": {"sentiment": "0.6"},
            }],
        )
        result = await service.run_digest(request)
        assert result.entry_count == 1
        assert "AAPL" in result.content

    async def test_auto_fetch_produces_entries(self) -> None:
        """When no sources provided, auto-fetch creates entries."""
        config = AppConfig(fred_api_key="")
        service = DigestService(config)

        mock_sources = [
            DataSource(
                source_type="edgar",
                ticker="MSFT",
                date="2026-04-01",
                content="10-K filed 2026-04-01: Annual report",
                metadata={"form_type": "10-K", "sentiment": "0.1"},
            ),
        ]
        with patch(
            "src.application.services.digest_service._fetch_filing_sources",
            return_value=mock_sources,
        ):
            request = RunDigestRequest(tickers=["MSFT"])
            result = await service.run_digest(request)
        assert result.entry_count >= 1
        assert result.ticker_count == 1
        assert "MSFT" in result.content

    async def test_auto_fetch_with_macro(self) -> None:
        """Auto-fetch includes macro regime when FRED key available."""
        config = AppConfig(fred_api_key="test_key")
        service = DigestService(config)

        mock_filing_sources = [
            DataSource(
                source_type="edgar",
                ticker="AAPL",
                date="2026-04-01",
                content="10-K filing",
                metadata={"sentiment": "0.1"},
            ),
        ]
        mock_macro_source = DataSource(
            source_type="macro",
            ticker="MACRO",
            date="2026-04-01",
            content="Macro regime: EXPANSION",
            metadata={"regime": "EXPANSION", "sentiment": "0.5"},
        )
        with (
            patch(
                "src.application.services.digest_service._fetch_filing_sources",
                return_value=mock_filing_sources,
            ),
            patch(
                "src.application.services.digest_service._fetch_macro_source",
                return_value=mock_macro_source,
            ),
        ):
            request = RunDigestRequest(tickers=["AAPL"])
            result = await service.run_digest(request)
        # Should have filing + macro entries
        assert result.entry_count >= 2

    async def test_material_entries_generate_alerts(self) -> None:
        """Entries with high sentiment become material and generate alerts."""
        config = AppConfig(fred_api_key="")
        service = DigestService(config)

        mock_sources = [
            DataSource(
                source_type="edgar",
                ticker="TSLA",
                date="2026-04-01",
                content="8-K material event",
                metadata={"form_type": "8-K", "sentiment": "-0.6"},
            ),
        ]
        with patch(
            "src.application.services.digest_service._fetch_filing_sources",
            return_value=mock_sources,
        ):
            request = RunDigestRequest(
                tickers=["TSLA"],
                alert_threshold=Decimal("0.5"),
            )
            result = await service.run_digest(request)
        assert result.entry_count == 1
        assert result.material_count == 1
        assert result.alert_count == 1
