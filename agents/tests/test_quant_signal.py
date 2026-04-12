"""Tests for the quant_signal agent and its helper functions."""


from decimal import Decimal

import pytest

from src.agents.quant_signal import (
    QuantSignalAgent,
    Signal,
    composite_score,
    compute_zscore,
    decay_weight,
    guidance_to_signal,
    normalize_signal,
    regime_to_signal,
    sentiment_to_signal,
)
from src.core.agent import AgentResponse, BaseAgent

# ---------------------------------------------------------------------------
# normalize_signal
# ---------------------------------------------------------------------------


class TestNormalizeSignal:
    def test_midpoint_returns_zero(self) -> None:
        assert normalize_signal(Decimal("5"), Decimal("0"), Decimal("10")) == Decimal("0")

    def test_max_returns_one(self) -> None:
        assert normalize_signal(Decimal("10"), Decimal("0"), Decimal("10")) == Decimal("1")

    def test_min_returns_negative_one(self) -> None:
        assert normalize_signal(Decimal("0"), Decimal("0"), Decimal("10")) == Decimal("-1")

    def test_above_max_clamped(self) -> None:
        assert normalize_signal(Decimal("20"), Decimal("0"), Decimal("10")) == Decimal("1")

    def test_below_min_clamped(self) -> None:
        assert normalize_signal(Decimal("-5"), Decimal("0"), Decimal("10")) == Decimal("-1")


# ---------------------------------------------------------------------------
# compute_zscore
# ---------------------------------------------------------------------------


class TestComputeZscore:
    def test_known_values(self) -> None:
        result = compute_zscore(Decimal("12"), Decimal("10"), Decimal("2"))
        assert result == Decimal("1")

    def test_negative_zscore(self) -> None:
        result = compute_zscore(Decimal("8"), Decimal("10"), Decimal("2"))
        assert result == Decimal("-1")

    def test_zero_std_returns_zero(self) -> None:
        assert compute_zscore(Decimal("5"), Decimal("3"), Decimal("0")) == Decimal("0")


# ---------------------------------------------------------------------------
# sentiment_to_signal
# ---------------------------------------------------------------------------


class TestSentimentToSignal:
    def test_positive_score(self) -> None:
        sig = sentiment_to_signal(Decimal("0.8"), "bullish", "earnings_interpreter")
        assert sig.value > 0
        assert sig.confidence > 0

    def test_negative_score(self) -> None:
        sig = sentiment_to_signal(Decimal("-0.6"), "bearish", "earnings_interpreter")
        assert sig.value < 0

    def test_zero_score(self) -> None:
        sig = sentiment_to_signal(Decimal("0"), "neutral", "earnings_interpreter")
        assert sig.value == Decimal("0")
        assert sig.confidence == Decimal("0")

    def test_source_preserved(self) -> None:
        sig = sentiment_to_signal(Decimal("0.5"), "tone", "my_source")
        assert sig.source == "my_source"


# ---------------------------------------------------------------------------
# regime_to_signal
# ---------------------------------------------------------------------------


class TestRegimeToSignal:
    def test_expansion(self) -> None:
        sig = regime_to_signal("EXPANSION", "macro_regime")
        assert sig.value == Decimal("1")
        assert sig.confidence == Decimal("0.8")

    def test_contraction(self) -> None:
        sig = regime_to_signal("CONTRACTION", "macro_regime")
        assert sig.value == Decimal("-1")
        assert sig.confidence == Decimal("0.8")

    def test_transition(self) -> None:
        sig = regime_to_signal("TRANSITION", "macro_regime")
        assert sig.value == Decimal("0")
        assert sig.confidence == Decimal("0.4")

    def test_unknown_raises(self) -> None:
        with pytest.raises(ValueError):
            regime_to_signal("BOOM", "macro_regime")


# ---------------------------------------------------------------------------
# guidance_to_signal
# ---------------------------------------------------------------------------


class TestGuidanceToSignal:
    def test_raised(self) -> None:
        sig = guidance_to_signal("RAISED", "earnings_interpreter")
        assert sig.value == Decimal("1")

    def test_lowered(self) -> None:
        sig = guidance_to_signal("LOWERED", "earnings_interpreter")
        assert sig.value == Decimal("-1")

    def test_maintained(self) -> None:
        sig = guidance_to_signal("MAINTAINED", "earnings_interpreter")
        assert sig.value == Decimal("0")

    def test_neutral(self) -> None:
        sig = guidance_to_signal("NEUTRAL", "earnings_interpreter")
        assert sig.value == Decimal("0")

    def test_unknown_raises(self) -> None:
        with pytest.raises(ValueError):
            guidance_to_signal("YOLO", "earnings_interpreter")


# ---------------------------------------------------------------------------
# composite_score
# ---------------------------------------------------------------------------


class TestCompositeScore:
    @staticmethod
    def _make_signal(value: str, confidence: str = "1") -> Signal:
        return Signal(
            name="test",
            value=Decimal(value),
            confidence=Decimal(confidence),
            source="test",
            timestamp="2025-01-01",
            raw_value=Decimal(value),
        )

    def test_equal_weight_averages(self) -> None:
        signals = [self._make_signal("0.4"), self._make_signal("0.6")]
        comp = composite_score(signals, method="equal_weight")
        assert comp.score == Decimal("0.5")
        assert comp.method == "equal_weight"

    def test_confidence_weight(self) -> None:
        s1 = self._make_signal("1", "0.8")  # contributes 0.8
        s2 = self._make_signal("-1", "0.2")  # contributes -0.2
        comp = composite_score([s1, s2], method="confidence_weight")
        # (1*0.8 + -1*0.2) / (0.8+0.2) = 0.6
        assert comp.score == Decimal("0.6")

    def test_empty_signals_raises(self) -> None:
        with pytest.raises(ValueError):
            composite_score([])

    def test_all_zero_confidence(self) -> None:
        """Signals with zero confidence should not cause division by zero."""
        signals = [
            self._make_signal("0.5", "0"),
            self._make_signal("-0.3", "0"),
        ]
        comp = composite_score(signals, method="confidence_weight")
        assert comp.score == Decimal("0")


# ---------------------------------------------------------------------------
# decay_weight
# ---------------------------------------------------------------------------


class TestDecayWeight:
    def test_age_zero(self) -> None:
        assert decay_weight(0) == Decimal("1.0")

    def test_age_equals_half_life(self) -> None:
        assert decay_weight(30, half_life=30) == Decimal("0.5")

    def test_weight_decreases_with_age(self) -> None:
        assert decay_weight(60, half_life=30) < decay_weight(30, half_life=30)

    def test_large_age_still_positive(self) -> None:
        w = decay_weight(300, half_life=30)
        assert w > Decimal("0")
        assert w < Decimal("0.01")


# ---------------------------------------------------------------------------
# QuantSignalAgent
# ---------------------------------------------------------------------------


class TestQuantSignalAgent:
    def test_is_base_agent_subclass(self) -> None:
        agent = QuantSignalAgent()
        assert isinstance(agent, BaseAgent)

    def test_system_prompt_mentions_signal(self) -> None:
        agent = QuantSignalAgent()
        prompt = agent.system_prompt.lower()
        assert "signal" in prompt
        assert "quant" in prompt

    @pytest.mark.asyncio
    async def test_run_returns_agent_response(self) -> None:
        agent = QuantSignalAgent()
        resp = await agent.run("generate signals", regime="EXPANSION", source="test")
        assert isinstance(resp, AgentResponse)
        assert resp.metadata.get("composite") is not None
