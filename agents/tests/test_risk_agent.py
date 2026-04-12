"""Tests for the risk agent module."""


from decimal import Decimal

import pytest

from src.agents.risk_agent import (
    PositionRisk,
    RiskAgent,
    Scenario,
    compute_cvar,
    compute_portfolio_weights,
    compute_risk_metrics,
    compute_var,
    compute_volatility,
    correlation_pair,
    run_scenario,
)
from src.core.agent import BaseAgent

# ---------------------------------------------------------------------------
# compute_var
# ---------------------------------------------------------------------------


class TestComputeVar:
    """Tests for historical VaR calculation."""

    def test_known_series(self) -> None:
        """VaR at 95% on a 20-element series picks the (1-conf) percentile."""
        returns = [Decimal(str(x)) for x in range(-10, 10)]  # -10 .. 9
        var = compute_var(returns, Decimal("0.95"))
        # index = int(0.05 * 20) = 1 → sorted[1] = -9 → VaR = 9
        assert var == Decimal("9")

    def test_empty_returns(self) -> None:
        """Empty return series yields zero."""
        assert compute_var([], Decimal("0.95")) == Decimal("0")

    def test_identical_returns(self) -> None:
        """All identical returns → VaR reflects no variation in losses."""
        returns = [Decimal("0")] * 20
        var = compute_var(returns, Decimal("0.95"))
        assert var == Decimal("0")


# ---------------------------------------------------------------------------
# compute_cvar
# ---------------------------------------------------------------------------


class TestComputeCvar:
    """Tests for Conditional VaR (Expected Shortfall)."""

    def test_tail_average(self) -> None:
        """CVaR should average losses in the tail."""
        returns = [Decimal(str(x)) for x in range(-10, 10)]
        cvar = compute_cvar(returns, Decimal("0.95"))
        # With 20 returns, 5% tail = 1 element = the worst return (-10)
        assert cvar == Decimal("10")

    def test_empty_returns(self) -> None:
        """Empty series yields zero."""
        assert compute_cvar([]) == Decimal("0")


# ---------------------------------------------------------------------------
# compute_volatility
# ---------------------------------------------------------------------------


class TestComputeVolatility:
    """Tests for return-series volatility."""

    def test_known_series(self) -> None:
        """Volatility of [1, -1, 1, -1] is known analytically."""
        returns = [Decimal("1"), Decimal("-1"), Decimal("1"), Decimal("-1")]
        vol = compute_volatility(returns)
        # std dev with ddof=1: sqrt(4/3) ≈ 1.1547...
        expected = Decimal("1.1547005383792517")
        assert abs(vol - expected) < Decimal("0.0001")

    def test_fewer_than_two(self) -> None:
        """Fewer than 2 data points yields zero."""
        assert compute_volatility([]) == Decimal("0")
        assert compute_volatility([Decimal("5")]) == Decimal("0")


# ---------------------------------------------------------------------------
# run_scenario
# ---------------------------------------------------------------------------


class TestRunScenario:
    """Tests for stress-test scenario application."""

    @pytest.fixture()
    def positions(self) -> list[PositionRisk]:
        """Sample two-position portfolio."""
        return [
            PositionRisk(
                ticker="SPY",
                weight=Decimal("0.6"),
                returns=[],
            ),
            PositionRisk(
                ticker="TLT",
                weight=Decimal("0.4"),
                returns=[],
            ),
        ]

    @pytest.fixture()
    def crash_scenario(self) -> Scenario:
        """Equity crash: SPY drops 20%."""
        return Scenario(
            name="equity_crash",
            description="Broad equity sell-off",
            shocks={"SPY": Decimal("-0.20")},
        )

    def test_shock_applied(
        self,
        positions: list[PositionRisk],
        crash_scenario: Scenario,
    ) -> None:
        """Portfolio impact equals weight × shock for affected positions."""
        result = run_scenario(positions, crash_scenario)
        expected_impact = Decimal("0.6") * Decimal("-0.20")
        assert result.portfolio_impact == expected_impact
        assert result.positions_affected == 1

    def test_worst_position(
        self,
        positions: list[PositionRisk],
        crash_scenario: Scenario,
    ) -> None:
        """Worst position should be SPY after the equity crash."""
        result = run_scenario(positions, crash_scenario)
        assert result.worst_position == "SPY"
        assert result.worst_position_loss < Decimal("0")

    def test_unaffected_position(
        self,
        positions: list[PositionRisk],
        crash_scenario: Scenario,
    ) -> None:
        """TLT is not in shocks and should not contribute to impact."""
        result = run_scenario(positions, crash_scenario)
        # Only SPY is affected, so impact is purely from SPY
        assert result.portfolio_impact == Decimal("0.6") * Decimal("-0.20")

    def test_empty_positions(self, crash_scenario: Scenario) -> None:
        """Empty portfolio yields zero impact."""
        result = run_scenario([], crash_scenario)
        assert result.portfolio_impact == Decimal("0")
        assert result.positions_affected == 0


# ---------------------------------------------------------------------------
# correlation_pair
# ---------------------------------------------------------------------------


class TestCorrelationPair:
    """Tests for Pearson correlation."""

    def test_perfectly_correlated(self) -> None:
        """Identical series should correlate at 1."""
        series = [Decimal(str(i)) for i in range(10)]
        corr = correlation_pair(series, series)
        assert abs(corr - Decimal("1")) < Decimal("0.0001")

    def test_insufficient_data(self) -> None:
        """Fewer than 3 data points returns zero."""
        a = [Decimal("1"), Decimal("2")]
        b = [Decimal("3"), Decimal("4")]
        assert correlation_pair(a, b) == Decimal("0")

    def test_negatively_correlated(self) -> None:
        """Opposite series should correlate at -1."""
        a = [Decimal(str(i)) for i in range(10)]
        b = [Decimal(str(-i)) for i in range(10)]
        corr = correlation_pair(a, b)
        assert abs(corr - Decimal("-1")) < Decimal("0.0001")

    def test_zero_variance_returns_zero(self) -> None:
        """One series with all same values (zero variance) → correlation = 0."""
        a = [Decimal("1")] * 5
        b = [Decimal(str(i)) for i in range(5)]
        corr = correlation_pair(a, b)
        assert corr == Decimal("0")


# ---------------------------------------------------------------------------
# compute_risk_metrics
# ---------------------------------------------------------------------------


class TestComputeRiskMetrics:
    """Tests for the risk metrics bundle."""

    def test_bundles_correctly(self) -> None:
        """All sub-metrics should match their standalone computations."""
        returns = [Decimal(str(x)) for x in range(-10, 10)]
        metrics = compute_risk_metrics(returns)
        assert metrics.var_95 == compute_var(returns, Decimal("0.95"))
        assert metrics.var_99 == compute_var(returns, Decimal("0.99"))
        assert metrics.cvar_95 == compute_cvar(returns, Decimal("0.95"))
        assert metrics.volatility == compute_volatility(returns)
        assert metrics.max_loss == -min(returns)

    def test_empty_returns(self) -> None:
        """Empty series produces all-zero metrics."""
        metrics = compute_risk_metrics([])
        assert metrics.var_95 == Decimal("0")
        assert metrics.volatility == Decimal("0")
        assert metrics.max_loss == Decimal("0")


# ---------------------------------------------------------------------------
# compute_portfolio_weights
# ---------------------------------------------------------------------------


class TestComputePortfolioWeights:
    """Tests for weight normalization."""

    def test_normalization(self) -> None:
        """Weights should sum to 1 after normalization."""
        positions = [
            PositionRisk(ticker="A", weight=Decimal("3"), returns=[]),
            PositionRisk(ticker="B", weight=Decimal("7"), returns=[]),
        ]
        normalized = compute_portfolio_weights(positions)
        total = sum(p.weight for p in normalized)
        assert total == Decimal("1")
        assert normalized[0].weight == Decimal("0.3")

    def test_empty(self) -> None:
        """Empty list returns empty list."""
        assert compute_portfolio_weights([]) == []


# ---------------------------------------------------------------------------
# Agent class
# ---------------------------------------------------------------------------


class TestRiskAgent:
    """Tests for the RiskAgent class."""

    def test_is_base_agent(self) -> None:
        """RiskAgent should be a BaseAgent subclass."""
        agent = RiskAgent()
        assert isinstance(agent, BaseAgent)

    def test_system_prompt_mentions_risk(self) -> None:
        """System prompt should reference key risk concepts."""
        agent = RiskAgent()
        prompt = agent.system_prompt
        assert "VaR" in prompt or "Value-at-Risk" in prompt
        assert "tail" in prompt.lower() or "tail-risk" in prompt.lower()
        assert "correlation" in prompt.lower()
        assert "scenario" in prompt.lower() or "stress" in prompt.lower()
