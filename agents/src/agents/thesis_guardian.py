"""Thesis guardian agent — monitors investment theses for broken assumptions.

Evaluates investment thesis assumptions against incoming data and flags
when underlying conditions weaken or break, triggering alerts at
appropriate severity levels.
"""


import re
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Any

from src.core.agent import AgentResponse, BaseAgent


@dataclass
class Assumption:
    """A single testable assumption underlying an investment thesis."""

    description: str
    metric: str  # e.g., "revenue_growth", "market_share", "margin"
    condition: str  # e.g., ">5%", "<20", "positive"
    current_value: Decimal | None = None
    status: str = "UNTESTED"  # UNTESTED, HOLDING, WEAKENED, BROKEN


@dataclass
class Thesis:
    """An investment thesis with its underlying assumptions."""

    ticker: str
    statement: str
    direction: str  # "LONG" or "SHORT"
    assumptions: list[Assumption]
    status: str = "ACTIVE"  # ACTIVE, WEAKENED, INVALIDATED
    created_date: str = ""  # ISO date


@dataclass
class ThesisAlert:
    """Alert generated when an assumption's status changes."""

    thesis_ticker: str
    assumption_description: str
    severity: str  # "INFO", "WARNING", "CRITICAL"
    message: str
    old_status: str
    new_status: str


# Pattern for numeric comparison conditions like ">5", "<=20.5", ">=0"
_COMPARISON_RE = re.compile(r"^([<>]=?)\s*(-?\d+\.?\d*)\s*%?$")


def evaluate_condition(condition: str, value: Decimal) -> bool:
    """Parse and evaluate a condition string against a value.

    Args:
        condition: Condition like ">5", "<20", ">=0", "positive", "negative".
        value: The decimal value to test.

    Returns:
        True if the condition holds for the given value.
    """
    stripped = condition.strip()
    lower = stripped.lower()

    if lower == "positive":
        return value > 0
    if lower == "negative":
        return value < 0

    match = _COMPARISON_RE.match(stripped)
    if not match:
        return False

    operator, threshold_str = match.group(1), match.group(2)
    threshold = Decimal(threshold_str)

    if operator == ">":
        return value > threshold
    if operator == "<":
        return value < threshold
    if operator == ">=":
        return value >= threshold
    if operator == "<=":
        return value <= threshold

    return False  # pragma: no cover


def _is_borderline(condition: str, value: Decimal) -> bool:
    """Check whether a value is within 10% of the condition threshold.

    Args:
        condition: The condition string.
        value: The decimal value to check.

    Returns:
        True if the value is borderline (within 10% of the threshold).
    """
    stripped = condition.strip().lower()
    if stripped in ("positive", "negative"):
        return False

    match = _COMPARISON_RE.match(condition.strip())
    if not match:
        return False

    threshold = Decimal(match.group(2))
    if threshold == 0:
        return False

    distance = abs(value - threshold)
    margin = abs(threshold) * Decimal("0.10")
    return distance <= margin


def evaluate_assumption(assumption: Assumption, new_value: Decimal) -> Assumption:
    """Evaluate an assumption against a new data point.

    Args:
        assumption: The assumption to evaluate.
        new_value: The latest observed value for the assumption's metric.

    Returns:
        A new Assumption with updated current_value and status.
    """
    holds = evaluate_condition(assumption.condition, new_value)

    if holds:
        if _is_borderline(assumption.condition, new_value):
            status = "WEAKENED"
        else:
            status = "HOLDING"
    else:
        if _is_borderline(assumption.condition, new_value):
            status = "WEAKENED"
        else:
            status = "BROKEN"

    return replace(assumption, current_value=new_value, status=status)


def severity_for_status_change(old_status: str, new_status: str) -> str:
    """Determine alert severity for an assumption status transition.

    Args:
        old_status: Previous assumption status.
        new_status: New assumption status.

    Returns:
        Severity level: "CRITICAL", "WARNING", or "INFO".
    """
    if old_status == "HOLDING" and new_status == "BROKEN":
        return "CRITICAL"
    if old_status == "HOLDING" and new_status == "WEAKENED":
        return "WARNING"
    if old_status == "UNTESTED" and new_status == "BROKEN":
        return "WARNING"
    return "INFO"


def check_thesis(thesis: Thesis) -> tuple[Thesis, list[ThesisAlert]]:
    """Evaluate all assumptions in a thesis and generate alerts.

    Assumptions must already have current_value set (via evaluate_assumption)
    before calling this function. This function reads each assumption's status
    and derives the overall thesis status plus any alerts.

    Args:
        thesis: The thesis to check.

    Returns:
        Tuple of (updated thesis with new status, list of generated alerts).
    """
    alerts: list[ThesisAlert] = []
    statuses: list[str] = []

    for assumption in thesis.assumptions:
        statuses.append(assumption.status)

    # Derive thesis-level status
    if any(s == "BROKEN" for s in statuses):
        thesis_status = "INVALIDATED"
    elif any(s == "WEAKENED" for s in statuses):
        thesis_status = "WEAKENED"
    else:
        thesis_status = "ACTIVE"

    # Generate alerts for non-trivial status changes
    for assumption in thesis.assumptions:
        old = "UNTESTED"
        new = assumption.status
        if old == new:
            continue
        severity = severity_for_status_change(old, new)
        alerts.append(ThesisAlert(
            thesis_ticker=thesis.ticker,
            assumption_description=assumption.description,
            severity=severity,
            message=(
                f"Assumption '{assumption.description}' changed "
                f"from {old} to {new}"
            ),
            old_status=old,
            new_status=new,
        ))

    updated_thesis = replace(thesis, status=thesis_status)
    return updated_thesis, alerts


class ThesisGuardianAgent(BaseAgent):
    """Agent that monitors investment theses for broken assumptions.

    Tracks a portfolio of investment theses, evaluates their underlying
    assumptions against new data, and generates alerts when assumptions
    weaken or break.
    """

    def __init__(self) -> None:
        super().__init__(
            name="thesis_guardian",
            description=(
                "Monitors investment theses and flags when underlying "
                "assumptions are broken by new data"
            ),
        )
        self._theses: list[Thesis] = []

    @property
    def system_prompt(self) -> str:
        """System prompt for investment thesis monitoring."""
        return (
            "You are an investment thesis guardian with deep expertise "
            "in fundamental analysis and risk management. Your role is to:\n\n"
            "1. **Thesis Tracking**: Maintain a portfolio of investment "
            "theses, each with clearly defined assumptions that can be "
            "tested against observable data.\n\n"
            "2. **Assumption Monitoring**: Continuously evaluate whether "
            "the key assumptions underlying each thesis still hold — "
            "revenue growth targets, margin expectations, market share "
            "trends, and competitive dynamics.\n\n"
            "3. **Alert Generation**: Flag when assumptions weaken or "
            "break, with severity levels reflecting the impact on the "
            "overall thesis. CRITICAL alerts demand immediate attention; "
            "WARNING alerts suggest thesis is under pressure.\n\n"
            "4. **Thesis Invalidation**: Determine when accumulated "
            "broken assumptions invalidate the entire investment thesis, "
            "requiring position review or exit.\n\n"
            "5. **Evidence-Based Updates**: Ground every status change "
            "in observable metrics — never speculate without data.\n\n"
            "Output structured analysis with:\n"
            "- Current thesis status and assumption health\n"
            "- Alerts with severity and supporting evidence\n"
            "- Recommended actions for weakened or invalidated theses\n"
            "- Historical assumption tracking over time"
        )

    async def run(self, prompt: str, **kwargs: Any) -> AgentResponse:
        """Execute thesis guardian analysis.

        Args:
            prompt: Analysis request or thesis to evaluate.
            **kwargs: May include 'theses' as list of Thesis objects,
                'data' as dict mapping metrics to Decimal values.

        Returns:
            AgentResponse with thesis evaluation results.
        """
        theses: list[Thesis] = kwargs.get("theses", self._theses)
        data: dict[str, Decimal] = kwargs.get("data", {})

        if not theses:
            return AgentResponse(
                content=(
                    "No theses to monitor. Provide theses via:\n"
                    "  agent.run(prompt, theses=[Thesis(...)])"
                ),
                metadata={"error": "no_theses"},
            )

        all_alerts: list[ThesisAlert] = []
        updated_theses: list[Thesis] = []

        for thesis in theses:
            updated_assumptions: list[Assumption] = []
            for assumption in thesis.assumptions:
                if assumption.metric in data:
                    updated = evaluate_assumption(
                        assumption, data[assumption.metric]
                    )
                    updated_assumptions.append(updated)
                else:
                    updated_assumptions.append(assumption)

            updated_thesis = replace(thesis, assumptions=updated_assumptions)
            checked, alerts = check_thesis(updated_thesis)
            updated_theses.append(checked)
            all_alerts.extend(alerts)

        lines = ["## Thesis Guardian Report\n"]
        for t in updated_theses:
            lines.append(f"### {t.ticker} ({t.direction}) — {t.status}")
            lines.append(f"  {t.statement}")
            for a in t.assumptions:
                val_str = str(a.current_value) if a.current_value is not None else "N/A"
                lines.append(
                    f"  - [{a.status}] {a.description}: "
                    f"{a.metric} {a.condition} (current: {val_str})"
                )

        if all_alerts:
            lines.append("\n### Alerts")
            for alert in all_alerts:
                lines.append(
                    f"  - [{alert.severity}] {alert.thesis_ticker}: "
                    f"{alert.message}"
                )

        self._theses = updated_theses

        return AgentResponse(
            content="\n".join(lines),
            metadata={
                "theses_checked": len(updated_theses),
                "alerts_generated": len(all_alerts),
                "critical_alerts": sum(
                    1 for a in all_alerts if a.severity == "CRITICAL"
                ),
            },
        )
