"""FastAPI web service wrapping the finance-os application layer.

Thin REST wrapper over the same services used by CLI and MCP server.
Agent endpoints create fresh service instances per request to avoid
cross-request state leakage (agents maintain internal history).

Knowledge graph endpoints share a process-level graph store that
persists across requests (like a database), guarded by an asyncio
lock for thread safety.

Watchlist endpoints persist named ticker lists to disk at
~/.config/finance-os/watchlists.json.

Run locally:
    uvicorn src.web_api:app --reload
    finance-os-api              # console script
"""

import asyncio
import logging
from functools import lru_cache
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.application.config import AppConfig
from src.application.contracts.agents import (
    AnalyzeEarningsRequest,
    AnalyzeEarningsResponse,
    AssessRiskRequest,
    AssessRiskResponse,
    ChallengeThesisRequest,
    ChallengeThesisResponse,
    ClassifyMacroRequest,
    ClassifyMacroResponse,
    EvaluateThesisRequest,
    EvaluateThesisResponse,
    GenerateSignalsRequest,
    GenerateSignalsResponse,
    RunDigestRequest,
    RunDigestResponse,
    RunPipelineRequest,
    RunPipelineResponse,
    SearchFilingsRequest,
    SearchFilingsResponse,
)
from src.application.contracts.knowledge_graph import (
    ExtractEntitiesRequest,
    ExtractEntitiesResponse,
    KGStatsResponse,
    QueryRelatedRequest,
    QueryRelatedResponse,
    QuerySharedRisksRequest,
    QuerySharedRisksResponse,
    QuerySupplyChainRequest,
    QuerySupplyChainResponse,
)
from src.application.contracts.ticker import TickerSummary, TickerTranscript
from src.application.registry import AGENT_CATALOG, create_pipeline_service
from src.application.services.agent_service import AgentService
from src.application.services.digest_service import DigestService
from src.application.services.kg_service import KnowledgeGraphService
from src.application.watchlists import WatchlistNotFoundError, WatchlistStore
from src.core.knowledge_graph import KnowledgeGraph

logger = logging.getLogger(__name__)


class CreateWatchlistRequest(BaseModel):
    """Request body for creating a watchlist."""

    name: str
    tickers: list[str] = Field(default_factory=list)


class UpdateWatchlistRequest(BaseModel):
    """Request body for updating a watchlist's tickers."""

    tickers: list[str]

# Process-level knowledge graph store (persists across requests like a DB)
_kg_graph = KnowledgeGraph()
_kg_lock = asyncio.Lock()

# Process-level watchlist store (persists to ~/.config/finance-os/watchlists.json)
_watchlist_store = WatchlistStore()

app = FastAPI(
    title="finance-os",
    description="Personal investment intelligence API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

VALID_AGENT_NAMES = frozenset(info["name"] for info in AGENT_CATALOG)


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    """Lazy-loaded, cached application configuration."""
    return AppConfig()


@app.exception_handler(ValueError)
async def value_error_handler(_request: Request, exc: ValueError) -> JSONResponse:
    """Map domain ValueError (bad input, unknown agent) to 400."""
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(WatchlistNotFoundError)
async def watchlist_not_found_handler(
    _request: Request, exc: WatchlistNotFoundError,
) -> JSONResponse:
    """Map WatchlistNotFoundError to 404."""
    return JSONResponse(status_code=404, content={"detail": str(exc)})


# --- Health & Info ---


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check."""
    return {"status": "ok"}


@app.get("/agents")
async def list_agents() -> list[dict[str, str]]:
    """List available agents."""
    return list(AGENT_CATALOG)


# --- Ticker Lookup Endpoints ---


@app.get("/ticker/{symbol}/summary", response_model=TickerSummary)
async def ticker_summary(symbol: str) -> Any:
    """Fetch company summary from Yahoo Finance."""
    from src.application.services.ticker_service import get_ticker_summary

    return await get_ticker_summary(symbol)


@app.get("/ticker/{symbol}/transcript", response_model=TickerTranscript)
async def ticker_transcript(symbol: str) -> Any:
    """Fetch latest earnings transcript (best-effort)."""
    from src.application.services.ticker_service import get_ticker_transcript

    return await get_ticker_transcript(symbol)


# --- Agent Endpoints ---


@app.post("/agents/earnings_interpreter", response_model=AnalyzeEarningsResponse)
async def analyze_earnings(request: AnalyzeEarningsRequest) -> Any:
    """Analyze an earnings call transcript for tone, sentiment, and guidance.

    If ``transcript`` is empty but ``ticker`` is provided, auto-fetches
    the latest transcript from Yahoo Finance.
    """
    if not request.transcript and request.ticker:
        from src.application.services.ticker_service import get_ticker_transcript

        result = await get_ticker_transcript(request.ticker)
        if not result.available:
            raise ValueError(
                f"No transcript available for {request.ticker}. "
                "Provide transcript text directly."
            )
        request = request.model_copy(update={"transcript": result.transcript})
    if not request.transcript:
        raise ValueError("Provide either a transcript or a ticker symbol.")
    service = AgentService()
    response = await service.analyze_earnings(request)
    return response.model_dump(mode="json")


@app.post("/agents/macro_regime", response_model=ClassifyMacroResponse)
async def classify_macro(request: ClassifyMacroRequest) -> Any:
    """Classify the current macroeconomic regime from FRED data."""
    if not request.api_key:
        request = request.model_copy(update={"api_key": get_config().fred_api_key})
    service = AgentService()
    response = await service.classify_macro(request)
    return response.model_dump(mode="json")


@app.post("/agents/filing_analyst", response_model=SearchFilingsResponse)
async def search_filings(request: SearchFilingsRequest) -> Any:
    """Search SEC filings for a company."""
    service = AgentService()
    response = await service.search_filings(request)
    return response.model_dump(mode="json")


@app.post("/agents/quant_signal", response_model=GenerateSignalsResponse)
async def generate_signals(request: GenerateSignalsRequest) -> Any:
    """Generate composite quantitative signals."""
    service = AgentService()
    response = await service.generate_signals(request)
    return response.model_dump(mode="json")


@app.post("/agents/thesis_guardian", response_model=EvaluateThesisResponse)
async def evaluate_thesis(request: EvaluateThesisRequest) -> Any:
    """Evaluate investment theses against observed data."""
    service = AgentService()
    response = await service.evaluate_thesis(request)
    return response.model_dump(mode="json")


@app.post("/agents/risk_analyst", response_model=AssessRiskResponse)
async def assess_risk(request: AssessRiskRequest) -> Any:
    """Run risk analysis on a portfolio."""
    service = AgentService()
    response = await service.assess_risk(request)
    return response.model_dump(mode="json")


@app.post("/agents/adversarial", response_model=ChallengeThesisResponse)
async def challenge_thesis(request: ChallengeThesisRequest) -> Any:
    """Adversarially challenge investment claims or thesis."""
    service = AgentService()
    response = await service.challenge_thesis(request)
    return response.model_dump(mode="json")


# --- Pipeline & Digest ---


@app.post("/pipeline", response_model=RunPipelineResponse)
async def run_pipeline(
    request: RunPipelineRequest,
    ticker: str = "",
    date: str = "",
) -> Any:
    """Run a multi-agent research pipeline with dependency ordering."""
    for task in request.tasks:
        if task.agent_name not in VALID_AGENT_NAMES:
            valid = ", ".join(sorted(VALID_AGENT_NAMES))
            msg = f"Unknown agent '{task.agent_name}'. Valid agents: {valid}"
            raise ValueError(msg)
    service = create_pipeline_service(get_config())
    response = await service.run_pipeline(request, ticker=ticker, date=date)
    return response.model_dump(mode="json")


@app.post("/digest", response_model=RunDigestResponse)
async def run_digest(request: RunDigestRequest) -> Any:
    """Run a research digest for a watchlist of tickers."""
    service = DigestService(get_config())
    response = await service.run_digest(request)
    return response.model_dump(mode="json")


# --- Knowledge Graph ---


def _kg_service() -> KnowledgeGraphService:
    """Create a KG service wrapping the process-level graph."""
    return KnowledgeGraphService(_kg_graph)


@app.post("/kg/extract", response_model=ExtractEntitiesResponse)
async def kg_extract(request: ExtractEntitiesRequest) -> Any:
    """Extract entities and relationships from text and ingest into the graph."""
    async with _kg_lock:
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None, _kg_service().extract_and_ingest, request,
        )
    return response.model_dump(mode="json")


@app.post("/kg/query/related", response_model=QueryRelatedResponse)
async def kg_query_related(request: QueryRelatedRequest) -> Any:
    """Find entities related to a given entity."""
    async with _kg_lock:
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None, _kg_service().query_related, request,
        )
    return response.model_dump(mode="json")


@app.post("/kg/query/supply-chain", response_model=QuerySupplyChainResponse)
async def kg_query_supply_chain(request: QuerySupplyChainRequest) -> Any:
    """Trace the supply chain from an entity."""
    async with _kg_lock:
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None, _kg_service().query_supply_chain, request,
        )
    return response.model_dump(mode="json")


@app.post("/kg/query/shared-risks", response_model=QuerySharedRisksResponse)
async def kg_query_shared_risks(request: QuerySharedRisksRequest) -> Any:
    """Find risks shared across multiple entities."""
    async with _kg_lock:
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None, _kg_service().query_shared_risks, request,
        )
    return response.model_dump(mode="json")


@app.get("/kg/stats", response_model=KGStatsResponse)
async def kg_stats() -> Any:
    """Get knowledge graph summary statistics."""
    async with _kg_lock:
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None, _kg_service().get_stats,
        )
    return response.model_dump(mode="json")


# --- Watchlists ---


@app.get("/watchlists")
async def list_watchlists() -> Any:
    """List all watchlists with the active watchlist's data."""
    return await asyncio.to_thread(_watchlist_store.list_all)


@app.post("/watchlists", status_code=201)
async def create_watchlist(body: CreateWatchlistRequest) -> Any:
    """Create a new named watchlist."""
    return await asyncio.to_thread(
        _watchlist_store.create, body.name, body.tickers,
    )


@app.get("/watchlists/{name}")
async def get_watchlist(name: str) -> Any:
    """Get a specific watchlist by name."""
    return await asyncio.to_thread(_watchlist_store.get, name)


@app.put("/watchlists/{name}")
async def update_watchlist(name: str, body: UpdateWatchlistRequest) -> Any:
    """Update tickers in a watchlist."""
    return await asyncio.to_thread(
        _watchlist_store.update, name, body.tickers,
    )


@app.delete("/watchlists/{name}", status_code=204)
async def delete_watchlist(name: str) -> None:
    """Delete a watchlist (cannot delete the active one)."""
    await asyncio.to_thread(_watchlist_store.delete, name)


@app.put("/watchlists/{name}/activate")
async def activate_watchlist(name: str) -> Any:
    """Set a watchlist as the active one."""
    return await asyncio.to_thread(_watchlist_store.activate, name)


def main() -> None:
    """Entry point for the Web API server."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
