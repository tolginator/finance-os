"""FastAPI web service wrapping the finance-os application layer.

Thin REST wrapper over the same services used by CLI and MCP server.
Each endpoint creates fresh service instances per request to avoid
cross-request state leakage (agents maintain internal history).

Run locally:
    uvicorn src.web_api:app --reload
    finance-os-api              # console script
"""

import logging
from functools import lru_cache
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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
from src.application.registry import AGENT_CATALOG, create_pipeline_service
from src.application.services.agent_service import AgentService
from src.application.services.digest_service import DigestService

logger = logging.getLogger(__name__)

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


# --- Health & Info ---


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check."""
    return {"status": "ok"}


@app.get("/agents")
async def list_agents() -> list[dict[str, str]]:
    """List available agents."""
    return list(AGENT_CATALOG)


# --- Agent Endpoints ---


@app.post("/agents/earnings_interpreter", response_model=AnalyzeEarningsResponse)
async def analyze_earnings(request: AnalyzeEarningsRequest) -> Any:
    """Analyze an earnings call transcript for tone, sentiment, and guidance."""
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


def main() -> None:
    """Entry point for the Web API server."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
