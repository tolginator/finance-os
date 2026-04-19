"""Tests for FRED data service — parsing, caching, indicator catalog."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from src.application.data_services.base import FreshnessState
from src.application.data_services.fred_service import (
    FRED_INDICATORS,
    FREDService,
)


class TestFREDIndicatorCatalog:
    def test_original_eight_present(self) -> None:
        original = {"GDP", "UNRATE", "CPIAUCSL", "FEDFUNDS",
                     "T10Y2Y", "UMCSENT", "INDPRO", "PAYEMS"}
        assert original.issubset(FRED_INDICATORS.keys())

    def test_new_indicators_present(self) -> None:
        new = {"HOUST", "MANEMP", "USALOLITONOSTSAM",
               "BAMLH0A0HYM2", "DGS5", "DGS10", "DGS30", "DCOILWTICO"}
        assert new.issubset(FRED_INDICATORS.keys())

    def test_catalog_has_description_unit_frequency(self) -> None:
        for sid, (desc, unit, freq) in FRED_INDICATORS.items():
            assert desc, f"{sid} missing description"
            assert unit, f"{sid} missing unit"
            assert freq, f"{sid} missing frequency"

    def test_available_indicators_returns_copy(self) -> None:
        a = FREDService.available_indicators()
        b = FREDService.available_indicators()
        assert a == b
        assert a is not b


class TestFREDServiceParsing:
    """Test parsing logic with mocked HTTP."""

    def _service(self) -> FREDService:
        return FREDService(api_key="test-key")

    def test_parse_valid_observations(self) -> None:
        svc = self._service()
        raw = [
            {"date": "2024-03-01", "value": "105.0"},
            {"date": "2024-02-01", "value": "100.0"},
        ]
        readings = svc._parse("INDPRO", raw)
        assert len(readings) == 2
        assert readings[0].value == Decimal("105.0")
        assert readings[0].pct_change == Decimal("5")
        assert readings[0].unit == "index"
        assert readings[0].frequency == "monthly"
        assert readings[0].date == date(2024, 3, 1)

    def test_parse_skips_dot_values(self) -> None:
        svc = self._service()
        raw = [
            {"date": "2024-03-01", "value": "."},
            {"date": "2024-02-01", "value": "100.0"},
        ]
        readings = svc._parse("GDP", raw)
        assert len(readings) == 1
        assert readings[0].date == date(2024, 2, 1)

    def test_parse_empty_observations(self) -> None:
        svc = self._service()
        assert svc._parse("GDP", []) == []

    def test_parse_unknown_series_uses_id_as_description(self) -> None:
        svc = self._service()
        raw = [{"date": "2024-01-01", "value": "42"}]
        readings = svc._parse("CUSTOM_SERIES", raw)
        assert readings[0].description == "CUSTOM_SERIES"

    def test_parse_skips_invalid_decimal(self) -> None:
        svc = self._service()
        raw = [{"date": "2024-01-01", "value": "N/A"}]
        assert svc._parse("GDP", raw) == []

    def test_parse_skips_invalid_date(self) -> None:
        svc = self._service()
        raw = [{"date": "not-a-date", "value": "100"}]
        assert svc._parse("GDP", raw) == []


class TestFREDServiceFetch:
    """Test fetch logic with mocked HTTP."""

    def _mock_observations(self) -> list[dict[str, str]]:
        return [
            {"date": "2024-03-01", "value": "105.0"},
            {"date": "2024-02-01", "value": "100.0"},
        ]

    def test_fetch_series_returns_data_response(self) -> None:
        svc = FREDService(api_key="test-key")
        with patch.object(svc, "_http_fetch", return_value=self._mock_observations()):
            resp = svc.fetch_series("INDPRO", limit=2)

        assert len(resp.readings) == 2
        assert resp.freshness.source == "fred"
        assert resp.freshness.state == FreshnessState.FRESH
        assert resp.freshness.data_as_of == date(2024, 3, 1)

    def test_fetch_series_caches_result(self) -> None:
        svc = FREDService(api_key="test-key")
        with patch.object(svc, "_http_fetch", return_value=self._mock_observations()) as mock:
            svc.fetch_series("INDPRO")
            svc.fetch_series("INDPRO")
            assert mock.call_count == 1

    def test_fetch_series_bypass_cache(self) -> None:
        svc = FREDService(api_key="test-key")
        with patch.object(svc, "_http_fetch", return_value=self._mock_observations()) as mock:
            svc.fetch_series("INDPRO")
            svc.fetch_series("INDPRO", bypass_cache=True)
            assert mock.call_count == 2

    def test_cached_response_marked_stale(self) -> None:
        svc = FREDService(api_key="test-key")
        with patch.object(svc, "_http_fetch", return_value=self._mock_observations()):
            svc.fetch_series("INDPRO")
            cached = svc.fetch_series("INDPRO")

        assert cached.freshness.state == FreshnessState.STALE
        assert cached.freshness.reason == "cached"

    def test_fetch_series_requires_api_key(self) -> None:
        svc = FREDService(api_key="")
        with pytest.raises(ValueError, match="FRED API key required"):
            svc.fetch_series("GDP")

    def test_fetch_series_clamps_limit(self) -> None:
        svc = FREDService(api_key="test-key")
        with patch.object(svc, "_http_fetch", return_value=[]) as mock:
            svc.fetch_series("GDP", limit=0)
            mock.assert_called_once_with("GDP", 1)

            mock.reset_mock()
            svc.fetch_series("GDP", limit=9999, bypass_cache=True)
            mock.assert_called_once_with("GDP", 1000)

    def test_fetch_multiple(self) -> None:
        svc = FREDService(api_key="test-key")
        with patch.object(svc, "_http_fetch", return_value=self._mock_observations()):
            results = svc.fetch_multiple(["GDP", "UNRATE"])

        assert "GDP" in results
        assert "UNRATE" in results
        assert len(results["GDP"].readings) == 2

    def test_http_failure_returns_empty(self) -> None:
        svc = FREDService(api_key="test-key")
        with patch.object(
            svc, "_http_fetch", return_value=[]
        ):
            resp = svc.fetch_series("GDP")
        assert resp.readings == []
        assert resp.freshness.data_as_of is None


@pytest.mark.integration
class TestFREDServiceLive:
    """Live FRED API tests — skipped when API key is not configured."""

    def test_fetch_single_series(self, fred_api_key: str) -> None:
        svc = FREDService(api_key=fred_api_key)
        resp = svc.fetch_series("UNRATE", limit=3)
        assert len(resp.readings) > 0
        assert resp.freshness.source == "fred"
        assert resp.freshness.data_as_of is not None

    def test_fetch_new_indicator(self, fred_api_key: str) -> None:
        svc = FREDService(api_key=fred_api_key)
        resp = svc.fetch_series("HOUST", limit=3)
        assert len(resp.readings) > 0
        assert resp.readings[0].unit == "thousands"
