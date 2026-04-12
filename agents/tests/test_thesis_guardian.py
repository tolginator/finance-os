"""Tests for the thesis guardian agent."""

from decimal import Decimal

from src.agents.thesis_guardian import (
    Assumption,
    Thesis,
    ThesisGuardianAgent,
    check_thesis,
    evaluate_assumption,
    evaluate_condition,
    severity_for_status_change,
)
from src.core.agent import BaseAgent

# ---------------------------------------------------------------------------
# evaluate_condition
# ---------------------------------------------------------------------------


class TestEvaluateCondition:
    """Tests for condition parsing and evaluation."""

    def test_greater_than_holds(self) -> None:
        assert evaluate_condition(">5", Decimal("6")) is True

    def test_greater_than_fails(self) -> None:
        assert evaluate_condition(">5", Decimal("4")) is False

    def test_greater_than_boundary(self) -> None:
        assert evaluate_condition(">5", Decimal("5")) is False

    def test_less_than_holds(self) -> None:
        assert evaluate_condition("<20", Decimal("10")) is True

    def test_less_than_fails(self) -> None:
        assert evaluate_condition("<20", Decimal("25")) is False

    def test_less_than_boundary(self) -> None:
        assert evaluate_condition("<20", Decimal("20")) is False

    def test_greater_equal(self) -> None:
        assert evaluate_condition(">=0", Decimal("0")) is True

    def test_less_equal(self) -> None:
        assert evaluate_condition("<=10", Decimal("10")) is True

    def test_positive_holds(self) -> None:
        assert evaluate_condition("positive", Decimal("1")) is True

    def test_positive_fails(self) -> None:
        assert evaluate_condition("positive", Decimal("-1")) is False

    def test_negative_holds(self) -> None:
        assert evaluate_condition("negative", Decimal("-3")) is True

    def test_negative_fails(self) -> None:
        assert evaluate_condition("negative", Decimal("5")) is False

    def test_condition_with_percent_sign(self) -> None:
        assert evaluate_condition(">5%", Decimal("6")) is True

    def test_invalid_condition_returns_false(self) -> None:
        assert evaluate_condition("unknown", Decimal("5")) is False


# ---------------------------------------------------------------------------
# evaluate_assumption
# ---------------------------------------------------------------------------


class TestEvaluateAssumption:
    """Tests for assumption evaluation with status transitions."""

    def test_condition_holds_clearly(self) -> None:
        a = Assumption("Revenue growing", "revenue_growth", ">5")
        result = evaluate_assumption(a, Decimal("20"))
        assert result.status == "HOLDING"
        assert result.current_value == Decimal("20")

    def test_condition_broken_clearly(self) -> None:
        a = Assumption("Revenue growing", "revenue_growth", ">5")
        result = evaluate_assumption(a, Decimal("2"))
        assert result.status == "BROKEN"
        assert result.current_value == Decimal("2")

    def test_borderline_value_weakened(self) -> None:
        # 5.3 is within 10% of threshold 5 → borderline, condition holds → WEAKENED
        a = Assumption("Revenue growing", "revenue_growth", ">5")
        result = evaluate_assumption(a, Decimal("5.3"))
        assert result.status == "WEAKENED"

    def test_borderline_below_threshold_weakened(self) -> None:
        # 4.7 is within 10% of threshold 5 → borderline, condition fails → WEAKENED
        a = Assumption("Revenue growing", "revenue_growth", ">5")
        result = evaluate_assumption(a, Decimal("4.7"))
        assert result.status == "WEAKENED"

    def test_weakened_value_just_within_margin(self) -> None:
        """Value at exactly threshold + 10% margin boundary → WEAKENED."""
        # threshold=5, margin=0.5, value=5.5 → distance=0.5 == margin → borderline
        a = Assumption("Revenue growing", "revenue_growth", ">5")
        result = evaluate_assumption(a, Decimal("5.5"))
        assert result.status == "WEAKENED"
        assert result.current_value == Decimal("5.5")

    def test_original_assumption_unchanged(self) -> None:
        a = Assumption("Margin positive", "margin", "positive")
        result = evaluate_assumption(a, Decimal("10"))
        assert a.status == "UNTESTED"
        assert a.current_value is None
        assert result.status == "HOLDING"

    def test_positive_condition_holding(self) -> None:
        a = Assumption("Margin positive", "margin", "positive")
        result = evaluate_assumption(a, Decimal("10"))
        assert result.status == "HOLDING"

    def test_positive_condition_broken(self) -> None:
        a = Assumption("Margin positive", "margin", "positive")
        result = evaluate_assumption(a, Decimal("-5"))
        assert result.status == "BROKEN"


# ---------------------------------------------------------------------------
# check_thesis
# ---------------------------------------------------------------------------


class TestCheckThesis:
    """Tests for thesis-level evaluation."""

    def _make_thesis(self, assumptions: list[Assumption]) -> Thesis:
        return Thesis(
            ticker="AAPL",
            statement="Apple will grow services revenue",
            direction="LONG",
            assumptions=assumptions,
        )

    def test_all_holding_is_active(self) -> None:
        thesis = self._make_thesis([
            Assumption("Rev growth", "rev", ">5", Decimal("10"), "HOLDING"),
            Assumption("Margin up", "margin", ">20", Decimal("25"), "HOLDING"),
        ])
        updated, alerts = check_thesis(thesis)
        assert updated.status == "ACTIVE"

    def test_one_broken_invalidates(self) -> None:
        thesis = self._make_thesis([
            Assumption("Rev growth", "rev", ">5", Decimal("10"), "HOLDING"),
            Assumption("Margin up", "margin", ">20", Decimal("10"), "BROKEN"),
        ])
        updated, alerts = check_thesis(thesis)
        assert updated.status == "INVALIDATED"

    def test_one_weakened_weakens_thesis(self) -> None:
        thesis = self._make_thesis([
            Assumption("Rev growth", "rev", ">5", Decimal("10"), "HOLDING"),
            Assumption("Margin up", "margin", ">20", Decimal("21"), "WEAKENED"),
        ])
        updated, alerts = check_thesis(thesis)
        assert updated.status == "WEAKENED"

    def test_broken_takes_precedence_over_weakened(self) -> None:
        thesis = self._make_thesis([
            Assumption("Rev growth", "rev", ">5", Decimal("3"), "BROKEN"),
            Assumption("Margin up", "margin", ">20", Decimal("21"), "WEAKENED"),
        ])
        updated, alerts = check_thesis(thesis)
        assert updated.status == "INVALIDATED"

    def test_untested_stays_active(self) -> None:
        thesis = self._make_thesis([
            Assumption("Rev growth", "rev", ">5"),
        ])
        updated, _alerts = check_thesis(thesis)
        assert updated.status == "ACTIVE"


# ---------------------------------------------------------------------------
# severity_for_status_change
# ---------------------------------------------------------------------------


class TestSeverityForStatusChange:
    """Tests for alert severity determination."""

    def test_holding_to_broken_is_critical(self) -> None:
        assert severity_for_status_change("HOLDING", "BROKEN") == "CRITICAL"

    def test_holding_to_weakened_is_warning(self) -> None:
        assert severity_for_status_change("HOLDING", "WEAKENED") == "WARNING"

    def test_untested_to_broken_is_warning(self) -> None:
        assert severity_for_status_change("UNTESTED", "BROKEN") == "WARNING"

    def test_untested_to_holding_is_info(self) -> None:
        assert severity_for_status_change("UNTESTED", "HOLDING") == "INFO"

    def test_weakened_to_broken_is_info(self) -> None:
        assert severity_for_status_change("WEAKENED", "BROKEN") == "INFO"


# ---------------------------------------------------------------------------
# ThesisAlert generation
# ---------------------------------------------------------------------------


class TestAlertGeneration:
    """Tests for alert generation during thesis checks."""

    def test_alerts_generated_for_status_changes(self) -> None:
        thesis = Thesis(
            ticker="MSFT",
            statement="Cloud growth sustains",
            direction="LONG",
            assumptions=[
                Assumption("Growth", "rev", ">10", Decimal("15"), "HOLDING"),
                Assumption("Margin", "margin", ">30", Decimal("5"), "BROKEN"),
            ],
        )
        _, alerts = check_thesis(thesis)
        assert len(alerts) == 2
        tickers = {a.thesis_ticker for a in alerts}
        assert tickers == {"MSFT"}

    def test_broken_assumption_alert_has_warning_severity(self) -> None:
        thesis = Thesis(
            ticker="GOOG",
            statement="Ad revenue dominance",
            direction="LONG",
            assumptions=[
                Assumption("Ad rev", "ad_rev", ">50", Decimal("40"), "BROKEN"),
            ],
        )
        _, alerts = check_thesis(thesis)
        assert len(alerts) == 1
        # old_status defaults to UNTESTED in check_thesis, UNTESTED→BROKEN = WARNING
        assert alerts[0].severity == "WARNING"
        assert alerts[0].new_status == "BROKEN"

    def test_no_alerts_for_untested(self) -> None:
        thesis = Thesis(
            ticker="TSLA",
            statement="EV dominance",
            direction="LONG",
            assumptions=[
                Assumption("Market share", "share", ">20"),
            ],
        )
        _, alerts = check_thesis(thesis)
        assert len(alerts) == 0


# ---------------------------------------------------------------------------
# ThesisGuardianAgent
# ---------------------------------------------------------------------------


class TestThesisGuardianAgent:
    """Tests for the ThesisGuardianAgent class."""

    def test_is_base_agent_subclass(self) -> None:
        agent = ThesisGuardianAgent()
        assert isinstance(agent, BaseAgent)

    def test_system_prompt_mentions_thesis_concepts(self) -> None:
        agent = ThesisGuardianAgent()
        prompt = agent.system_prompt
        assert "thesis" in prompt.lower()
        assert "investment" in prompt.lower()
        assert "assumption" in prompt.lower()

    async def test_run_without_theses_returns_guidance(self) -> None:
        agent = ThesisGuardianAgent()
        response = await agent.run("check")
        assert "No theses" in response.content

    async def test_run_with_thesis_and_data(self) -> None:
        thesis = Thesis(
            ticker="NVDA",
            statement="AI chip dominance",
            direction="LONG",
            assumptions=[
                Assumption("Revenue growth", "revenue_growth", ">20"),
            ],
        )
        agent = ThesisGuardianAgent()
        response = await agent.run(
            "evaluate",
            theses=[thesis],
            data={"revenue_growth": Decimal("50")},
        )
        assert "NVDA" in response.content
        assert response.metadata["theses_checked"] == 1
