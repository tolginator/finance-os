"""Tests for the macro regime agent."""

from decimal import Decimal

from src.agents.macro_regime import (
    IndicatorReading,
    MacroRegimeAgent,
    classify_regime,
    format_dashboard,
    parse_observations,
)


class TestParseObservations:
    """Tests for FRED observation parsing."""

    def test_parses_valid_observations(self) -> None:
        obs = [
            {"date": "2024-03-01", "value": "105.0"},
            {"date": "2024-02-01", "value": "100.0"},
        ]
        readings = parse_observations("INDPRO", "Industrial Production", obs)
        assert len(readings) == 2
        assert readings[0].value == Decimal("105.0")
        assert readings[0].change_pct == Decimal("5")

    def test_skips_missing_values(self) -> None:
        obs = [
            {"date": "2024-03-01", "value": "."},
            {"date": "2024-02-01", "value": "100.0"},
        ]
        readings = parse_observations("GDP", "GDP", obs)
        assert len(readings) == 1
        assert readings[0].date == "2024-02-01"

    def test_handles_empty_observations(self) -> None:
        readings = parse_observations("GDP", "GDP", [])
        assert readings == []


class TestClassifyRegime:
    """Tests for regime classification logic."""

    def test_expansion_signals(self) -> None:
        readings = {
            "GDP": [IndicatorReading("GDP", "GDP", "2024-03", Decimal("100"), Decimal("95"), Decimal("5.26"))],
            "UNRATE": [IndicatorReading("UNRATE", "Unemployment", "2024-03", Decimal("3.5"), Decimal("3.7"), Decimal("-5.41"))],
            "T10Y2Y": [IndicatorReading("T10Y2Y", "Spread", "2024-03", Decimal("1.5"), None, None)],
            "UMCSENT": [IndicatorReading("UMCSENT", "Sentiment", "2024-03", Decimal("100"), Decimal("90"), Decimal("11.1"))],
            "INDPRO": [IndicatorReading("INDPRO", "IndProd", "2024-03", Decimal("105"), Decimal("100"), Decimal("5"))],
        }
        assert classify_regime(readings) == "EXPANSION"

    def test_contraction_signals(self) -> None:
        readings = {
            "GDP": [IndicatorReading("GDP", "GDP", "2024-03", Decimal("95"), Decimal("100"), Decimal("-5"))],
            "UNRATE": [IndicatorReading("UNRATE", "Unemployment", "2024-03", Decimal("5.0"), Decimal("4.0"), Decimal("25"))],
            "T10Y2Y": [IndicatorReading("T10Y2Y", "Spread", "2024-03", Decimal("-0.5"), None, None)],
            "UMCSENT": [IndicatorReading("UMCSENT", "Sentiment", "2024-03", Decimal("60"), Decimal("70"), Decimal("-14.3"))],
            "INDPRO": [IndicatorReading("INDPRO", "IndProd", "2024-03", Decimal("95"), Decimal("100"), Decimal("-5"))],
        }
        assert classify_regime(readings) == "CONTRACTION"

    def test_transition_on_mixed_signals(self) -> None:
        readings = {
            "GDP": [IndicatorReading("GDP", "GDP", "2024-03", Decimal("101"), Decimal("100"), Decimal("1"))],
            "UNRATE": [IndicatorReading("UNRATE", "Unemployment", "2024-03", Decimal("4.5"), Decimal("4.0"), Decimal("12.5"))],
            "T10Y2Y": [IndicatorReading("T10Y2Y", "Spread", "2024-03", Decimal("0.1"), None, None)],
        }
        assert classify_regime(readings) == "TRANSITION"

    def test_empty_readings(self) -> None:
        regime = classify_regime({})
        assert regime == "TRANSITION"


class TestFormatDashboard:
    """Tests for dashboard formatting."""

    def test_includes_regime_and_indicators(self) -> None:
        readings = {
            "GDP": [IndicatorReading("GDP", "Real GDP growth", "2024-03", Decimal("100"), Decimal("95"), Decimal("5.26"))],
        }
        output = format_dashboard(readings, "EXPANSION")
        assert "EXPANSION" in output
        assert "Real GDP growth" in output
        assert "5.26%" in output

    def test_handles_no_data_indicator(self) -> None:
        readings = {"GDP": []}
        output = format_dashboard(readings, "TRANSITION")
        assert "No data available" in output


class TestMacroRegimeAgent:
    """Tests for MacroRegimeAgent behavior."""

    def test_system_prompt_covers_key_areas(self) -> None:
        agent = MacroRegimeAgent()
        prompt = agent.system_prompt
        assert "regime" in prompt.lower()
        assert "yield" in prompt.lower()
        assert "EXPANSION" in prompt

    async def test_run_requires_api_key(self) -> None:
        agent = MacroRegimeAgent()
        response = await agent.run("analyze")
        assert "API key" in response.content
