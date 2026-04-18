"""MCP server exposing finance-os agents as tools.

Uses FastMCP with stdio transport. Each tool wraps an application service,
creating fresh instances per call to avoid cross-request state leakage.

LLM gateway is skipped by default — the host LLM (Copilot, Claude Desktop)
handles reasoning. Agents return structured data for the host to synthesize.
"""

import re
import sys
from decimal import Decimal
from typing import Any

from mcp.server.fastmcp import FastMCP

from src.application.config import AppConfig
from src.application.contracts.agents import (
    AnalyzeEarningsRequest,
    ClassifyMacroRequest,
    RunDigestRequest,
    RunPipelineRequest,
    TaskDefinition,
)
from src.application.registry import AGENT_CATALOG, create_pipeline_service
from src.application.services.agent_service import AgentService
from src.application.services.digest_service import DigestService

_TICKER_RE = re.compile(r"^[A-Za-z0-9.\-]{1,10}$")

mcp = FastMCP(
    "finance-os-agents",
    instructions=(
        "Personal investment intelligence tools. "
        "Use analyze_earnings for transcript analysis, classify_macro for macro regime, "
        "research_digest for watchlist digests, and orchestrate for multi-agent pipelines."
    ),
)

# Valid agent names for the orchestrate tool
VALID_AGENT_NAMES = frozenset(info["name"] for info in AGENT_CATALOG)


@mcp.tool()
async def analyze_earnings(transcript: str = "", ticker: str = "") -> dict[str, Any]:
    """Analyze an earnings call transcript for tone, sentiment, and guidance.

    Provide either transcript text directly, or a ticker to auto-fetch
    the latest earnings transcript from Yahoo Finance.

    Args:
        transcript: Full earnings call transcript text.
        ticker: Company ticker symbol — auto-fetches transcript if transcript is empty.

    Returns:
        Analysis with tone, net_sentiment, confidence, guidance_direction,
        guidance_count, key_phrase_count, and human-readable content.
    """
    if not transcript and ticker:
        from src.application.services.ticker_service import get_ticker_transcript

        ticker = ticker.strip().upper()
        if not _TICKER_RE.match(ticker):
            msg = f"Invalid ticker symbol: {ticker!r}"
            raise ValueError(msg)
        result = await get_ticker_transcript(ticker)
        if result.available:
            transcript = result.transcript
        else:
            msg = f"No earnings transcript found for ticker '{ticker}'."
            raise ValueError(msg)
    if not transcript:
        msg = "Provide either a transcript or a ticker symbol."
        raise ValueError(msg)
    request = AnalyzeEarningsRequest(transcript=transcript, ticker=ticker)
    service = AgentService()
    response = await service.analyze_earnings(request)
    return response.model_dump(mode="json")


@mcp.tool()
async def classify_macro(indicators: list[str] | None = None) -> dict[str, Any]:
    """Classify the current macroeconomic regime from FRED data.

    Args:
        indicators: FRED series IDs to fetch (e.g. ["GDP", "UNRATE"]).
            Uses sensible defaults if not provided.

    Returns:
        Regime classification (expansion/contraction/transition) with
        indicators_fetched, indicators_with_data, and dashboard content.
    """
    config = AppConfig()
    request = ClassifyMacroRequest(
        api_key=config.fred_api_key,
        indicators=indicators or [],
    )
    service = AgentService()
    response = await service.classify_macro(request)
    return response.model_dump(mode="json")


@mcp.tool()
async def research_digest(
    tickers: list[str],
    lookback_days: int = 7,
    alert_threshold: float = 0.5,
) -> dict[str, Any]:
    """Run a research digest for a watchlist of tickers.

    Ingests recent data, scores materiality, and generates alerts.

    Args:
        tickers: Watchlist ticker symbols (e.g. ["AAPL", "MSFT", "GOOGL"]).
        lookback_days: Number of days of data to consider.
        alert_threshold: Materiality threshold for alerts (0.0–1.0).

    Returns:
        Digest with ticker_count, entry_count, alert_count, material_count,
        and human-readable content.
    """
    request = RunDigestRequest(
        tickers=tickers,
        lookback_days=lookback_days,
        alert_threshold=Decimal(str(alert_threshold)),
    )
    service = DigestService(AppConfig())
    response = await service.run_digest(request)
    return response.model_dump(mode="json")


@mcp.tool()
async def orchestrate(
    tasks: list[dict[str, Any]],
    ticker: str = "",
    date: str = "",
) -> dict[str, Any]:
    """Run a multi-agent research pipeline.

    Executes multiple agents with dependency ordering and produces
    a consolidated research memo.

    Args:
        tasks: Task definitions, each with:
            - agent_name: One of macro_regime, filing_analyst,
              earnings_interpreter, quant_signal, thesis_guardian,
              risk_analyst, adversarial.
            - prompt: Prompt text for the agent.
            - kwargs: Additional keyword arguments (optional).
            - priority: Scheduling priority (optional, default 0).
            - depends_on: Task IDs that must complete first (optional).
            - task_id: Unique identifier for this task (optional).
        ticker: Ticker symbol for memo generation.
        date: Analysis date (YYYY-MM-DD) for memo.

    Returns:
        Pipeline results with per-task outcomes, duration, success/failure
        counts, and optional research memo.
    """
    # Validate agent names upfront
    for task_def in tasks:
        agent_name = task_def.get("agent_name", "")
        if agent_name not in VALID_AGENT_NAMES:
            valid = ", ".join(sorted(VALID_AGENT_NAMES))
            msg = f"Unknown agent '{agent_name}'. Valid agents: {valid}"
            raise ValueError(msg)

    task_models = [TaskDefinition(**t) for t in tasks]
    request = RunPipelineRequest(tasks=task_models)
    service = create_pipeline_service()
    response = await service.run_pipeline(request, ticker=ticker, date=date)
    return response.model_dump(mode="json")


def main() -> None:
    """Entry point for the MCP server."""
    import logging

    logging.basicConfig(
        level=logging.WARNING,
        stream=sys.stderr,
        format="%(levelname)s: %(message)s",
    )
    mcp.run()


if __name__ == "__main__":
    main()
