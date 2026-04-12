"""Macro regime agent — classifies macroeconomic environment.

Analyzes FRED economic indicators and textual signals to classify
the current macro regime as expansion, contraction, or transition.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from src.core.agent import AgentResponse, BaseAgent

FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

# Key macro indicators and their regime signals
MACRO_INDICATORS: dict[str, str] = {
    "GDP": "Real GDP growth",
    "UNRATE": "Unemployment rate",
    "CPIAUCSL": "Consumer Price Index",
    "FEDFUNDS": "Federal Funds Rate",
    "T10Y2Y": "10Y-2Y Treasury Spread",
    "UMCSENT": "Consumer Sentiment",
    "INDPRO": "Industrial Production",
    "PAYEMS": "Nonfarm Payrolls",
}


@dataclass
class IndicatorReading:
    """A single economic indicator observation."""

    series_id: str
    description: str
    date: str
    value: Decimal
    previous_value: Decimal | None
    change_pct: Decimal | None


def fetch_fred_series(
    series_id: str,
    api_key: str,
    limit: int = 12,
) -> list[dict[str, str]]:
    """Fetch recent observations for a FRED series.

    Args:
        series_id: FRED series identifier (e.g., 'GDP', 'UNRATE').
        api_key: FRED API key.
        limit: Number of recent observations to fetch.

    Returns:
        List of observation dicts with 'date' and 'value' keys.
    """
    url = (
        f"{FRED_BASE_URL}"
        f"?series_id={series_id}"
        f"&api_key={api_key}"
        f"&file_type=json"
        f"&sort_order=desc"
        f"&limit={limit}"
    )
    req = urllib.request.Request(
        url, headers={"User-Agent": "finance-os/0.1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            return data.get("observations", [])
    except (urllib.error.URLError, json.JSONDecodeError):
        return []


def parse_observations(
    series_id: str,
    description: str,
    observations: list[dict[str, str]],
) -> list[IndicatorReading]:
    """Parse FRED observations into IndicatorReading objects.

    Args:
        series_id: The FRED series identifier.
        description: Human-readable description.
        observations: Raw observation dicts from FRED API.

    Returns:
        List of parsed IndicatorReading objects, newest first.
    """
    readings: list[IndicatorReading] = []
    for i, obs in enumerate(observations):
        raw_val = obs.get("value", ".")
        if raw_val == ".":
            continue
        value = Decimal(raw_val)

        previous_value: Decimal | None = None
        change_pct: Decimal | None = None
        if i + 1 < len(observations):
            prev_raw = observations[i + 1].get("value", ".")
            if prev_raw != ".":
                previous_value = Decimal(prev_raw)
                if previous_value != 0:
                    change_pct = (
                        (value - previous_value) / previous_value * 100
                    )

        readings.append(IndicatorReading(
            series_id=series_id,
            description=description,
            date=obs.get("date", ""),
            value=value,
            previous_value=previous_value,
            change_pct=change_pct,
        ))

    return readings


def classify_regime(readings: dict[str, list[IndicatorReading]]) -> str:
    """Classify macro regime based on indicator readings.

    Args:
        readings: Dict mapping series_id to their IndicatorReading lists.

    Returns:
        Regime classification: EXPANSION, CONTRACTION, or TRANSITION.
    """
    signals: dict[str, int] = {
        "expansion": 0,
        "contraction": 0,
    }

    # GDP growth > 0 => expansion signal
    gdp = readings.get("GDP", [])
    if gdp and gdp[0].change_pct is not None:
        if gdp[0].change_pct > 0:
            signals["expansion"] += 2
        else:
            signals["contraction"] += 2

    # Unemployment rising => contraction signal
    unrate = readings.get("UNRATE", [])
    if unrate and unrate[0].change_pct is not None:
        if unrate[0].change_pct > 0:
            signals["contraction"] += 1
        else:
            signals["expansion"] += 1

    # Yield curve inversion (T10Y2Y < 0) => contraction signal
    spread = readings.get("T10Y2Y", [])
    if spread and spread[0].value < 0:
        signals["contraction"] += 2
    elif spread and spread[0].value > 0:
        signals["expansion"] += 1

    # Consumer sentiment declining => contraction signal
    sentiment = readings.get("UMCSENT", [])
    if sentiment and sentiment[0].change_pct is not None:
        if sentiment[0].change_pct < Decimal("-5"):
            signals["contraction"] += 1
        elif sentiment[0].change_pct > Decimal("5"):
            signals["expansion"] += 1

    # Industrial production growth
    indpro = readings.get("INDPRO", [])
    if indpro and indpro[0].change_pct is not None:
        if indpro[0].change_pct > 0:
            signals["expansion"] += 1
        else:
            signals["contraction"] += 1

    exp = signals["expansion"]
    con = signals["contraction"]

    if exp > con + 2:
        return "EXPANSION"
    elif con > exp + 2:
        return "CONTRACTION"
    else:
        return "TRANSITION"


def format_dashboard(
    readings: dict[str, list[IndicatorReading]],
    regime: str,
) -> str:
    """Format indicator readings into a readable dashboard.

    Args:
        readings: Dict of series_id to IndicatorReading lists.
        regime: Classified regime string.

    Returns:
        Formatted multi-line dashboard string.
    """
    lines = [
        f"## Macro Regime: **{regime}**\n",
        "### Key Indicators\n",
    ]

    for series_id, indicator_readings in readings.items():
        if not indicator_readings:
            lines.append(
                f"- **{MACRO_INDICATORS.get(series_id, series_id)}**: "
                f"No data available"
            )
            continue

        latest = indicator_readings[0]
        change_str = ""
        if latest.change_pct is not None:
            direction = "↑" if latest.change_pct > 0 else "↓"
            change_str = f" ({direction} {abs(latest.change_pct):.2f}%)"

        lines.append(
            f"- **{latest.description}** ({latest.series_id}): "
            f"{latest.value}{change_str} — {latest.date}"
        )

    return "\n".join(lines)


class MacroRegimeAgent(BaseAgent):
    """Agent that classifies the macroeconomic environment.

    Analyzes FRED economic indicators to determine whether the
    economy is in expansion, contraction, or transition. Provides
    a structured dashboard with indicator readings and regime
    classification.
    """

    def __init__(self, fred_api_key: str = "") -> None:
        super().__init__(
            name="macro_regime",
            description=(
                "Classifies macroeconomic regime from FRED data "
                "and textual signals"
            ),
        )
        self._fred_api_key = fred_api_key

    @property
    def system_prompt(self) -> str:
        """System prompt for macro regime analysis."""
        return (
            "You are a macroeconomic strategist with deep expertise "
            "in business cycle analysis. Your role is to:\n\n"
            "1. **Regime Classification**: Determine current macro "
            "regime — EXPANSION, CONTRACTION, or TRANSITION — based "
            "on economic indicators and textual signals.\n\n"
            "2. **Leading Indicators**: Identify which indicators "
            "are leading (predictive) vs lagging (confirmatory) for "
            "the current cycle phase.\n\n"
            "3. **Yield Curve Analysis**: Interpret Treasury spread "
            "dynamics and their implications for credit conditions "
            "and recession probability.\n\n"
            "4. **Cross-Asset Implications**: Translate macro regime "
            "into asset class positioning — equities, bonds, "
            "commodities, cash.\n\n"
            "5. **Transition Signals**: Flag early indicators of "
            "regime change — leading indicators diverging from "
            "lagging ones, unusual spread behavior, sentiment "
            "shifts.\n\n"
            "Output structured analysis with:\n"
            "- Current regime classification with confidence level\n"
            "- Key supporting and contradicting indicators\n"
            "- Historical comparison to similar regimes\n"
            "- Asset allocation implications\n"
            "- Watchlist of transition triggers"
        )

    async def run(self, prompt: str, **kwargs: Any) -> AgentResponse:
        """Execute macro regime analysis.

        Args:
            prompt: Analysis request or specific indicator focus.
            **kwargs: May include 'api_key' to override FRED key,
                'indicators' as list of FRED series IDs.

        Returns:
            AgentResponse with regime classification and dashboard.
        """
        api_key = kwargs.get("api_key", self._fred_api_key)
        indicator_ids = kwargs.get(
            "indicators",
            list(MACRO_INDICATORS.keys()),
        )

        if not api_key:
            return AgentResponse(
                content=(
                    "FRED API key required for macro data. "
                    "Get a free key at https://fred.stlouisfed.org/docs/api/api_key.html\n\n"
                    "Pass via: agent.run(prompt, api_key='your_key')"
                ),
                metadata={"error": "missing_api_key"},
            )

        all_readings: dict[str, list[IndicatorReading]] = {}

        for series_id in indicator_ids:
            desc = MACRO_INDICATORS.get(series_id, series_id)
            observations = fetch_fred_series(
                series_id, str(api_key), limit=12
            )
            all_readings[series_id] = parse_observations(
                series_id, desc, observations
            )

        regime = classify_regime(all_readings)
        dashboard = format_dashboard(all_readings, regime)

        return AgentResponse(
            content=dashboard,
            metadata={
                "regime": regime,
                "indicators_fetched": len(all_readings),
                "indicators_with_data": sum(
                    1 for r in all_readings.values() if r
                ),
            },
        )
