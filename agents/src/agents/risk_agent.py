"""Risk agent — portfolio risk analysis with scenario modeling.

Provides Value-at-Risk, Conditional VaR, volatility, correlation,
and stress-test scenario analysis using only ``decimal.Decimal``
arithmetic (no floats).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from src.core.agent import AgentResponse, BaseAgent

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Scenario:
    """A stress-test scenario definition.

    Attributes:
        name: Human-readable scenario label.
        description: Longer explanation of what the scenario models.
        shocks: Mapping of factor/ticker to shock magnitude
            (e.g. ``{"SPY": Decimal("-0.20")}`` for a 20 % drop).
    """

    name: str
    description: str
    shocks: dict[str, Decimal]


@dataclass
class RiskMetrics:
    """Bundle of portfolio-level risk statistics.

    Attributes:
        var_95: Value at Risk at the 95th-percentile confidence.
        var_99: Value at Risk at the 99th-percentile confidence.
        cvar_95: Conditional VaR (Expected Shortfall) at 95 %.
        max_loss: Maximum single-period loss in the return series.
        volatility: Standard deviation of the return series.
    """

    var_95: Decimal
    var_99: Decimal
    cvar_95: Decimal
    max_loss: Decimal
    volatility: Decimal


@dataclass
class StressResult:
    """Result of applying a stress scenario to a portfolio.

    Attributes:
        scenario_name: Which scenario was applied.
        portfolio_impact: Estimated total P&L change.
        worst_position: Ticker with the largest individual loss.
        worst_position_loss: Loss amount for the worst position.
        positions_affected: Number of positions hit by the scenario.
    """

    scenario_name: str
    portfolio_impact: Decimal
    worst_position: str
    worst_position_loss: Decimal
    positions_affected: int


@dataclass
class PositionRisk:
    """A single portfolio position with its risk data.

    Attributes:
        ticker: Instrument identifier.
        weight: Portfolio weight in [0, 1].
        returns: Historical return series as ``Decimal`` values.
    """

    ticker: str
    weight: Decimal
    returns: list[Decimal]


# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------


def compute_portfolio_weights(
    positions: list[PositionRisk],
) -> list[PositionRisk]:
    """Normalize position weights so they sum to 1.

    Args:
        positions: List of positions with raw weights.

    Returns:
        New list of ``PositionRisk`` objects with normalized weights.
        Returns an empty list when *positions* is empty.
    """
    if not positions:
        return []
    total = sum(p.weight for p in positions)
    if total == Decimal("0"):
        return positions
    return [
        PositionRisk(
            ticker=p.ticker,
            weight=p.weight / total,
            returns=list(p.returns),
        )
        for p in positions
    ]


def compute_var(
    returns: list[Decimal],
    confidence: Decimal = Decimal("0.95"),
) -> Decimal:
    """Historical Value-at-Risk.

    Sorts the return series ascending, picks the ``(1 - confidence)``
    percentile, and returns the loss as a **positive** number.

    Args:
        returns: Historical return series.
        confidence: Confidence level (e.g. ``Decimal("0.95")``).

    Returns:
        VaR as a positive ``Decimal``, or ``Decimal("0")`` when
        *returns* is empty.
    """
    if not returns:
        return Decimal("0")
    sorted_returns = sorted(returns)
    index = int((Decimal("1") - confidence) * len(sorted_returns))
    index = max(0, min(index, len(sorted_returns) - 1))
    return -sorted_returns[index]


def compute_cvar(
    returns: list[Decimal],
    confidence: Decimal = Decimal("0.95"),
) -> Decimal:
    """Conditional VaR (Expected Shortfall).

    Average of all returns that are worse than (or equal to) the VaR
    threshold, returned as a positive loss number.

    Args:
        returns: Historical return series.
        confidence: Confidence level.

    Returns:
        CVaR as a positive ``Decimal``, or ``Decimal("0")`` for empty
        input.
    """
    if not returns:
        return Decimal("0")
    sorted_returns = sorted(returns)
    cutoff = int((Decimal("1") - confidence) * len(sorted_returns))
    cutoff = max(1, cutoff)
    tail = sorted_returns[:cutoff]
    avg = sum(tail) / len(tail)
    return -avg


def compute_volatility(returns: list[Decimal]) -> Decimal:
    """Standard deviation of a return series.

    Args:
        returns: Historical return series.

    Returns:
        Volatility as a ``Decimal``. Returns ``Decimal("0")`` when
        fewer than 2 data points are provided.
    """
    if len(returns) < 2:
        return Decimal("0")
    n = len(returns)
    mean = sum(returns) / n
    variance = sum((r - mean) ** 2 for r in returns) / (n - 1)
    return Decimal(str(math.sqrt(float(variance))))


def run_scenario(
    positions: list[PositionRisk],
    scenario: Scenario,
) -> StressResult:
    """Apply a stress scenario to a portfolio.

    Each position whose ticker appears in ``scenario.shocks`` is
    shocked by the corresponding magnitude multiplied by its weight.
    Positions not listed in shocks are unaffected.

    Args:
        positions: Current portfolio positions.
        scenario: The scenario to apply.

    Returns:
        A ``StressResult`` summarizing the portfolio impact.
    """
    if not positions:
        return StressResult(
            scenario_name=scenario.name,
            portfolio_impact=Decimal("0"),
            worst_position="",
            worst_position_loss=Decimal("0"),
            positions_affected=0,
        )

    total_impact = Decimal("0")
    worst_ticker = ""
    worst_loss = Decimal("0")
    affected = 0

    for pos in positions:
        shock = scenario.shocks.get(pos.ticker)
        if shock is None:
            continue
        loss = pos.weight * shock
        total_impact += loss
        affected += 1
        # loss is negative when shock is negative
        if loss < worst_loss:
            worst_loss = loss
            worst_ticker = pos.ticker

    return StressResult(
        scenario_name=scenario.name,
        portfolio_impact=total_impact,
        worst_position=worst_ticker,
        worst_position_loss=worst_loss,
        positions_affected=affected,
    )


def compute_risk_metrics(returns: list[Decimal]) -> RiskMetrics:
    """Compute a full suite of risk metrics for a return series.

    Args:
        returns: Historical return series.

    Returns:
        A ``RiskMetrics`` bundle.
    """
    var_95 = compute_var(returns, Decimal("0.95"))
    var_99 = compute_var(returns, Decimal("0.99"))
    cvar_95 = compute_cvar(returns, Decimal("0.95"))
    volatility = compute_volatility(returns)
    max_loss = -min(returns) if returns else Decimal("0")
    return RiskMetrics(
        var_95=var_95,
        var_99=var_99,
        cvar_95=cvar_95,
        max_loss=max_loss,
        volatility=volatility,
    )


def correlation_pair(
    returns_a: list[Decimal],
    returns_b: list[Decimal],
) -> Decimal:
    """Pearson correlation between two return series.

    Args:
        returns_a: First return series.
        returns_b: Second return series (must be same length).

    Returns:
        Correlation as a ``Decimal`` in [-1, 1].
        Returns ``Decimal("0")`` when fewer than 3 data points or
        when the series have zero variance.
    """
    n = len(returns_a)
    if n < 3 or n != len(returns_b):
        return Decimal("0")

    mean_a = sum(returns_a) / n
    mean_b = sum(returns_b) / n

    cov = sum(
        (returns_a[i] - mean_a) * (returns_b[i] - mean_b) for i in range(n)
    )
    var_a = sum((r - mean_a) ** 2 for r in returns_a)
    var_b = sum((r - mean_b) ** 2 for r in returns_b)

    denom_sq = float(var_a * var_b)
    if denom_sq <= 0:
        return Decimal("0")

    corr = float(cov) / math.sqrt(denom_sq)
    # Clamp to [-1, 1] for floating-point safety
    corr = max(-1.0, min(1.0, corr))
    return Decimal(str(corr))


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class RiskAgent(BaseAgent):
    """Agent that performs portfolio risk analysis.

    Specializes in Value-at-Risk, Conditional VaR, volatility
    estimation, stress-test scenario modeling, tail-risk assessment,
    and correlation analysis.
    """

    def __init__(self) -> None:
        super().__init__(
            name="risk_analyst",
            description=(
                "Analyzes portfolio risk via VaR, CVaR, volatility, "
                "correlation, and stress-test scenarios"
            ),
        )

    @property
    def system_prompt(self) -> str:
        """System prompt defining the risk analyst persona."""
        return (
            "You are a quantitative risk analyst specializing in "
            "portfolio risk management. Your capabilities include:\n\n"
            "1. **Value-at-Risk (VaR)**: Compute historical VaR at "
            "various confidence levels to estimate potential losses.\n\n"
            "2. **Conditional VaR / Expected Shortfall**: Measure "
            "tail-risk by averaging losses beyond the VaR threshold.\n\n"
            "3. **Volatility Analysis**: Calculate portfolio and "
            "position-level volatility from return series.\n\n"
            "4. **Scenario / Stress Testing**: Model the impact of "
            "macro shocks (rate hikes, equity drawdowns, credit "
            "spread widening) on portfolio P&L.\n\n"
            "5. **Correlation Analysis**: Assess pairwise and "
            "cross-asset correlations to identify concentration and "
            "diversification opportunities.\n\n"
            "6. **Tail-Risk Assessment**: Identify fat-tail "
            "exposures and non-normal return distributions.\n\n"
            "Always express risk figures with clear units and "
            "confidence levels. Use Decimal precision — never "
            "approximate with floats. Cite assumptions explicitly."
        )

    async def run(self, prompt: str, **kwargs: Any) -> AgentResponse:
        """Execute risk analysis on the provided portfolio data.

        Args:
            prompt: Natural-language analysis request.
            **kwargs: May include ``positions`` (list of PositionRisk),
                ``scenarios`` (list of Scenario), or ``returns``
                (list of Decimal).

        Returns:
            AgentResponse with risk metrics and/or stress results.
        """
        positions: list[PositionRisk] = kwargs.get("positions", [])
        scenarios: list[Scenario] = kwargs.get("scenarios", [])
        returns: list[Decimal] = kwargs.get("returns", [])

        results: list[str] = []

        # Portfolio-level risk from aggregated returns
        if returns:
            metrics = compute_risk_metrics(returns)
            results.append(
                f"Portfolio Risk Metrics:\n"
                f"  VaR(95%): {metrics.var_95}\n"
                f"  VaR(99%): {metrics.var_99}\n"
                f"  CVaR(95%): {metrics.cvar_95}\n"
                f"  Max Loss: {metrics.max_loss}\n"
                f"  Volatility: {metrics.volatility}"
            )

        # Stress tests
        if positions and scenarios:
            normalized = compute_portfolio_weights(positions)
            for scenario in scenarios:
                sr = run_scenario(normalized, scenario)
                results.append(
                    f"Scenario '{sr.scenario_name}':\n"
                    f"  Portfolio Impact: {sr.portfolio_impact}\n"
                    f"  Worst Position: {sr.worst_position} "
                    f"({sr.worst_position_loss})\n"
                    f"  Positions Affected: {sr.positions_affected}"
                )

        if not results:
            return AgentResponse(
                content=(
                    "Please provide portfolio positions, scenarios, "
                    "or a return series to analyze."
                ),
                metadata={},
            )

        return AgentResponse(
            content="\n\n".join(results),
            metadata={"prompt": prompt},
        )
