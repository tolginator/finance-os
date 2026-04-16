"""Tests for WatchlistStore — CRUD, persistence, invariants."""

import json
from pathlib import Path

import pytest

from src.application.watchlists import WatchlistNotFoundError, WatchlistStore


@pytest.fixture()
def store(tmp_path: Path) -> WatchlistStore:
    """WatchlistStore backed by a temp file."""
    return WatchlistStore(path=tmp_path / "watchlists.json")


class TestListAll:
    def test_empty_store_returns_default(self, store: WatchlistStore) -> None:
        result = store.list_all()
        assert result["active"] == "default"
        assert "default" in result["watchlists"]
        assert result["active_watchlist"] == {"tickers": []}

    def test_list_includes_active_watchlist_data(
        self, store: WatchlistStore,
    ) -> None:
        store.update("default", ["AAPL", "MSFT"])
        result = store.list_all()
        assert result["active_watchlist"]["tickers"] == ["AAPL", "MSFT"]


class TestCreate:
    def test_create_empty(self, store: WatchlistStore) -> None:
        result = store.create("tech")
        assert result == {"tickers": []}

    def test_create_with_tickers(self, store: WatchlistStore) -> None:
        result = store.create("energy", ["xom", "cvx"])
        assert result["tickers"] == ["CVX", "XOM"]

    def test_create_duplicate_rejects(self, store: WatchlistStore) -> None:
        store.create("tech")
        with pytest.raises(ValueError):
            store.create("tech")

    def test_create_normalizes_tickers(self, store: WatchlistStore) -> None:
        result = store.create("mixed", ["aapl", "AAPL", " msft "])
        assert result["tickers"] == ["AAPL", "MSFT"]


class TestGet:
    def test_get_existing(self, store: WatchlistStore) -> None:
        store.create("tech", ["NVDA"])
        result = store.get("tech")
        assert result["tickers"] == ["NVDA"]

    def test_get_nonexistent_raises(self, store: WatchlistStore) -> None:
        with pytest.raises(WatchlistNotFoundError):
            store.get("nonexistent")


class TestUpdate:
    def test_update_replaces_tickers(self, store: WatchlistStore) -> None:
        result = store.update("default", ["GOOG", "AMZN"])
        assert result["tickers"] == ["AMZN", "GOOG"]

    def test_update_nonexistent_raises(self, store: WatchlistStore) -> None:
        with pytest.raises(WatchlistNotFoundError):
            store.update("nonexistent", ["AAPL"])

    def test_update_deduplicates(self, store: WatchlistStore) -> None:
        result = store.update("default", ["AAPL", "aapl", "MSFT"])
        assert result["tickers"] == ["AAPL", "MSFT"]


class TestDelete:
    def test_delete_non_active(self, store: WatchlistStore) -> None:
        store.create("temp")
        store.delete("temp")
        with pytest.raises(WatchlistNotFoundError):
            store.get("temp")

    def test_delete_active_raises(self, store: WatchlistStore) -> None:
        with pytest.raises(ValueError):
            store.delete("default")

    def test_delete_nonexistent_raises(self, store: WatchlistStore) -> None:
        with pytest.raises(WatchlistNotFoundError):
            store.delete("nonexistent")


class TestActivate:
    def test_activate_switches(self, store: WatchlistStore) -> None:
        store.create("tech", ["NVDA"])
        result = store.activate("tech")
        assert result["active"] == "tech"
        assert result["watchlist"]["tickers"] == ["NVDA"]
        assert store.list_all()["active"] == "tech"

    def test_activate_nonexistent_raises(
        self, store: WatchlistStore,
    ) -> None:
        with pytest.raises(WatchlistNotFoundError):
            store.activate("nonexistent")


class TestNameValidation:
    def test_valid_names(self, store: WatchlistStore) -> None:
        for name in ["tech", "my-list", "a", "abc-123"]:
            assert store.validate_name(name) == name

    def test_invalid_names(self, store: WatchlistStore) -> None:
        for name in ["", "My List", "has spaces", "-leading", "a/b"]:
            with pytest.raises(ValueError):
                store.validate_name(name)

    def test_normalizes_case(self, store: WatchlistStore) -> None:
        assert store.validate_name("Tech") == "tech"


class TestPersistence:
    def test_survives_reload(self, tmp_path: Path) -> None:
        path = tmp_path / "watchlists.json"
        store1 = WatchlistStore(path=path)
        store1.update("default", ["AAPL", "MSFT"])
        store2 = WatchlistStore(path=path)
        assert store2.get("default")["tickers"] == ["AAPL", "MSFT"]

    def test_corrupt_file_resets(self, tmp_path: Path) -> None:
        path = tmp_path / "watchlists.json"
        path.write_text("not valid json!!!", encoding="utf-8")
        store = WatchlistStore(path=path)
        result = store.list_all()
        assert result["active"] == "default"

    def test_missing_keys_handled(self, tmp_path: Path) -> None:
        path = tmp_path / "watchlists.json"
        path.write_text("{}", encoding="utf-8")
        store = WatchlistStore(path=path)
        result = store.list_all()
        assert result["active"] == "default"


class TestInvariants:
    def test_active_always_exists(self, tmp_path: Path) -> None:
        path = tmp_path / "watchlists.json"
        bad_data = {"active": "gone", "watchlists": {"a": {"tickers": []}}}
        path.write_text(json.dumps(bad_data), encoding="utf-8")
        store = WatchlistStore(path=path)
        result = store.list_all()
        assert result["active"] in result["watchlists"]

    def test_empty_watchlists_gets_default(self, tmp_path: Path) -> None:
        path = tmp_path / "watchlists.json"
        bad_data = {"active": "default", "watchlists": {}}
        path.write_text(json.dumps(bad_data), encoding="utf-8")
        store = WatchlistStore(path=path)
        result = store.list_all()
        assert "default" in result["watchlists"]
