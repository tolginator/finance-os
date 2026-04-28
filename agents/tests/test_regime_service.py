"""Tests for multi-dimensional macro regime classification."""

from datetime import date
from decimal import Decimal

import pytest

from src.application.contracts.regime import (
    DimensionClassification,
    GrowthClassification,
    GrowthRegime,
    InflationRegime,
    MacroRegimeReport,
    RateClassification,
    RateEnvironment,
    TrendDirection,
)
from src.application.data_services.base import (
    DataReading,
    DataResponse,
    FreshnessMetadata,
    FreshnessState,
)
from src.application.services.regime_service import (
    classify_growth,
    classify_inflation,
    classify_rates,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_D = Decimal


def _reading(
    series_id: str,
    value: Decimal,
    pct_change: Decimal | None = None,
    obs_date: date | None = None,
    frequency: str = "monthly",
) -> DataReading:
    """Build a DataReading for testing."""
    return DataReading(
        series_id=series_id,
        description=f"Test {series_id}",
        date=obs_date or date.today(),
        value=value,
        unit="%",
        frequency=frequency,
        pct_change=pct_change,
    )


def _response(reading: DataReading) -> DataResponse:
    """Wrap a reading in a DataResponse."""
    return DataResponse(
        readings=[reading],
        freshness=FreshnessMetadata(source="fred"),
    )


def _growth_data(
    gdp_pct: Decimal | None = _D("2.0"),
    unrate_pct: Decimal | None = _D("-0.1"),
    indpro_pct: Decimal | None = _D("0.3"),
    payems_pct: Decimal | None = _D("0.2"),
    lei_pct: Decimal | None = _D("0.1"),
) -> dict[str, DataResponse]:
    """Build mock data for growth classification."""
    data: dict[str, DataResponse] = {}
    if gdp_pct is not None:
        data["GDP"] = _response(
            _reading("GDP", _D("25000"), gdp_pct, frequency="quarterly")
        )
    if unrate_pct is not None:
        data["UNRATE"] = _response(_reading("UNRATE", _D("3.7"), unrate_pct))
    if indpro_pct is not None:
        data["INDPRO"] = _response(_reading("INDPRO", _D("103"), indpro_pct))
    if payems_pct is not None:
        data["PAYEMS"] = _response(_reading("PAYEMS", _D("157000"), payems_pct))
    if lei_pct is not None:
        data["USALOLITONOSTSAM"] = _response(
            _reading("USALOLITONOSTSAM", _D("100"), lei_pct)
        )
    return data


def _rate_data(
    ff_value: Decimal = _D("5.25"),
    ff_pct: Decimal | None = _D("0"),
    spread_value: Decimal = _D("0.5"),
    dgs10_pct: Decimal | None = _D("0"),
) -> dict[str, DataResponse]:
    """Build mock data for rate classification."""
    data: dict[str, DataResponse] = {}
    data["FEDFUNDS"] = _response(
        _reading("FEDFUNDS", ff_value, ff_pct)
    )
    data["T10Y2Y"] = _response(
        _reading("T10Y2Y", spread_value, frequency="daily")
    )
    data["DGS10"] = _response(
        _reading("DGS10", _D("4.2"), dgs10_pct, frequency="daily")
    )
    return data


def _inflation_data(
    cpi_pct: Decimal = _D("0.2"),
    unrate_pct: Decimal | None = None,
) -> dict[str, DataResponse]:
    """Build mock data for inflation classification."""
    data: dict[str, DataResponse] = {}
    data["CPIAUCSL"] = _response(_reading("CPIAUCSL", _D("310"), cpi_pct))
    if unrate_pct is not None:
        data["UNRATE"] = _response(_reading("UNRATE", _D("4.0"), unrate_pct))
    return data


# ---------------------------------------------------------------------------
# Contract tests
# ---------------------------------------------------------------------------


class TestRegimeContracts:
    def test_growth_regime_values(self) -> None:
        assert set(GrowthRegime) == {
            GrowthRegime.EXPANSION,
            GrowthRegime.SLOWING,
            GrowthRegime.CONTRACTION,
            GrowthRegime.RECOVERY,
        }

    def test_rate_environment_values(self) -> None:
        assert set(RateEnvironment) == {
            RateEnvironment.RISING,
            RateEnvironment.PEAK,
            RateEnvironment.FALLING,
            RateEnvironment.TROUGH,
        }

    def test_inflation_regime_values(self) -> None:
        assert set(InflationRegime) == {
            InflationRegime.DISINFLATION,
            InflationRegime.STABLE,
            InflationRegime.REFLATION,
            InflationRegime.STAGFLATION,
        }

    def test_dimension_confidence_bounds(self) -> None:
        with pytest.raises(ValueError, match="confidence"):
            DimensionClassification(
                regime="test",
                confidence=_D("1.5"),
            )
        with pytest.raises(ValueError, match="confidence"):
            DimensionClassification(
                regime="test",
                confidence=_D("-0.1"),
            )

    def test_macro_regime_report_legacy_regime(self) -> None:
        report = MacroRegimeReport(
            growth=GrowthClassification(
                regime=GrowthRegime.EXPANSION,
                contributing_indicators=["GDP"],
            ),
        )
        assert report.legacy_regime == "EXPANSION"

    def test_legacy_regime_contraction(self) -> None:
        report = MacroRegimeReport(
            growth=GrowthClassification(
                regime=GrowthRegime.CONTRACTION,
                contributing_indicators=["GDP"],
            ),
        )
        assert report.legacy_regime == "CONTRACTION"

    def test_legacy_regime_transition_on_slowing(self) -> None:
        report = MacroRegimeReport(
            growth=GrowthClassification(
                regime=GrowthRegime.SLOWING,
                contributing_indicators=["GDP"],
            ),
        )
        assert report.legacy_regime == "TRANSITION"

    def test_legacy_regime_none_growth(self) -> None:
        report = MacroRegimeReport()
        assert report.legacy_regime == "TRANSITION"

    def test_overall_confidence_average(self) -> None:
        report = MacroRegimeReport(
            growth=GrowthClassification(
                regime=GrowthRegime.EXPANSION,
                confidence=_D("0.8"),
                contributing_indicators=["GDP"],
            ),
            rates=RateClassification(
                regime=RateEnvironment.PEAK,
                confidence=_D("0.6"),
                contributing_indicators=["FEDFUNDS"],
            ),
        )
        assert report.overall_confidence == _D("0.7")

    def test_overall_confidence_empty(self) -> None:
        report = MacroRegimeReport()
        assert report.overall_confidence == _D("0")

    def test_populated_dimensions_count(self) -> None:
        report = MacroRegimeReport(
            growth=GrowthClassification(
                regime=GrowthRegime.EXPANSION,
                contributing_indicators=["GDP"],
            ),
        )
        assert report.populated_dimensions == 1

    def test_serialization_roundtrip(self) -> None:
        report = MacroRegimeReport(
            growth=GrowthClassification(
                regime=GrowthRegime.EXPANSION,
                trend=TrendDirection.IMPROVING,
                confidence=_D("0.8"),
                contributing_indicators=["GDP", "INDPRO"],
            ),
            rates=RateClassification(
                regime=RateEnvironment.PEAK,
                contributing_indicators=["FEDFUNDS"],
            ),
        )
        dumped = report.model_dump(mode="json")
        restored = MacroRegimeReport.model_validate(dumped)
        assert restored.growth is not None
        assert restored.growth.regime == GrowthRegime.EXPANSION
        assert restored.rates is not None
        assert restored.rates.regime == RateEnvironment.PEAK
        assert restored.global_trade is None


# ---------------------------------------------------------------------------
# Growth classifier tests
# ---------------------------------------------------------------------------


class TestClassifyGrowth:
    def test_expansion_strong_signals(self) -> None:
        result = classify_growth(_growth_data())
        assert result is not None
        assert result.regime == GrowthRegime.EXPANSION
        assert result.trend == TrendDirection.IMPROVING

    def test_contraction_negative_gdp(self) -> None:
        result = classify_growth(
            _growth_data(
                gdp_pct=_D("-1.0"),
                unrate_pct=_D("0.5"),
                indpro_pct=_D("-0.5"),
                payems_pct=_D("-0.3"),
                lei_pct=_D("-0.2"),
            )
        )
        assert result is not None
        assert result.regime == GrowthRegime.CONTRACTION
        assert result.trend == TrendDirection.DETERIORATING

    def test_recovery_negative_gdp_improving_lei(self) -> None:
        result = classify_growth(
            _growth_data(
                gdp_pct=_D("-0.5"),
                unrate_pct=_D("0.3"),
                indpro_pct=_D("-0.2"),
                payems_pct=_D("-0.1"),
                lei_pct=_D("0.5"),  # LEI improving
            )
        )
        assert result is not None
        assert result.regime == GrowthRegime.RECOVERY

    def test_slowing_positive_gdp_weak_signals(self) -> None:
        result = classify_growth(
            _growth_data(
                gdp_pct=_D("0.5"),
                unrate_pct=_D("0.2"),  # rising unemployment
                indpro_pct=_D("-0.1"),  # declining production
                payems_pct=_D("-0.1"),  # declining payrolls
                lei_pct=_D("-0.1"),  # LEI declining
            )
        )
        assert result is not None
        assert result.regime == GrowthRegime.SLOWING

    def test_no_data_returns_none(self) -> None:
        result = classify_growth({})
        assert result is None

    def test_confidence_reduced_for_stale_data(self) -> None:
        stale_date = date(2020, 1, 1)
        data = {
            "GDP": _response(
                _reading("GDP", _D("25000"), _D("2.0"), stale_date, "quarterly")
            ),
            "UNRATE": _response(
                _reading("UNRATE", _D("3.7"), _D("-0.1"), stale_date)
            ),
            "INDPRO": _response(
                _reading("INDPRO", _D("103"), _D("0.3"), stale_date)
            ),
        }
        result = classify_growth(data)
        assert result is not None
        assert result.confidence < _D("0.8")
        assert result.freshness == FreshnessState.STALE

    def test_contributing_indicators_tracked(self) -> None:
        result = classify_growth(_growth_data())
        assert result is not None
        assert "GDP" in result.contributing_indicators
        assert "INDPRO" in result.contributing_indicators

    def test_zero_pct_change_is_neutral(self) -> None:
        """pct_change == 0 should not count as either signal."""
        result = classify_growth(
            _growth_data(
                gdp_pct=_D("0"),
                unrate_pct=_D("0"),
                indpro_pct=_D("0"),
                payems_pct=_D("0"),
                lei_pct=_D("0"),
            )
        )
        assert result is not None
        # With no positive or negative signals, trend should be stable
        assert result.trend == TrendDirection.STABLE


# ---------------------------------------------------------------------------
# Rate classifier tests
# ---------------------------------------------------------------------------


class TestClassifyRates:
    def test_rising_rates(self) -> None:
        result = classify_rates(_rate_data(ff_pct=_D("0.25")))
        assert result is not None
        assert result.regime == RateEnvironment.RISING
        assert result.trend == TrendDirection.DETERIORATING

    def test_falling_rates(self) -> None:
        result = classify_rates(_rate_data(ff_pct=_D("-0.25")))
        assert result is not None
        assert result.regime == RateEnvironment.FALLING
        assert result.trend == TrendDirection.IMPROVING

    def test_peak_high_stable_rates(self) -> None:
        result = classify_rates(
            _rate_data(ff_value=_D("5.5"), ff_pct=_D("0"), spread_value=_D("-0.5"))
        )
        assert result is not None
        assert result.regime == RateEnvironment.PEAK

    def test_trough_low_stable_rates(self) -> None:
        result = classify_rates(
            _rate_data(ff_value=_D("0.5"), ff_pct=_D("0"), spread_value=_D("2.0"))
        )
        assert result is not None
        assert result.regime == RateEnvironment.TROUGH

    def test_no_data_returns_none(self) -> None:
        result = classify_rates({})
        assert result is None

    def test_no_fedfunds_returns_none(self) -> None:
        """Rate classification requires FEDFUNDS — curve alone is insufficient."""
        data = {
            "T10Y2Y": _response(
                _reading("T10Y2Y", _D("0.5"), frequency="daily")
            ),
            "DGS10": _response(
                _reading("DGS10", _D("4.2"), frequency="daily")
            ),
        }
        result = classify_rates(data)
        assert result is None


# ---------------------------------------------------------------------------
# Inflation classifier tests
# ---------------------------------------------------------------------------


class TestClassifyInflation:
    def test_stable_inflation(self) -> None:
        result = classify_inflation(_inflation_data(cpi_pct=_D("0.2")))
        assert result is not None
        assert result.regime == InflationRegime.STABLE
        assert result.trend == TrendDirection.STABLE

    def test_disinflation(self) -> None:
        result = classify_inflation(_inflation_data(cpi_pct=_D("0.05")))
        assert result is not None
        assert result.regime == InflationRegime.DISINFLATION
        assert result.trend == TrendDirection.IMPROVING

    def test_reflation(self) -> None:
        result = classify_inflation(_inflation_data(cpi_pct=_D("0.5")))
        assert result is not None
        assert result.regime == InflationRegime.REFLATION
        assert result.trend == TrendDirection.DETERIORATING

    def test_stagflation(self) -> None:
        result = classify_inflation(
            _inflation_data(cpi_pct=_D("0.6"), unrate_pct=_D("0.3"))
        )
        assert result is not None
        assert result.regime == InflationRegime.STAGFLATION

    def test_no_cpi_returns_none(self) -> None:
        # Only has UNRATE, not CPIAUCSL
        data = {"UNRATE": _response(_reading("UNRATE", _D("4.0"), _D("0.1")))}
        result = classify_inflation(data)
        assert result is None


# ---------------------------------------------------------------------------
# Historical snapshot regression tests
# ---------------------------------------------------------------------------


class TestHistoricalSnapshots:
    """Regression tests using known historical macro conditions."""

    def test_2022_rate_hiking(self) -> None:
        """2022: Fed aggressively hiking, inflation high."""
        data = _rate_data(
            ff_value=_D("4.0"),
            ff_pct=_D("0.75"),  # 75bp hike
            spread_value=_D("-0.3"),  # inverted curve
        )
        result = classify_rates(data)
        assert result is not None
        assert result.regime == RateEnvironment.RISING

    def test_2020_trough(self) -> None:
        """2020: Near-zero rates, steep curve."""
        data = _rate_data(
            ff_value=_D("0.25"),
            ff_pct=_D("0"),
            spread_value=_D("1.5"),
        )
        result = classify_rates(data)
        assert result is not None
        assert result.regime == RateEnvironment.TROUGH

    def test_2008_contraction(self) -> None:
        """2008: Negative GDP, rising unemployment, declining production."""
        data = _growth_data(
            gdp_pct=_D("-4.0"),
            unrate_pct=_D("2.0"),
            indpro_pct=_D("-3.0"),
            payems_pct=_D("-2.0"),
            lei_pct=_D("-1.5"),
        )
        result = classify_growth(data)
        assert result is not None
        assert result.regime == GrowthRegime.CONTRACTION

    def test_1970s_stagflation(self) -> None:
        """1970s-style: High CPI + rising unemployment."""
        data = _inflation_data(cpi_pct=_D("0.8"), unrate_pct=_D("0.5"))
        result = classify_inflation(data)
        assert result is not None
        assert result.regime == InflationRegime.STAGFLATION


# ---------------------------------------------------------------------------
# Backward compatibility tests
# ---------------------------------------------------------------------------


class TestBackwardCompat:
    def test_legacy_regime_maps_all_growth_states(self) -> None:
        """All GrowthRegime values map to valid legacy strings."""
        for gr in GrowthRegime:
            report = MacroRegimeReport(
                growth=GrowthClassification(
                    regime=gr, contributing_indicators=["GDP"]
                ),
            )
            assert report.legacy_regime in ("EXPANSION", "CONTRACTION", "TRANSITION")

    def test_classify_macro_response_includes_report(self) -> None:
        """ClassifyMacroResponse can carry a regime_report."""
        from src.application.contracts.agents import ClassifyMacroResponse

        report = MacroRegimeReport(
            growth=GrowthClassification(
                regime=GrowthRegime.EXPANSION,
                contributing_indicators=["GDP"],
            ),
        )
        resp = ClassifyMacroResponse(
            content="Dashboard",
            regime="EXPANSION",
            indicators_fetched=5,
            indicators_with_data=5,
            regime_report=report,
        )
        dumped = resp.model_dump(mode="json")
        assert dumped["regime_report"]["growth"]["regime"] == "expansion"
        assert dumped["regime"] == "EXPANSION"
