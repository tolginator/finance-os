"""Base types for data services — readings, freshness, caching.

Not an ABC with generic fetch_series; each provider has typed methods.
Shared types and the in-memory TTL cache live here.
"""

import time
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Freshness
# ---------------------------------------------------------------------------


class FreshnessState(StrEnum):
    """Explicit staleness categories — no vague 0-1 float."""

    FRESH = "fresh"
    STALE = "stale"
    PROVISIONAL = "provisional"
    INTERPOLATED = "interpolated"


class FreshnessMetadata(BaseModel):
    """Describes how fresh a data response is."""

    source: str = Field(description="Provider name (e.g. 'fred', 'bls')")
    fetched_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )
    data_as_of: date | None = Field(
        default=None, description="Date of newest observation"
    )
    state: FreshnessState = FreshnessState.FRESH
    reason: str | None = Field(
        default=None,
        description="Why state is not FRESH (e.g. 'cached', 'interpolated gap')",
    )
    served_from_cache: bool = False


# ---------------------------------------------------------------------------
# Data readings
# ---------------------------------------------------------------------------


class DataReading(BaseModel):
    """A single observation from an economic data series."""

    series_id: str
    description: str
    date: date
    value: Decimal
    unit: str = ""
    frequency: str = ""
    geography: str = "US"
    previous_value: Decimal | None = None
    pct_change: Decimal | None = None


class DataResponse(BaseModel):
    """Wrapper for a batch of readings plus freshness metadata."""

    readings: list[DataReading]
    freshness: FreshnessMetadata


# ---------------------------------------------------------------------------
# TTL cache
# ---------------------------------------------------------------------------


class _CacheEntry:
    """Internal cache entry with expiration."""

    __slots__ = ("response", "expires_at")

    def __init__(self, response: DataResponse, ttl_seconds: float) -> None:
        self.response = response
        self.expires_at = time.monotonic() + ttl_seconds


class TTLCache:
    """Simple in-memory TTL cache keyed by string.

    Thread-safe for single-writer (GIL protects dict mutations).
    Not shared across processes — each Web API / MCP / CLI process
    has its own cache instance.
    """

    def __init__(self, default_ttl: float = 3600.0) -> None:
        self._store: dict[str, _CacheEntry] = {}
        self._default_ttl = default_ttl

    def get(self, key: str) -> DataResponse | None:
        """Return deep-copied cached response if not expired, else None."""
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.monotonic() > entry.expires_at:
            self._store.pop(key, None)
            return None
        # Deep copy to isolate callers from cached data
        resp = entry.response.model_copy(deep=True)
        resp.freshness.served_from_cache = True
        return resp

    def put(
        self, key: str, response: DataResponse, ttl: float | None = None
    ) -> None:
        """Store a deep copy of response with TTL."""
        self._store[key] = _CacheEntry(
            response.model_copy(deep=True),
            self._default_ttl if ttl is None else ttl,
        )

    def invalidate(self, key: str) -> None:
        """Remove a specific key."""
        self._store.pop(key, None)

    def clear(self) -> None:
        """Drop all entries."""
        self._store.clear()
