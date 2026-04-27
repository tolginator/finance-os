"""Pydantic request/response contracts for agent operations.

Contracts model what agents actually do, not aspirational capabilities.
Each pair maps directly to an agent's run() kwargs and metadata output.
"""

from decimal import Decimal

from pydantic import BaseModel, Field

from src.application.contracts.regime import MacroRegimeReport

# --- Earnings Interpreter ---


class AnalyzeEarningsRequest(BaseModel):
    """Request to analyze an earnings transcript.

    Provide either ``transcript`` directly, or ``ticker`` to auto-fetch
    the latest transcript from Yahoo Finance.
    """

    transcript: str = Field(default="", description="Earnings call transcript text")
    ticker: str = Field(
        default="",
        description="Company ticker — auto-fetches transcript if transcript is empty",
    )


class AnalyzeEarningsResponse(BaseModel):
    """Structured earnings analysis results."""

    content: str = Field(description="Human-readable analysis report")
    tone: str = Field(description="Overall tone classification")
    net_sentiment: float = Field(description="Net sentiment score")
    confidence: str = Field(description="Confidence level in the assessment")
    guidance_direction: str = Field(description="Forward guidance direction")
    guidance_count: int = Field(description="Number of guidance items extracted")
    key_phrase_count: int = Field(description="Number of key phrases identified")


# --- Macro Regime ---


class ClassifyMacroRequest(BaseModel):
    """Request to classify the current macro regime."""

    api_key: str = Field(default="", description="FRED API key")
    indicators: list[str] = Field(
        default_factory=list,
        description="FRED series IDs to fetch. Empty uses defaults.",
    )


class ClassifyMacroResponse(BaseModel):
    """Macro regime classification results."""

    content: str = Field(description="Human-readable macro dashboard")
    regime: str = Field(description="Legacy regime (expansion/contraction/transition)")
    indicators_fetched: int = Field(description="Number of indicators requested")
    indicators_with_data: int = Field(description="Number that returned data")
    regime_report: MacroRegimeReport | None = Field(
        default=None,
        description="Multi-dimensional regime report (enhanced classifier)",
    )


# --- Filing Analyst ---


class SearchFilingsRequest(BaseModel):
    """Request to search/list SEC filings for a company."""

    ticker: str = Field(default="", description="Company ticker symbol")
    cik: str = Field(default="", description="SEC CIK number")
    form_type: str = Field(default="10-K", description="Filing form type filter")


class SearchFilingsResponse(BaseModel):
    """Filing search results."""

    content: str = Field(description="Formatted filing list or search results")
    cik: str = Field(default="", description="Resolved CIK")
    form_type: str = Field(default="", description="Form type searched")
    filing_count: int = Field(default=0, description="Number of filings found")


# --- Quant Signal ---


class GenerateSignalsRequest(BaseModel):
    """Request to generate composite quant signals."""

    signals: list[dict] = Field(
        default_factory=list,
        description="Pre-computed signal dicts with name/value/weight/direction",
    )
    sentiment: Decimal | None = Field(default=None, description="Sentiment input")
    regime: str = Field(default="", description="Current macro regime")
    direction: str = Field(default="", description="Signal direction context")
    source: str = Field(default="", description="Signal source attribution")
    method: str = Field(default="equal_weight", description="Scoring method")


class GenerateSignalsResponse(BaseModel):
    """Composite signal results."""

    content: str = Field(description="Human-readable signal report")
    agent: str = Field(default="quant_signal", description="Agent that produced signals")
    composite: dict = Field(default_factory=dict, description="Composite score details")
    signals: list[dict] = Field(default_factory=list, description="Individual signal details")


# --- Thesis Guardian ---


class EvaluateThesisRequest(BaseModel):
    """Request to evaluate investment theses against observed data."""

    theses: list[dict] = Field(
        description="Thesis dicts with ticker, hypothesis, assumptions, status",
    )
    data: dict[str, Decimal] = Field(
        default_factory=dict,
        description="Observed metric values to evaluate assumptions against",
    )


class EvaluateThesisResponse(BaseModel):
    """Thesis evaluation results."""

    content: str = Field(description="Human-readable thesis report")
    theses_checked: int = Field(description="Number of theses evaluated")
    alerts_generated: int = Field(description="Total alerts raised")
    critical_alerts: int = Field(description="Number of critical alerts")


# --- Risk Agent ---


class AssessRiskRequest(BaseModel):
    """Request to run risk analysis on a portfolio."""

    positions: list[dict] = Field(
        default_factory=list,
        description="Position dicts with ticker, weight, returns",
    )
    scenarios: list[dict] = Field(
        default_factory=list,
        description="Scenario dicts with name, shocks",
    )
    returns: list[Decimal] = Field(
        default_factory=list,
        description="Historical return series for VaR/CVaR",
    )


class AssessRiskResponse(BaseModel):
    """Risk analysis results."""

    content: str = Field(description="Human-readable risk report")


# --- Adversarial ---


class ChallengeThesisRequest(BaseModel):
    """Request to adversarially challenge claims or a thesis."""

    claims: list[str] = Field(
        default_factory=list,
        description="Claims to challenge. If empty, uses prompt text.",
    )
    prompt: str = Field(default="", description="Free-text thesis to challenge")


class ChallengeThesisResponse(BaseModel):
    """Adversarial challenge results."""

    content: str = Field(description="Human-readable challenge report")
    conviction_score: str = Field(description="Final conviction score")
    counter_count: int = Field(description="Number of counter-arguments generated")
    blind_spot_count: int = Field(description="Number of blind spots identified")


# --- Pipeline ---


class TaskDefinition(BaseModel):
    """Definition for a single pipeline task."""

    agent_name: str = Field(min_length=1, description="Agent name to execute")
    prompt: str = Field(default="", description="Prompt text passed to the agent")
    kwargs: dict[str, object] = Field(
        default_factory=dict,
        description="Additional keyword arguments passed to the agent",
    )
    priority: int = Field(default=0, description="Scheduling priority for the task")
    depends_on: list[str] = Field(
        default_factory=list,
        description="Task IDs that must complete before this task runs",
    )
    task_id: str = Field(default="", description="Unique task identifier")


class RunPipelineRequest(BaseModel):
    """Request to run a multi-agent orchestrated pipeline."""

    tasks: list[TaskDefinition] = Field(
        description="Task definitions for the pipeline",
    )


class RunPipelineResponse(BaseModel):
    """Pipeline execution results."""

    results: list[dict] = Field(description="Per-task results")
    total_duration_ms: int = Field(description="Total pipeline duration")
    successful: int = Field(description="Number of successful tasks")
    failed: int = Field(description="Number of failed tasks")
    memo: dict | None = Field(default=None, description="Generated research memo if requested")


# --- Research Digest ---


class RunDigestRequest(BaseModel):
    """Request to run the research digest pipeline."""

    tickers: list[str] = Field(description="Watchlist tickers")
    lookback_days: int = Field(default=7, description="Days of data to consider")
    alert_threshold: Decimal = Field(default=Decimal("0.5"), description="Materiality threshold")
    sources: list[dict] = Field(
        default_factory=list,
        description="Pre-loaded DataSource dicts. If empty, pipeline runs with no sources.",
    )


class RunDigestResponse(BaseModel):
    """Research digest results."""

    ticker_count: int = Field(description="Number of tickers processed")
    entry_count: int = Field(description="Number of digest entries")
    alert_count: int = Field(description="Number of alerts generated")
    material_count: int = Field(description="Number of material entries")
    content: str = Field(description="Human-readable digest summary")
