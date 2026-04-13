"""Default agent registration — shared across CLI, MCP server, and future interfaces."""

from src.agents.adversarial import AdversarialAgent
from src.agents.earnings_interpreter import EarningsInterpreterAgent
from src.agents.filing_analyst import FilingAnalystAgent
from src.agents.macro_regime import MacroRegimeAgent
from src.agents.quant_signal import QuantSignalAgent
from src.agents.risk_agent import RiskAgent
from src.agents.thesis_guardian import ThesisGuardianAgent
from src.application.config import AppConfig
from src.application.services.pipeline_service import PipelineService
from src.core.agent import BaseAgent

AGENT_CATALOG: list[dict[str, str]] = [
    {"name": "macro_regime", "description": "Classifies macro regime from FRED indicators"},
    {"name": "filing_analyst", "description": "Searches and analyzes SEC filings (10-K/10-Q)"},
    {"name": "earnings_interpreter", "description": "Analyzes earnings call transcripts"},
    {"name": "quant_signal", "description": "Generates composite quantitative signals"},
    {"name": "thesis_guardian", "description": "Monitors investment theses against data"},
    {"name": "risk_analyst", "description": "Portfolio risk analysis (VaR, stress tests)"},
    {"name": "adversarial", "description": "Challenges investment theses adversarially"},
]


def create_all_agents(config: AppConfig | None = None) -> list[BaseAgent]:
    """Instantiate all available agents.

    Returns fresh instances each call to avoid cross-request state leakage.

    Args:
        config: Application config for agents that need secrets/settings.
            Created from environment if not provided.
    """
    cfg = config or AppConfig()
    return [
        MacroRegimeAgent(fred_api_key=cfg.fred_api_key),
        FilingAnalystAgent(),
        EarningsInterpreterAgent(),
        QuantSignalAgent(),
        ThesisGuardianAgent(),
        RiskAgent(),
        AdversarialAgent(),
    ]


def create_pipeline_service(config: AppConfig | None = None) -> PipelineService:
    """Create a PipelineService with all default agents registered."""
    service = PipelineService()
    for agent in create_all_agents(config):
        service.register_agent(agent)
    return service
