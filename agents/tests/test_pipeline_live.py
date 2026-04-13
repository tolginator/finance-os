"""Integration tests for the research pipeline — runs agents against live APIs.

Tests the full pipeline flow: agent execution, context propagation between
dependent tasks, soft failure handling, and memo generation.
"""

import pytest

from src.application.config import AppConfig
from src.application.contracts.agents import RunPipelineRequest, TaskDefinition
from src.application.registry import create_pipeline_service

_config = AppConfig()
requires_edgar = pytest.mark.skipif(
    not _config.sec_edgar_email,
    reason="SEC EDGAR email not configured",
)
requires_fred = pytest.mark.skipif(
    not _config.fred_api_key,
    reason="FRED API key not configured",
)


@pytest.mark.integration
@requires_edgar
class TestPipelineFilingAnalystLive:
    """Pipeline integration with live SEC EDGAR."""

    async def test_filing_analyst_receives_ticker_via_kwargs(self) -> None:
        """Filing analyst resolves CIK when ticker is passed in kwargs."""
        service = create_pipeline_service()
        request = RunPipelineRequest(tasks=[
            TaskDefinition(
                agent_name="filing_analyst",
                prompt="Search recent filings for MSFT",
                task_id="filings",
                kwargs={"ticker": "MSFT"},
            ),
        ])
        result = await service.run_pipeline(request, ticker="MSFT", date="2026-04-13")
        assert result.successful == 1
        assert result.failed == 0
        filings_result = result.results[0]
        assert filings_result["agent_name"] == "filing_analyst"
        assert filings_result["success"]
        assert filings_result["metadata"].get("cik") == "789019"
        assert filings_result["metadata"].get("filing_count", 0) > 0

    async def test_filing_analyst_without_kwargs_uses_prompt(self) -> None:
        """Filing analyst extracts ticker from prompt when kwargs empty."""
        service = create_pipeline_service()
        request = RunPipelineRequest(tasks=[
            TaskDefinition(
                agent_name="filing_analyst",
                prompt="Search recent filings for AAPL",
                task_id="filings",
            ),
        ])
        result = await service.run_pipeline(request)
        filings_result = result.results[0]
        assert filings_result["success"]
        # Should have searched for AAPL, not "Search"
        query = filings_result["metadata"].get("query", "")
        cik = filings_result["metadata"].get("cik", "")
        assert query == "AAPL" or cik == "320193"


@pytest.mark.integration
@requires_fred
class TestPipelineMacroRegimeLive:
    """Pipeline integration with live FRED API."""

    async def test_macro_regime_gets_api_key_from_config(self) -> None:
        """MacroRegimeAgent receives FRED key via registry config injection."""
        config = AppConfig()
        service = create_pipeline_service(config)
        request = RunPipelineRequest(tasks=[
            TaskDefinition(
                agent_name="macro_regime",
                prompt="Classify current macro regime",
                task_id="macro",
                kwargs={"indicators": ["UNRATE"]},
            ),
        ])
        result = await service.run_pipeline(request)
        assert result.successful == 1
        macro_result = result.results[0]
        assert macro_result["success"]
        assert macro_result["metadata"].get("regime") in (
            "EXPANSION", "CONTRACTION", "TRANSITION",
        )
        # Should NOT be a soft failure
        assert "error" not in macro_result["metadata"]


@pytest.mark.integration
@requires_fred
@requires_edgar
class TestPipelineContextChainingLive:
    """End-to-end pipeline with context flowing between agents."""

    async def test_macro_regime_feeds_quant_signal(self) -> None:
        """Quant signal receives regime from macro_regime via context propagation."""
        config = AppConfig()
        service = create_pipeline_service(config)
        request = RunPipelineRequest(tasks=[
            TaskDefinition(
                agent_name="macro_regime",
                prompt="Classify current macro regime",
                task_id="macro",
                kwargs={"indicators": ["UNRATE"]},
            ),
            TaskDefinition(
                agent_name="quant_signal",
                prompt="Generate signals for MSFT",
                task_id="signals",
                depends_on=["macro"],
            ),
        ])
        result = await service.run_pipeline(request)
        assert result.successful == 2
        signals_result = next(
            r for r in result.results if r["agent_name"] == "quant_signal"
        )
        # quant_signal should have received regime and produced signals
        assert signals_result["success"]
        assert "composite" in signals_result["metadata"]
        assert int(signals_result["metadata"]["composite"]["n_signals"]) >= 1

    async def test_mini_pipeline_with_memo(self) -> None:
        """Run a small pipeline and verify memo excludes soft failures."""
        config = AppConfig()
        service = create_pipeline_service(config)
        request = RunPipelineRequest(tasks=[
            TaskDefinition(
                agent_name="macro_regime",
                prompt="Classify regime",
                task_id="macro",
                kwargs={"indicators": ["UNRATE"]},
            ),
            TaskDefinition(
                agent_name="filing_analyst",
                prompt="Search filings for MSFT",
                task_id="filings",
                kwargs={"ticker": "MSFT"},
            ),
        ])
        result = await service.run_pipeline(
            request, ticker="MSFT", date="2026-04-13",
        )
        assert result.successful >= 1
        assert result.memo is not None
        assert result.memo["ticker"] == "MSFT"
        # Only successful agents should be in sources
        for source in result.memo["sources"]:
            matching = [
                r for r in result.results
                if r["agent_name"] == source and r["success"]
            ]
            assert len(matching) > 0


@pytest.mark.integration
class TestPipelineSoftFailureLive:
    """Verify soft failure handling with real agents."""

    async def test_missing_fred_key_is_soft_failure(self) -> None:
        """MacroRegimeAgent without API key returns soft failure."""
        # Create service WITHOUT config so no FRED key
        service = create_pipeline_service(AppConfig(fred_api_key=""))
        request = RunPipelineRequest(tasks=[
            TaskDefinition(
                agent_name="macro_regime",
                prompt="Classify regime",
                task_id="macro",
            ),
        ])
        result = await service.run_pipeline(request)
        assert result.failed == 1
        assert result.successful == 0
        macro_result = result.results[0]
        assert macro_result["metadata"].get("error") == "missing_api_key"
