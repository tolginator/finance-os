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
_CACHE_MAX_SIZE = 500

_cache: dict[str, tuple[float, object]] = {}
_inflight: dict[str, asyncio.Future[object]] = {}


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
    if len(_cache) >= _CACHE_MAX_SIZE:
        _cache_evict()
    _cache[key] = (time.monotonic(), val)


def _cache_evict() -> None:
    """Remove oldest entries to stay under max size."""
    entries = sorted(_cache.items(), key=lambda e: e[1][0])
    to_remove = len(_cache) - _CACHE_MAX_SIZE + _CACHE_MAX_SIZE // 4
    for k, _ in entries[:max(to_remove, 1)]:
        _cache.pop(k, None)


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
    normalized = symbol.upper()
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info or {}

        name = info.get("longName") or info.get("shortName") or normalized
        earnings_date = ""
        cal = getattr(ticker, "calendar", None)
        if isinstance(cal, dict) and "Earnings Date" in cal:
            dates = cal["Earnings Date"]
            if isinstance(dates, list) and dates:
                earnings_date = str(dates[0])
            elif dates:
                earnings_date = str(dates)

        return TickerSummary(
            symbol=normalized,
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
    except Exception:
        logger.warning("Summary fetch failed for %s", symbol, exc_info=True)
        return TickerSummary(
            symbol=normalized, name=normalized, sector="", industry="",
            market_cap="", currency="USD", current_price="",
            previous_close="", fifty_two_week_high="", fifty_two_week_low="",
            earnings_date="", description="",
        )


def _fetch_transcript_sync(symbol: str) -> TickerTranscript:
    """Synchronous earnings transcript fetch (best-effort, runs in thread)."""
    try:
        ticker = yf.Ticker(symbol)
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


async def _fetch_with_dedup(key: str, ttl: float, fetcher: object) -> object:
    """Fetch with cache and in-flight request deduplication."""
    cached = _cache_get(key, ttl)
    if cached is not None:
        return cached.model_copy(deep=True)  # type: ignore[union-attr]

    # Deduplicate concurrent requests for the same key
    if key in _inflight:
        result = await _inflight[key]
        return result.model_copy(deep=True)  # type: ignore[union-attr]

    loop = asyncio.get_running_loop()
    fut: asyncio.Future[object] = loop.create_future()
    # Suppress "Future exception was never retrieved" when no concurrent waiters
    fut.add_done_callback(lambda f: f.exception() if not f.cancelled() else None)
    _inflight[key] = fut
    try:
        result = await asyncio.to_thread(fetcher)  # type: ignore[arg-type]
        _cache_set(key, result)
        fut.set_result(result)
        return result.model_copy(deep=True)  # type: ignore[union-attr]
    except BaseException as exc:
        if not fut.done():
            fut.set_exception(exc)
        raise
    finally:
        _inflight.pop(key, None)


async def get_ticker_summary(symbol: str) -> TickerSummary:
    """Fetch company summary. Cached for 5 minutes."""
    key = f"summary:{symbol.upper()}"
    result = await _fetch_with_dedup(
        key, _SUMMARY_TTL, lambda: _fetch_summary_sync(symbol)
    )
    return result  # type: ignore[return-value]


async def get_ticker_transcript(symbol: str) -> TickerTranscript:
    """Fetch latest earnings transcript (best-effort). Cached for 1 hour."""
    key = f"transcript:{symbol.upper()}"
    result = await _fetch_with_dedup(
        key, _TRANSCRIPT_TTL, lambda: _fetch_transcript_sync(symbol)
    )
    return result  # type: ignore[return-value]
