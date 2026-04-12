"""Agent invocation service — maps typed contracts to agent run() calls.

Handles contract validation, kwargs mapping, and response normalization.
"""

from typing import Any

from src.agents.adversarial import AdversarialAgent
from src.agents.earnings_interpreter import EarningsInterpreterAgent
from src.agents.filing_analyst import FilingAnalystAgent
from src.agents.macro_regime import MacroRegimeAgent
from src.agents.quant_signal import QuantSignalAgent
from src.agents.risk_agent import RiskAgent
from src.agents.thesis_guardian import ThesisGuardianAgent
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
    SearchFilingsRequest,
    SearchFilingsResponse,
)
from src.core.agent import AgentResponse, BaseAgent


def _metadata_get(metadata: dict[str, Any], key: str, default: Any = "") -> Any:
    """Safely get a metadata value with a default."""
    return metadata.get(key, default)


class AgentService:
    """Invokes agents with validated contracts.

    Each method:
    1. Validates the Pydantic request
    2. Maps fields to agent kwargs
    3. Runs the agent
    4. Normalizes the response into a typed contract
    """

    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}

    def _get_or_create(self, agent_cls: type[BaseAgent], *args: Any) -> BaseAgent:
        """Cache agent instances by class name."""
        key = agent_cls.__name__
        if key not in self._agents:
            self._agents[key] = agent_cls(*args)
        return self._agents[key]

    async def analyze_earnings(
        self, request: AnalyzeEarningsRequest
    ) -> AnalyzeEarningsResponse:
        """Analyze an earnings transcript."""
        agent = self._get_or_create(EarningsInterpreterAgent)
        prompt = request.ticker or "Analyze this transcript"
        response: AgentResponse = await agent.run(
            prompt, transcript=request.transcript
        )
        return AnalyzeEarningsResponse(
            content=response.content,
            tone=_metadata_get(response.metadata, "tone"),
            net_sentiment=float(_metadata_get(response.metadata, "net_sentiment", 0)),
            confidence=str(_metadata_get(response.metadata, "confidence", "")),
            guidance_direction=_metadata_get(response.metadata, "guidance_direction"),
            guidance_count=int(_metadata_get(response.metadata, "guidance_count", 0)),
            key_phrase_count=int(_metadata_get(response.metadata, "key_phrase_count", 0)),
        )

    async def classify_macro(
        self, request: ClassifyMacroRequest
    ) -> ClassifyMacroResponse:
        """Classify the macro regime."""
        agent = self._get_or_create(MacroRegimeAgent)
        kwargs: dict[str, Any] = {}
        if request.api_key:
            kwargs["api_key"] = request.api_key
        if request.indicators:
            kwargs["indicators"] = request.indicators
        response = await agent.run("Classify current macro regime", **kwargs)
        return ClassifyMacroResponse(
            content=response.content,
            regime=_metadata_get(response.metadata, "regime"),
            indicators_fetched=int(
                _metadata_get(response.metadata, "indicators_fetched", 0)
            ),
            indicators_with_data=int(
                _metadata_get(response.metadata, "indicators_with_data", 0)
            ),
        )

    async def search_filings(
        self, request: SearchFilingsRequest
    ) -> SearchFilingsResponse:
        """Search SEC filings for a company."""
        agent = self._get_or_create(FilingAnalystAgent)
        kwargs: dict[str, Any] = {"form_type": request.form_type}
        if request.ticker:
            kwargs["ticker"] = request.ticker
        if request.cik:
            kwargs["cik"] = request.cik
        query_target = request.ticker or request.cik
        prompt = f"Search filings for {query_target}" if query_target else ""
        response = await agent.run(prompt, **kwargs)
        return SearchFilingsResponse(
            content=response.content,
            cik=str(_metadata_get(response.metadata, "cik", "")),
            form_type=str(_metadata_get(response.metadata, "form_type", "")),
            filing_count=int(_metadata_get(response.metadata, "filing_count", 0)),
        )

    async def generate_signals(
        self, request: GenerateSignalsRequest
    ) -> GenerateSignalsResponse:
        """Generate composite quant signals."""
        agent = self._get_or_create(QuantSignalAgent)
        kwargs: dict[str, Any] = {
            "method": request.method,
        }
        if request.signals:
            kwargs["signals"] = request.signals
        if request.sentiment is not None:
            kwargs["sentiment"] = request.sentiment
        if request.regime:
            kwargs["regime"] = request.regime
        if request.direction:
            kwargs["direction"] = request.direction
        if request.source:
            kwargs["source"] = request.source
        response = await agent.run("Generate composite signals", **kwargs)
        return GenerateSignalsResponse(
            content=response.content,
            agent=_metadata_get(response.metadata, "agent", "quant_signal"),
            composite=_metadata_get(response.metadata, "composite", {}),
            signals=_metadata_get(response.metadata, "signals", []),
        )

    async def evaluate_thesis(
        self, request: EvaluateThesisRequest
    ) -> EvaluateThesisResponse:
        """Evaluate investment theses against observed data."""
        agent = self._get_or_create(ThesisGuardianAgent)
        response = await agent.run(
            "Evaluate theses",
            theses=request.theses,
            data=request.data,
        )
        return EvaluateThesisResponse(
            content=response.content,
            theses_checked=int(
                _metadata_get(response.metadata, "theses_checked", 0)
            ),
            alerts_generated=int(
                _metadata_get(response.metadata, "alerts_generated", 0)
            ),
            critical_alerts=int(
                _metadata_get(response.metadata, "critical_alerts", 0)
            ),
        )

    async def assess_risk(self, request: AssessRiskRequest) -> AssessRiskResponse:
        """Run risk analysis."""
        agent = self._get_or_create(RiskAgent)
        kwargs: dict[str, Any] = {}
        if request.positions:
            kwargs["positions"] = request.positions
        if request.scenarios:
            kwargs["scenarios"] = request.scenarios
        if request.returns:
            kwargs["returns"] = request.returns
        response = await agent.run("Assess portfolio risk", **kwargs)
        return AssessRiskResponse(content=response.content)

    async def challenge_thesis(
        self, request: ChallengeThesisRequest
    ) -> ChallengeThesisResponse:
        """Adversarially challenge a thesis."""
        agent = self._get_or_create(AdversarialAgent)
        kwargs: dict[str, Any] = {}
        if request.claims:
            kwargs["claims"] = request.claims
        prompt = request.prompt or "Challenge these claims"
        response = await agent.run(prompt, **kwargs)
        return ChallengeThesisResponse(
            content=response.content,
            conviction_score=str(
                _metadata_get(response.metadata, "conviction_score", "")
            ),
            counter_count=int(
                _metadata_get(response.metadata, "counter_count", 0)
            ),
            blind_spot_count=int(
                _metadata_get(response.metadata, "blind_spot_count", 0)
            ),
        )
