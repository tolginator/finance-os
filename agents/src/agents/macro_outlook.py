"""Macro outlook agent — forward-looking asset-class tilts.

Synthesizes a pre-computed multi-dimensional regime classification into
policy-bounded asset-class tilt recommendations.  The agent is
deterministic: it delegates to ``outlook_service.compute_tilts`` for
tilt computation — no LLM calls are made.
"""

from typing import Any

from src.application.contracts.outlook import MacroOutlookResponse
from src.application.contracts.policy import InvestmentPolicy
from src.application.contracts.regime import MacroRegimeReport
from src.application.services.outlook_service import compute_tilts
from src.core.agent import AgentResponse, BaseAgent


class MacroOutlookAgent(BaseAgent):
    """Agent that produces forward-looking asset-class tilts.

    Requires a ``MacroRegimeReport`` (from RegimeService) and an
    ``InvestmentPolicy`` to compute tilts.  Returns structured output
    suitable for portfolio rebalancing decisions.
    """

    def __init__(self) -> None:
        super().__init__(
            name="macro_outlook",
            description=(
                "Produces forward-looking asset-class tilts bounded "
                "by investment policy, driven by macro regime"
            ),
        )

    @property
    def system_prompt(self) -> str:
        """System prompt for macro outlook analysis."""
        return (
            "You are a macro strategist who translates economic regime "
            "analysis into actionable portfolio tilts for a wealthy family. "
            "Your recommendations:\n\n"
            "1. Are bounded by the investment policy (IPS) — tilts never "
            "exceed policy min/max bands.\n"
            "2. Are budget-neutral — overweights are funded by "
            "underweights; the portfolio stays fully invested.\n"
            "3. Are confidence-weighted — lower regime confidence means "
            "smaller tilts toward the policy target.\n"
            "4. Consider all dimensions: growth cycle, rate environment, "
            "and inflation regime.\n"
            "5. Prioritize capital preservation while capturing moderate "
            "growth opportunities."
        )

    async def run(self, prompt: str, **kwargs: Any) -> AgentResponse:
        """Execute macro outlook analysis.

        Args:
            prompt: Analysis request.
            **kwargs: Must include:
                - ``regime_report``: MacroRegimeReport instance
                - ``policy``: InvestmentPolicy instance

        Returns:
            AgentResponse with tilts and outlook narrative.
        """
        regime_report: MacroRegimeReport | None = kwargs.get("regime_report")
        policy: InvestmentPolicy | None = kwargs.get("policy")

        if regime_report is None:
            return AgentResponse(
                content="Regime report required for macro outlook.",
                metadata={"error": "missing_regime_report"},
            )
        if policy is None:
            return AgentResponse(
                content="Investment policy required for macro outlook.",
                metadata={"error": "missing_policy"},
            )

        # Coerce dicts (e.g. from orchestrator/pipeline) into models
        if isinstance(regime_report, dict):
            regime_report = MacroRegimeReport.model_validate(regime_report)
        if isinstance(policy, dict):
            policy = InvestmentPolicy.model_validate(policy)

        outlook = compute_tilts(regime_report, policy)
        dashboard = _format_outlook(outlook)

        return AgentResponse(
            content=dashboard,
            metadata={
                "tilts": len(outlook.tilts),
                "active_tilts": len(outlook.active_tilts),
                "confidence": str(outlook.confidence),
                "regime_summary": outlook.regime_summary,
                "_outlook": outlook.model_dump(mode="json"),
            },
        )


def _format_outlook(outlook: MacroOutlookResponse) -> str:
    """Format the outlook into a human-readable dashboard."""
    lines = [
        "# Macro Outlook",
        "",
        f"**Regime**: {outlook.regime_summary}",
        f"**Confidence**: {outlook.confidence:.0%}",
        "",
        "## Asset-Class Tilts",
        "",
        "| Asset Class | Target | Recommended | Tilt | Direction |",
        "|---|---|---|---|---|",
    ]
    for t in outlook.tilts:
        sign = "+" if t.tilt > 0 else ""
        lines.append(
            f"| {t.asset_class.value} | {t.target_weight:.1%} "
            f"| {t.recommended_weight:.1%} | {sign}{t.tilt:.2%} "
            f"| {t.direction.value} |"
        )

    active = outlook.active_tilts
    if active:
        lines.extend(["", "## Key Moves", ""])
        for t in active:
            lines.append(f"- **{t.asset_class.value}**: {t.rationale}")

    return "\n".join(lines)
