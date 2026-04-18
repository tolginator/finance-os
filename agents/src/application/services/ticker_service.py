"""Ticker lookup service — auto-discover company data from Yahoo Finance.

Wraps yfinance with caching and graceful degradation. All yfinance calls
are dispatched to a thread to avoid blocking the async event loop.
"""

import asyncio
import logging
import time
from decimal import Decimal, InvalidOperation

import yfinance as yf

from src.application.contracts.ticker import TickerSummary, TickerTranscript

logger = logging.getLogger(__name__)

# Per-endpoint TTL caching (seconds)
_SUMMARY_TTL = 300  # 5 minutes
_TRANSCRIPT_TTL = 3600  # 1 hour

_cache: dict[str, tuple[float, object]] = {}


def _cache_get(key: str, ttl: float) -> object | None:
    """Return cached value if within TTL, else None."""
    entry = _cache.get(key)
    if entry is None:
        return None
    ts, val = entry
    if time.monotonic() - ts > ttl:
        del _cache[key]
        return None
    return val


def _cache_set(key: str, val: object) -> None:
    _cache[key] = (time.monotonic(), val)


def _safe_decimal(val: object) -> str:
    """Convert a numeric value to decimal string, or empty string on failure."""
    if val is None:
        return ""
    try:
        return str(Decimal(str(val)))
    except (InvalidOperation, ValueError):
        return ""


def _fetch_summary_sync(symbol: str) -> TickerSummary:
    """Synchronous Yahoo Finance summary fetch (runs in thread)."""
    ticker = yf.Ticker(symbol)
    info = ticker.info or {}

    name = info.get("longName") or info.get("shortName") or symbol
    earnings_date = ""
    cal = getattr(ticker, "calendar", None)
    if isinstance(cal, dict) and "Earnings Date" in cal:
        dates = cal["Earnings Date"]
        if isinstance(dates, list) and dates:
            earnings_date = str(dates[0])
        elif dates:
            earnings_date = str(dates)

    return TickerSummary(
        symbol=symbol.upper(),
        name=name,
        sector=info.get("sector", ""),
        industry=info.get("industry", ""),
        market_cap=_safe_decimal(info.get("marketCap")),
        currency=info.get("currency", "USD"),
        current_price=_safe_decimal(
            info.get("currentPrice") or info.get("regularMarketPrice")
        ),
        previous_close=_safe_decimal(info.get("previousClose")),
        fifty_two_week_high=_safe_decimal(info.get("fiftyTwoWeekHigh")),
        fifty_two_week_low=_safe_decimal(info.get("fiftyTwoWeekLow")),
        earnings_date=earnings_date,
        description=info.get("longBusinessSummary", ""),
    )


def _fetch_transcript_sync(symbol: str) -> TickerTranscript:
    """Synchronous earnings transcript fetch (best-effort, runs in thread)."""
    ticker = yf.Ticker(symbol)
    try:
        transcripts = getattr(ticker, "earnings_call_transcripts", None)
        if transcripts is not None and callable(transcripts):
            transcripts = transcripts()

        if not transcripts:
            return TickerTranscript(symbol=symbol.upper(), available=False)

        # yfinance returns list of transcript dicts — take the latest
        if isinstance(transcripts, list) and transcripts:
            latest = transcripts[0]
            text = latest if isinstance(latest, str) else str(latest.get("content", latest))
            period = latest.get("period", "") if isinstance(latest, dict) else ""
            return TickerTranscript(
                symbol=symbol.upper(),
                available=True,
                transcript=text,
                period=period,
            )

        return TickerTranscript(symbol=symbol.upper(), available=False)
    except Exception:
        logger.warning("Transcript fetch failed for %s", symbol, exc_info=True)
        return TickerTranscript(symbol=symbol.upper(), available=False)


async def get_ticker_summary(symbol: str) -> TickerSummary:
    """Fetch company summary. Cached for 5 minutes."""
    key = f"summary:{symbol.upper()}"
    cached = _cache_get(key, _SUMMARY_TTL)
    if cached is not None:
        return cached  # type: ignore[return-value]

    result = await asyncio.to_thread(_fetch_summary_sync, symbol)
    _cache_set(key, result)
    return result


async def get_ticker_transcript(symbol: str) -> TickerTranscript:
    """Fetch latest earnings transcript (best-effort). Cached for 1 hour."""
    key = f"transcript:{symbol.upper()}"
    cached = _cache_get(key, _TRANSCRIPT_TTL)
    if cached is not None:
        return cached  # type: ignore[return-value]

    result = await asyncio.to_thread(_fetch_transcript_sync, symbol)
    _cache_set(key, result)
    return result
