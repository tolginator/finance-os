"""Watchlist persistence — named ticker lists stored on disk.

Storage location: ~/.config/finance-os/watchlists.json
Separate from config.json to keep user state distinct from app config.

Thread-safe via threading.Lock (callers use asyncio.to_thread for
non-blocking access from async endpoints).
"""

import json
import logging
import re
import tempfile
import threading
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.application.config import CONFIG_DIR

WATCHLIST_FILE = CONFIG_DIR / "watchlists.json"
_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,48}[a-z0-9]$|^[a-z0-9]$")

logger = logging.getLogger(__name__)


class Watchlist(BaseModel):
    """A named list of ticker symbols."""

    tickers: list[str] = Field(default_factory=list)


class WatchlistData(BaseModel):
    """Root schema for watchlists.json."""

    active: str = "default"
    watchlists: dict[str, Watchlist] = Field(default_factory=dict)


class WatchlistStore:
    """Thread-safe watchlist persistence backed by a JSON file.

    All mutations use atomic writes (write to temp + rename) to
    prevent corruption from interrupted writes.
    """

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or WATCHLIST_FILE
        self._lock = threading.Lock()

    def _load(self) -> WatchlistData:
        """Load watchlist data from disk, creating defaults if needed."""
        if not self._path.is_file():
            data = self._default_data()
        else:
            try:
                raw = json.loads(self._path.read_text(encoding="utf-8"))
                data = WatchlistData.model_validate(raw)
            except (json.JSONDecodeError, ValueError):
                logger.warning(
                    "Corrupt watchlists.json at %s — resetting to defaults",
                    self._path,
                )
                data = self._default_data()
        self._ensure_invariants(data)
        return data

    def _save(self, data: WatchlistData) -> None:
        """Atomically write watchlist data to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(
            data.model_dump(), indent=2, ensure_ascii=False,
        )
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                dir=self._path.parent,
                suffix=".tmp",
                delete=False,
                encoding="utf-8",
            ) as fd:
                temp_path = Path(fd.name)
                fd.write(content)
                fd.flush()
            temp_path.replace(self._path)
        except BaseException:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
            raise

    @staticmethod
    def _default_data() -> WatchlistData:
        return WatchlistData(
            active="default",
            watchlists={"default": Watchlist()},
        )

    @staticmethod
    def _normalize_tickers(tickers: list[str]) -> list[str]:
        """Uppercase, deduplicate, sort."""
        seen: set[str] = set()
        result: list[str] = []
        for t in tickers:
            upper = t.strip().upper()
            if upper and upper not in seen:
                seen.add(upper)
                result.append(upper)
        result.sort()
        return result

    @staticmethod
    def validate_name(name: str) -> str:
        """Validate and normalize a watchlist name."""
        slug = name.strip().lower()
        if not _SLUG_PATTERN.match(slug):
            msg = (
                f"Invalid watchlist name '{name}'. "
                "Use lowercase letters, digits, and hyphens (1-50 chars)."
            )
            raise ValueError(msg)
        return slug

    def list_all(self) -> dict[str, Any]:
        """Return all watchlists with active indicator."""
        with self._lock:
            data = self._load()
            return {
                "active": data.active,
                "watchlists": {
                    name: wl.model_dump()
                    for name, wl in data.watchlists.items()
                },
                "active_watchlist": data.watchlists[
                    data.active
                ].model_dump(),
            }

    def get(self, name: str) -> dict[str, Any]:
        """Get a specific watchlist by name."""
        slug = self.validate_name(name)
        with self._lock:
            data = self._load()
            if slug not in data.watchlists:
                msg = f"Watchlist '{slug}' not found"
                raise KeyError(msg)
            return data.watchlists[slug].model_dump()

    def create(self, name: str, tickers: list[str] | None = None) -> dict[str, Any]:
        """Create a new watchlist."""
        slug = self.validate_name(name)
        normalized = self._normalize_tickers(tickers or [])
        with self._lock:
            data = self._load()
            if slug in data.watchlists:
                msg = f"Watchlist '{slug}' already exists"
                raise ValueError(msg)
            data.watchlists[slug] = Watchlist(tickers=normalized)
            self._save(data)
            return data.watchlists[slug].model_dump()

    def update(self, name: str, tickers: list[str]) -> dict[str, Any]:
        """Replace the ticker list for a watchlist."""
        slug = self.validate_name(name)
        normalized = self._normalize_tickers(tickers)
        with self._lock:
            data = self._load()
            if slug not in data.watchlists:
                msg = f"Watchlist '{slug}' not found"
                raise KeyError(msg)
            data.watchlists[slug] = Watchlist(tickers=normalized)
            self._save(data)
            return data.watchlists[slug].model_dump()

    def delete(self, name: str) -> None:
        """Delete a watchlist (cannot delete the active one)."""
        slug = self.validate_name(name)
        with self._lock:
            data = self._load()
            if slug not in data.watchlists:
                msg = f"Watchlist '{slug}' not found"
                raise KeyError(msg)
            if slug == data.active:
                msg = "Cannot delete the active watchlist"
                raise ValueError(msg)
            del data.watchlists[slug]
            self._save(data)

    def activate(self, name: str) -> dict[str, Any]:
        """Set a watchlist as active."""
        slug = self.validate_name(name)
        with self._lock:
            data = self._load()
            if slug not in data.watchlists:
                msg = f"Watchlist '{slug}' not found"
                raise KeyError(msg)
            data.active = slug
            self._save(data)
            return {
                "active": slug,
                "watchlist": data.watchlists[slug].model_dump(),
            }

    def _ensure_invariants(self, data: WatchlistData) -> None:
        """Guarantee at least one watchlist exists and active is valid."""
        if not data.watchlists:
            data.watchlists["default"] = Watchlist()
            data.active = "default"
        if data.active not in data.watchlists:
            data.active = next(iter(data.watchlists))
