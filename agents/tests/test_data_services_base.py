"""Tests for data services — base types and TTL cache."""

from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import patch

from src.application.data_services.base import (
    DataReading,
    DataResponse,
    FreshnessMetadata,
    FreshnessState,
    TTLCache,
)


def _sample_response(series_id: str = "TEST") -> DataResponse:
    """Build a minimal DataResponse for cache tests."""
    return DataResponse(
        readings=[
            DataReading(
                series_id=series_id,
                description="Test series",
                date=date(2024, 1, 1),
                value=Decimal("100"),
            ),
        ],
        freshness=FreshnessMetadata(
            source="test",
            fetched_at=datetime.now(UTC),
            data_as_of=date(2024, 1, 1),
            state=FreshnessState.FRESH,
        ),
    )


class TestDataReading:
    def test_minimal_construction(self) -> None:
        r = DataReading(
            series_id="GDP",
            description="Real GDP",
            date=date(2024, 1, 1),
            value=Decimal("100.5"),
        )
        assert r.series_id == "GDP"
        assert r.unit == ""
        assert r.geography == "US"

    def test_full_construction(self) -> None:
        r = DataReading(
            series_id="UNRATE",
            description="Unemployment",
            date=date(2024, 3, 1),
            value=Decimal("3.8"),
            unit="%",
            frequency="monthly",
            geography="US",
            previous_value=Decimal("3.9"),
            pct_change=Decimal("-2.56"),
        )
        assert r.pct_change == Decimal("-2.56")
        assert r.previous_value == Decimal("3.9")


class TestFreshnessMetadata:
    def test_defaults(self) -> None:
        f = FreshnessMetadata(source="fred")
        assert f.state == FreshnessState.FRESH
        assert f.reason is None
        assert f.fetched_at is not None

    def test_stale_with_reason(self) -> None:
        f = FreshnessMetadata(
            source="bls",
            state=FreshnessState.STALE,
            reason="cached",
        )
        assert f.state == FreshnessState.STALE
        assert f.reason == "cached"


class TestTTLCache:
    def test_put_and_get(self) -> None:
        cache = TTLCache(default_ttl=60.0)
        resp = _sample_response()
        cache.put("k1", resp)
        result = cache.get("k1")
        assert result is not None
        assert len(result.readings) == 1
        assert result.freshness.state == FreshnessState.STALE
        assert result.freshness.reason == "cached"

    def test_miss_returns_none(self) -> None:
        cache = TTLCache()
        assert cache.get("missing") is None

    def test_expired_entry_returns_none(self) -> None:
        _mono = "src.application.data_services.base.time.monotonic"
        with patch(_mono, return_value=1000.0):
            cache = TTLCache(default_ttl=10.0)
            cache.put("k", _sample_response())
        with patch(_mono, return_value=1011.0):
            assert cache.get("k") is None

    def test_custom_ttl_per_entry(self) -> None:
        _mono = "src.application.data_services.base.time.monotonic"
        with patch(_mono, return_value=1000.0):
            cache = TTLCache(default_ttl=10.0)
            cache.put("short", _sample_response(), ttl=5.0)
            cache.put("long", _sample_response("LONG"), ttl=60.0)
        with patch(_mono, return_value=1006.0):
            assert cache.get("short") is None
            assert cache.get("long") is not None

    def test_invalidate(self) -> None:
        cache = TTLCache()
        cache.put("k", _sample_response())
        cache.invalidate("k")
        assert cache.get("k") is None

    def test_clear(self) -> None:
        cache = TTLCache()
        cache.put("a", _sample_response())
        cache.put("b", _sample_response())
        cache.clear()
        assert cache.get("a") is None
        assert cache.get("b") is None

    def test_invalidate_nonexistent_is_noop(self) -> None:
        cache = TTLCache()
        cache.invalidate("nope")  # should not raise
