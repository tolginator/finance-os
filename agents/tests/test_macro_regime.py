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


def _reading(
    sid: str, desc: str, date: str,
    val: str, prev: str | None = None, chg: str | None = None,
) -> IndicatorReading:
    """Helper to build IndicatorReading with less boilerplate."""
    return IndicatorReading(
        series_id=sid,
        description=desc,
        date=date,
        value=Decimal(val),
        previous_value=Decimal(prev) if prev else None,
        change_pct=Decimal(chg) if chg else None,
    )


class TestClassifyRegime:
    """Tests for regime classification logic."""

    def test_expansion_signals(self) -> None:
        readings = {
            "GDP": [_reading("GDP", "GDP", "2024-03", "100", "95", "5.26")],
            "UNRATE": [_reading("UNRATE", "Unemp", "2024-03", "3.5", "3.7", "-5.41")],
            "T10Y2Y": [_reading("T10Y2Y", "Spread", "2024-03", "1.5")],
            "UMCSENT": [_reading("UMCSENT", "Sent", "2024-03", "100", "90", "11.1")],
            "INDPRO": [_reading("INDPRO", "IndProd", "2024-03", "105", "100", "5")],
        }
        assert classify_regime(readings) == "EXPANSION"

    def test_contraction_signals(self) -> None:
        readings = {
            "GDP": [_reading("GDP", "GDP", "2024-03", "95", "100", "-5")],
            "UNRATE": [_reading("UNRATE", "Unemp", "2024-03", "5.0", "4.0", "25")],
            "T10Y2Y": [_reading("T10Y2Y", "Spread", "2024-03", "-0.5")],
            "UMCSENT": [_reading("UMCSENT", "Sent", "2024-03", "60", "70", "-14.3")],
            "INDPRO": [_reading("INDPRO", "IndProd", "2024-03", "95", "100", "-5")],
        }
        assert classify_regime(readings) == "CONTRACTION"

    def test_transition_on_mixed_signals(self) -> None:
        readings = {
            "GDP": [_reading("GDP", "GDP", "2024-03", "101", "100", "1")],
            "UNRATE": [_reading("UNRATE", "Unemp", "2024-03", "4.5", "4.0", "12.5")],
            "T10Y2Y": [_reading("T10Y2Y", "Spread", "2024-03", "0.1")],
        }
        assert classify_regime(readings) == "TRANSITION"

    def test_empty_readings(self) -> None:
        regime = classify_regime({})
        assert regime == "TRANSITION"


class TestFormatDashboard:
    """Tests for dashboard formatting."""

    def test_includes_regime_and_indicators(self) -> None:
        readings = {
            "GDP": [_reading("GDP", "Real GDP growth", "2024-03", "100", "95", "5.26")],
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
