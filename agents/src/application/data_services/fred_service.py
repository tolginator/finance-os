"""FRED data service — Federal Reserve Economic Data.

Extracts the FRED fetching logic that was previously inline in
``macro_regime.py`` into a proper service with caching and freshness.
"""

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation

from src.application.data_services.base import (
    DataReading,
    DataResponse,
    FreshnessMetadata,
    FreshnessState,
    TTLCache,
)

logger = logging.getLogger(__name__)

FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

# Curated indicator catalog: series_id → (description, unit, frequency)
FRED_INDICATORS: dict[str, tuple[str, str, str]] = {
    # Existing (from v1)
    "GDP": ("Real GDP growth", "billions $", "quarterly"),
    "UNRATE": ("Unemployment rate", "%", "monthly"),
    "CPIAUCSL": ("Consumer Price Index (All Urban)", "index", "monthly"),
    "FEDFUNDS": ("Federal Funds Rate", "%", "monthly"),
    "T10Y2Y": ("10Y-2Y Treasury Spread", "%", "daily"),
    "UMCSENT": ("Consumer Sentiment (UMich)", "index", "monthly"),
    "INDPRO": ("Industrial Production Index", "index", "monthly"),
    "PAYEMS": ("Nonfarm Payrolls", "thousands", "monthly"),
    # New for enhanced data (#102)
    "HOUST": ("Housing Starts", "thousands", "monthly"),
    "MANEMP": ("Manufacturing Employment", "thousands", "monthly"),
    "USALOLITONOSTSAM": (
        "Leading Economic Index (OECD)",
        "index",
        "monthly",
    ),
    "BAMLH0A0HYM2": ("HY OAS Spread (ICE BofA)", "bps", "daily"),
    "DGS5": ("5-Year Treasury Rate", "%", "daily"),
    "DGS10": ("10-Year Treasury Rate", "%", "daily"),
    "DGS30": ("30-Year Treasury Rate", "%", "daily"),
    "DCOILWTICO": ("WTI Crude Oil Price", "$/barrel", "daily"),
}


class FREDService:
    """Fetch and cache FRED economic data series.

    Each instance holds its own TTL cache. Create one per process
    (web API, MCP server, CLI).
    """

    def __init__(self, api_key: str, cache_ttl: float = 3600.0) -> None:
        self._api_key = api_key
        self._cache = TTLCache(default_ttl=cache_ttl)

    # -- public API --------------------------------------------------------

    def fetch_series(
        self,
        series_id: str,
        limit: int = 12,
        *,
        bypass_cache: bool = False,
    ) -> DataResponse:
        """Fetch recent observations for a FRED series.

        Args:
            series_id: FRED series identifier (e.g. ``'GDP'``).
            limit: Max observations (most recent first). Clamped to 1–1000.
            bypass_cache: Skip cache lookup (still writes to cache).

        Returns:
            DataResponse with readings and freshness metadata.

        Raises:
            ValueError: If ``api_key`` is empty.
        """
        if not self._api_key:
            msg = "FRED API key required"
            raise ValueError(msg)

        limit = max(1, min(limit, 1000))
        cache_key = f"fred:{series_id}:{limit}"

        if not bypass_cache:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        raw = self._http_fetch(series_id, limit)
        readings = self._parse(series_id, raw)

        data_as_of: date | None = None
        if readings:
            data_as_of = readings[0].date

        response = DataResponse(
            readings=readings,
            freshness=FreshnessMetadata(
                source="fred",
                fetched_at=datetime.now(UTC),
                data_as_of=data_as_of,
                state=FreshnessState.FRESH,
            ),
        )
        self._cache.put(cache_key, response)
        return response

    def fetch_multiple(
        self,
        series_ids: list[str],
        limit: int = 12,
    ) -> dict[str, DataResponse]:
        """Fetch multiple series. Returns dict keyed by series_id."""
        results: dict[str, DataResponse] = {}
        for sid in series_ids:
            results[sid] = self.fetch_series(sid, limit=limit)
        return results

    @staticmethod
    def available_indicators() -> dict[str, tuple[str, str, str]]:
        """Return the curated indicator catalog."""
        return dict(FRED_INDICATORS)

    # -- internals ---------------------------------------------------------

    def _http_fetch(
        self, series_id: str, limit: int
    ) -> list[dict[str, str]]:
        """Raw HTTP fetch from FRED API."""
        params = urllib.parse.urlencode({
            "series_id": series_id,
            "api_key": self._api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": str(limit),
        })
        url = f"{FRED_BASE_URL}?{params}"
        req = urllib.request.Request(
            url, headers={"User-Agent": "finance-os/0.1.0"}
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
                return data.get("observations", [])
        except (urllib.error.URLError, json.JSONDecodeError) as exc:
            logger.warning("FRED fetch failed for %s: %s", series_id, exc)
            return []

    def _parse(
        self,
        series_id: str,
        observations: list[dict[str, str]],
    ) -> list[DataReading]:
        """Parse raw FRED JSON into DataReading objects."""
        meta = FRED_INDICATORS.get(series_id, (series_id, "", ""))
        description, unit, frequency = meta

        readings: list[DataReading] = []
        for i, obs in enumerate(observations):
            raw_val = obs.get("value", ".")
            if raw_val == ".":
                continue
            try:
                value = Decimal(raw_val)
            except InvalidOperation:
                continue

            raw_date = obs.get("date", "")
            try:
                obs_date = date.fromisoformat(raw_date)
            except ValueError:
                continue

            previous_value: Decimal | None = None
            pct_change: Decimal | None = None
            if i + 1 < len(observations):
                prev_raw = observations[i + 1].get("value", ".")
                if prev_raw != ".":
                    try:
                        previous_value = Decimal(prev_raw)
                        if previous_value != 0:
                            pct_change = (
                                (value - previous_value)
                                / previous_value
                                * 100
                            )
                    except InvalidOperation:
                        pass

            readings.append(
                DataReading(
                    series_id=series_id,
                    description=description,
                    date=obs_date,
                    value=value,
                    unit=unit,
                    frequency=frequency,
                    previous_value=previous_value,
                    pct_change=pct_change,
                )
            )

        return readings
