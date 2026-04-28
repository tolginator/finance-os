"""Regime classification service — deterministic multi-dimensional macro regime.

Classifies the economic environment across growth, rates, and inflation
dimensions using FRED indicator data.  Each dimension uses rule-based
scoring with per-series freshness thresholds.

Global trade dimension is defined but not populated until IMF/WB data
services are available.
"""

import logging
from datetime import UTC, date, datetime
from decimal import Decimal

from src.application.contracts.regime import (
    GrowthClassification,
    GrowthRegime,
    InflationClassification,
    InflationRegime,
    MacroRegimeReport,
    RateClassification,
    RateEnvironment,
    TrendDirection,
)
from src.application.data_services.base import DataReading, DataResponse, FreshnessState
from src.application.data_services.fred_service import FREDService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Freshness thresholds by frequency
# ---------------------------------------------------------------------------

# Maximum age (days) before data is considered stale for classification
FRESHNESS_THRESHOLDS: dict[str, int] = {
    "daily": 5,
    "monthly": 45,
    "quarterly": 120,
}


def _data_freshness(reading: DataReading) -> FreshnessState:
    """Determine freshness state based on observation date and frequency."""
    if not reading.date:
        return FreshnessState.STALE
    age_days = (date.today() - reading.date).days
    threshold = FRESHNESS_THRESHOLDS.get(reading.frequency, 45)
    if age_days <= threshold:
        return FreshnessState.FRESH
    return FreshnessState.STALE


def _latest_reading(response: DataResponse) -> DataReading | None:
    """Get the most recent reading from a response."""
    if not response.readings:
        return None
    return response.readings[0]


def _effective_date(readings: list[DataReading]) -> datetime:
    """Compute common effective date as the oldest latest-observation date."""
    if not readings:
        return datetime.now(UTC)
    oldest = min(r.date for r in readings)
    return datetime(oldest.year, oldest.month, oldest.day, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Growth dimension classifier
# ---------------------------------------------------------------------------

# Indicators used: GDP, UNRATE, INDPRO, PAYEMS, USALOLITONOSTSAM (LEI)
GROWTH_INDICATORS = ["GDP", "UNRATE", "INDPRO", "PAYEMS", "USALOLITONOSTSAM"]


def classify_growth(
    data: dict[str, DataResponse],
) -> GrowthClassification | None:
    """Classify growth regime from FRED indicator responses.

    Scoring logic:
    - GDP qoq growth > 0: expansion signal
    - GDP qoq growth < 0: contraction signal
    - Unemployment falling: expansion signal
    - Unemployment rising: contraction signal
    - Industrial production rising: expansion signal
    - Payrolls growing: expansion signal
    - LEI rising: expansion signal (forward-looking)

    Classification:
    - EXPANSION: strong positive signals, GDP growing
    - SLOWING: GDP still positive but momentum fading
    - CONTRACTION: GDP negative or overwhelming contraction signals
    - RECOVERY: GDP negative but leading indicators improving
    """
    signals: dict[str, int] = {"expansion": 0, "contraction": 0}
    contributing: list[str] = []
    latest_readings: list[DataReading] = []
    stale_count = 0

    for series_id in GROWTH_INDICATORS:
        resp = data.get(series_id)
        if resp is None:
            continue
        reading = _latest_reading(resp)
        if reading is None:
            continue
        latest_readings.append(reading)
        if _data_freshness(reading) == FreshnessState.STALE:
            stale_count += 1

        contributing.append(series_id)

        if series_id == "GDP":
            if reading.pct_change is not None:
                if reading.pct_change > 0:
                    signals["expansion"] += 2
                elif reading.pct_change < 0:
                    signals["contraction"] += 2
        elif series_id == "UNRATE":
            if reading.pct_change is not None:
                if reading.pct_change > 0:
                    signals["contraction"] += 1
                elif reading.pct_change < 0:
                    signals["expansion"] += 1
        elif series_id in ("INDPRO", "PAYEMS"):
            if reading.pct_change is not None:
                if reading.pct_change > 0:
                    signals["expansion"] += 1
                elif reading.pct_change < 0:
                    signals["contraction"] += 1
        elif series_id == "USALOLITONOSTSAM":
            # LEI: rising = forward expansion signal
            if reading.pct_change is not None:
                if reading.pct_change > 0:
                    signals["expansion"] += 1
                elif reading.pct_change < 0:
                    signals["contraction"] += 1

    if not contributing:
        logger.info("Growth classification skipped: no indicator data available")
        return None

    exp = signals["expansion"]
    con = signals["contraction"]

    # Determine regime
    gdp_resp = data.get("GDP")
    gdp_reading = _latest_reading(gdp_resp) if gdp_resp else None
    gdp_positive = (
        gdp_reading is not None
        and gdp_reading.pct_change is not None
        and gdp_reading.pct_change > 0
    )

    # Check if leading indicators are improving while GDP is negative
    lei_resp = data.get("USALOLITONOSTSAM")
    lei_reading = _latest_reading(lei_resp) if lei_resp else None
    lei_improving = (
        lei_reading is not None
        and lei_reading.pct_change is not None
        and lei_reading.pct_change > 0
    )

    if con > exp + 1 and not gdp_positive:
        if lei_improving:
            regime = GrowthRegime.RECOVERY
        else:
            regime = GrowthRegime.CONTRACTION
    elif exp > con + 2:
        regime = GrowthRegime.EXPANSION
    elif gdp_positive and con >= exp:
        regime = GrowthRegime.SLOWING
    elif gdp_positive:
        regime = GrowthRegime.EXPANSION
    else:
        regime = GrowthRegime.SLOWING

    # Confidence: reduced for stale data or few indicators
    base_confidence = Decimal("0.8")
    if stale_count > 0:
        base_confidence -= Decimal("0.1") * stale_count
    if len(contributing) < 3:
        base_confidence -= Decimal("0.2")
    confidence = max(Decimal("0.1"), min(Decimal("1.0"), base_confidence))

    # Trend: compare expansion vs contraction signal balance
    if exp > con + 1:
        trend = TrendDirection.IMPROVING
    elif con > exp + 1:
        trend = TrendDirection.DETERIORATING
    else:
        trend = TrendDirection.STABLE

    as_of = _effective_date(latest_readings)
    freshness = (
        FreshnessState.STALE if stale_count > len(contributing) / 2
        else FreshnessState.FRESH
    )

    return GrowthClassification(
        regime=regime,
        trend=trend,
        confidence=confidence,
        as_of=as_of,
        freshness=freshness,
        contributing_indicators=contributing,
    )


# ---------------------------------------------------------------------------
# Rate environment classifier
# ---------------------------------------------------------------------------

RATE_INDICATORS = ["FEDFUNDS", "DGS10", "T10Y2Y"]


def classify_rates(
    data: dict[str, DataResponse],
) -> RateClassification | None:
    """Classify rate environment from FRED indicator responses.

    Scoring logic:
    - Fed funds rate direction (rising/stable/falling)
    - Yield curve shape (normal/flat/inverted)
    - Long rates direction

    Classification:
    - RISING: Fed funds increasing, curve steepening or flat
    - PEAK: Fed funds high and stable, curve flat/inverted
    - FALLING: Fed funds decreasing
    - TROUGH: Fed funds low and stable, curve steepening
    """
    contributing: list[str] = []
    latest_readings: list[DataReading] = []
    stale_count = 0

    for series_id in RATE_INDICATORS:
        resp = data.get(series_id)
        if resp is None:
            continue
        reading = _latest_reading(resp)
        if reading is None:
            continue
        latest_readings.append(reading)
        if _data_freshness(reading) == FreshnessState.STALE:
            stale_count += 1
        contributing.append(series_id)

    if not contributing:
        logger.info("Rate classification skipped: no indicator data available")
        return None

    # Fed funds is required — without it, rate classification is underdetermined
    ff_resp = data.get("FEDFUNDS")
    ff_reading = _latest_reading(ff_resp) if ff_resp else None
    if ff_reading is None:
        logger.info("Rate classification skipped: FEDFUNDS data unavailable")
        return None

    # Fed funds direction
    ff_rising = (
        ff_reading.pct_change is not None
        and ff_reading.pct_change > 0
    )
    ff_falling = (
        ff_reading.pct_change is not None
        and ff_reading.pct_change < 0
    )
    ff_stable = not ff_rising and not ff_falling

    # Yield curve shape
    spread_resp = data.get("T10Y2Y")
    spread_reading = _latest_reading(spread_resp) if spread_resp else None
    curve_inverted = (
        spread_reading is not None and spread_reading.value < 0
    )
    curve_steep = (
        spread_reading is not None and spread_reading.value > Decimal("1.0")
    )

    # Fed funds level context (high = > 4%, low = < 2%)
    ff_high = ff_reading is not None and ff_reading.value > Decimal("4")
    ff_low = ff_reading is not None and ff_reading.value < Decimal("2")

    # Classification
    if ff_rising:
        regime = RateEnvironment.RISING
    elif ff_falling:
        regime = RateEnvironment.FALLING
    elif ff_stable and (ff_high or curve_inverted):
        regime = RateEnvironment.PEAK
    elif ff_stable and (ff_low or curve_steep):
        regime = RateEnvironment.TROUGH
    elif ff_stable:
        # Ambiguous stable — use curve shape
        if curve_inverted:
            regime = RateEnvironment.PEAK
        elif curve_steep:
            regime = RateEnvironment.TROUGH
        else:
            regime = RateEnvironment.PEAK  # default when unclear
    else:
        regime = RateEnvironment.PEAK

    # Confidence
    base_confidence = Decimal("0.8")
    if stale_count > 0:
        base_confidence -= Decimal("0.1") * stale_count
    if len(contributing) < 3:
        base_confidence -= Decimal("0.2")
    confidence = max(Decimal("0.1"), min(Decimal("1.0"), base_confidence))

    # Trend
    if ff_rising:
        trend = TrendDirection.DETERIORATING  # rising rates = tightening
    elif ff_falling:
        trend = TrendDirection.IMPROVING  # falling rates = easing
    else:
        trend = TrendDirection.STABLE

    as_of = _effective_date(latest_readings)
    freshness = (
        FreshnessState.STALE if stale_count > len(contributing) / 2
        else FreshnessState.FRESH
    )

    return RateClassification(
        regime=regime,
        trend=trend,
        confidence=confidence,
        as_of=as_of,
        freshness=freshness,
        contributing_indicators=contributing,
    )


# ---------------------------------------------------------------------------
# Inflation regime classifier
# ---------------------------------------------------------------------------

INFLATION_INDICATORS = ["CPIAUCSL", "UNRATE"]


def classify_inflation(
    data: dict[str, DataResponse],
) -> InflationClassification | None:
    """Classify inflation regime from FRED indicator responses.

    Scoring logic:
    - CPI month-over-month change direction and magnitude
    - Combination with growth signals for stagflation detection

    Classification:
    - DISINFLATION: CPI growth decelerating
    - STABLE: CPI growth in normal range (0-0.3% mom)
    - REFLATION: CPI growth accelerating
    - STAGFLATION: CPI rising while growth deteriorating
    """
    contributing: list[str] = []
    latest_readings: list[DataReading] = []
    stale_count = 0

    for series_id in INFLATION_INDICATORS:
        resp = data.get(series_id)
        if resp is None:
            continue
        reading = _latest_reading(resp)
        if reading is None:
            continue
        latest_readings.append(reading)
        if _data_freshness(reading) == FreshnessState.STALE:
            stale_count += 1
        contributing.append(series_id)

    if "CPIAUCSL" not in contributing:
        logger.info("Inflation classification skipped: CPI data unavailable")
        return None

    cpi_resp = data.get("CPIAUCSL")
    cpi_reading = _latest_reading(cpi_resp) if cpi_resp else None

    if cpi_reading is None or cpi_reading.pct_change is None:
        logger.info("Inflation classification skipped: CPI pct_change unavailable")
        return None

    cpi_mom = cpi_reading.pct_change

    # Thresholds for monthly CPI change (percentage)
    # Normal: 0.1-0.3% mom (~1.2-3.6% annualized)
    # High: > 0.4% mom (~4.8%+ annualized)
    # Low/Negative: < 0.1% mom

    if cpi_mom > Decimal("0.4"):
        # High inflation — check if stagflationary
        # Stagflation: high inflation + weak growth signals
        # Use unemployment as proxy for growth weakness
        unrate_resp = data.get("UNRATE")
        unrate_reading = _latest_reading(unrate_resp) if unrate_resp else None
        unemployment_rising = (
            unrate_reading is not None
            and unrate_reading.pct_change is not None
            and unrate_reading.pct_change > 0
        )
        if unemployment_rising:
            regime = InflationRegime.STAGFLATION
        else:
            regime = InflationRegime.REFLATION
    elif cpi_mom > Decimal("0.3"):
        regime = InflationRegime.REFLATION
    elif cpi_mom >= Decimal("0.1"):
        regime = InflationRegime.STABLE
    else:
        regime = InflationRegime.DISINFLATION

    # Confidence
    base_confidence = Decimal("0.7")
    if stale_count > 0:
        base_confidence -= Decimal("0.1") * stale_count
    confidence = max(Decimal("0.1"), min(Decimal("1.0"), base_confidence))

    # Trend
    if cpi_mom > Decimal("0.3"):
        trend = TrendDirection.DETERIORATING
    elif cpi_mom < Decimal("0.1"):
        trend = TrendDirection.IMPROVING
    else:
        trend = TrendDirection.STABLE

    as_of = _effective_date(latest_readings)
    freshness = (
        FreshnessState.STALE if stale_count > len(contributing) / 2
        else FreshnessState.FRESH
    )

    return InflationClassification(
        regime=regime,
        trend=trend,
        confidence=confidence,
        as_of=as_of,
        freshness=freshness,
        contributing_indicators=contributing,
    )


# ---------------------------------------------------------------------------
# Regime service
# ---------------------------------------------------------------------------

# All indicators needed across all dimensions
ALL_REGIME_INDICATORS = sorted(
    set(GROWTH_INDICATORS + RATE_INDICATORS + INFLATION_INDICATORS + ["UNRATE"])
)


class RegimeService:
    """Deterministic macro regime classification service.

    Fetches FRED data and classifies each dimension independently.
    Does not call LLMs — pure rule-based scoring.
    """

    def __init__(self, fred_service: FREDService) -> None:
        self._fred = fred_service

    def classify(self) -> MacroRegimeReport:
        """Classify all regime dimensions from current FRED data.

        Returns a MacroRegimeReport with populated dimensions.
        Dimensions return None if insufficient data is available.

        This method is synchronous because FREDService uses blocking I/O.
        Callers in async contexts should use ``asyncio.to_thread``.
        """
        # Fetch all indicators
        data = self._fetch_indicators()

        # Classify each dimension independently
        growth = classify_growth(data)
        rates = classify_rates(data)
        inflation = classify_inflation(data)

        # Compute common as_of
        all_readings: list[DataReading] = []
        for resp in data.values():
            if resp.readings:
                all_readings.append(resp.readings[0])

        as_of = _effective_date(all_readings) if all_readings else datetime.now(UTC)

        return MacroRegimeReport(
            growth=growth,
            rates=rates,
            inflation=inflation,
            global_trade=None,  # Awaiting IMF/WB services
            as_of=as_of,
        )

    def _fetch_indicators(self) -> dict[str, DataResponse]:
        """Fetch all regime indicators from FRED."""
        return self._fred.fetch_multiple(ALL_REGIME_INDICATORS, limit=3)
