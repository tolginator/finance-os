"""Tests for the ticker lookup service."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from src.application.contracts.ticker import TickerSummary, TickerTranscript
from src.application.services.ticker_service import (
    _cache,
    _safe_decimal,
    get_ticker_summary,
    get_ticker_transcript,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear ticker cache before each test."""
    _cache.clear()
    yield
    _cache.clear()


def _mock_ticker(info: dict | None = None, calendar: dict | None = None):
    """Create a mock yfinance Ticker."""
    mock = MagicMock()
    mock.info = info if info is not None else {
        "longName": "Apple Inc.",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "marketCap": 3000000000000,
        "currency": "USD",
        "currentPrice": 198.50,
        "previousClose": 197.25,
        "fiftyTwoWeekHigh": 220.00,
        "fiftyTwoWeekLow": 155.00,
        "longBusinessSummary": "Apple designs consumer electronics.",
    }
    mock.calendar = calendar or {}
    mock.earnings_call_transcripts = MagicMock(return_value=None)
    return mock


class TestSafeDecimal:
    def test_converts_number(self):
        assert _safe_decimal(198.50) == str(Decimal("198.5"))

    def test_converts_int(self):
        assert _safe_decimal(3000000000000) == "3000000000000"

    def test_returns_empty_on_none(self):
        assert _safe_decimal(None) == ""

    def test_returns_empty_on_invalid(self):
        assert _safe_decimal("not-a-number") == ""


class TestGetTickerSummary:
    @patch("src.application.services.ticker_service.yf.Ticker")
    async def test_returns_summary(self, mock_yf_ticker):
        mock_yf_ticker.return_value = _mock_ticker()

        result = await get_ticker_summary("AAPL")

        assert isinstance(result, TickerSummary)
        assert result.symbol == "AAPL"
        assert result.name == "Apple Inc."
        assert result.sector == "Technology"
        assert result.market_cap != ""
        assert result.current_price != ""

    @patch("src.application.services.ticker_service.yf.Ticker")
    async def test_caches_result(self, mock_yf_ticker):
        mock_yf_ticker.return_value = _mock_ticker()

        result1 = await get_ticker_summary("AAPL")
        result2 = await get_ticker_summary("AAPL")

        assert result1 is not result2  # defensive copy
        assert result1 == result2
        assert mock_yf_ticker.call_count == 1

    @patch("src.application.services.ticker_service.yf.Ticker")
    async def test_handles_minimal_info(self, mock_yf_ticker):
        mock_yf_ticker.return_value = _mock_ticker(info={})

        result = await get_ticker_summary("XYZ")

        assert result.symbol == "XYZ"
        assert result.name == "XYZ"
        assert result.sector == ""
        assert result.current_price == ""

    @patch("src.application.services.ticker_service.yf.Ticker")
    async def test_handles_earnings_date(self, mock_yf_ticker):
        mock_yf_ticker.return_value = _mock_ticker(
            calendar={"Earnings Date": ["2025-07-30"]}
        )

        result = await get_ticker_summary("AAPL")

        assert result.earnings_date == "2025-07-30"


class TestGetTickerTranscript:
    @patch("src.application.services.ticker_service.yf.Ticker")
    async def test_returns_unavailable_when_no_transcripts(self, mock_yf_ticker):
        mock_yf_ticker.return_value = _mock_ticker()

        result = await get_ticker_transcript("AAPL")

        assert isinstance(result, TickerTranscript)
        assert result.symbol == "AAPL"
        assert not result.available
        assert result.transcript == ""

    @patch("src.application.services.ticker_service.yf.Ticker")
    async def test_returns_transcript_when_available(self, mock_yf_ticker):
        mock = _mock_ticker()
        mock.earnings_call_transcripts = MagicMock(
            return_value=[{"content": "Q1 was great...", "period": "Q1 2025"}]
        )
        mock_yf_ticker.return_value = mock

        result = await get_ticker_transcript("AAPL")

        assert result.available
        assert "Q1 was great" in result.transcript
        assert result.period == "Q1 2025"

    @patch("src.application.services.ticker_service.yf.Ticker")
    async def test_handles_exception_gracefully(self, mock_yf_ticker):
        mock = _mock_ticker()
        mock.earnings_call_transcripts = MagicMock(side_effect=RuntimeError("network"))
        mock_yf_ticker.return_value = mock

        result = await get_ticker_transcript("AAPL")

        assert not result.available

    @patch("src.application.services.ticker_service.yf.Ticker")
    async def test_caches_transcript(self, mock_yf_ticker):
        mock_yf_ticker.return_value = _mock_ticker()

        result1 = await get_ticker_transcript("AAPL")
        result2 = await get_ticker_transcript("AAPL")

        assert result1 is not result2  # defensive copy
        assert result1 == result2
        assert mock_yf_ticker.call_count == 1
