"""Tests for the filing analyst agent."""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.agents.filing_analyst import (
    FilingAnalystAgent,
    _ticker_cik_cache,
    resolve_cik,
)
from src.core.agent import AgentResponse

# Sample SEC company_tickers.json response
MOCK_TICKERS_DATA = {
    "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    "1": {"cik_str": 789019, "ticker": "MSFT", "title": "Microsoft Corp"},
    "2": {"cik_str": 1318605, "ticker": "TSLA", "title": "Tesla, Inc."},
}

# Sample filings API response
MOCK_FILINGS_DATA = {
    "filings": {
        "recent": {
            "form": ["10-K", "10-Q", "10-K"],
            "accessionNumber": [
                "0000320193-24-000006",
                "0000320193-24-000005",
                "0000320193-23-000077",
            ],
            "filingDate": ["2024-11-01", "2024-08-02", "2023-11-03"],
            "primaryDocument": ["aapl-20240928.htm", "aapl-20240629.htm", "aapl-20230930.htm"],
            "primaryDocDescription": ["10-K", "10-Q", "10-K"],
        }
    }
}


def _mock_urlopen_tickers(req, timeout=15):
    """Mock urllib.request.urlopen for ticker resolution."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(MOCK_TICKERS_DATA).encode()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def _mock_urlopen_filings(req, timeout=15):
    """Mock urllib.request.urlopen for filings API."""
    url = req.full_url if hasattr(req, "full_url") else str(req)
    if "company_tickers.json" in url:
        return _mock_urlopen_tickers(req, timeout)
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(MOCK_FILINGS_DATA).encode()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


class TestResolveCIK:
    """Tests for ticker→CIK resolution."""

    def setup_method(self):
        _ticker_cik_cache.clear()

    def test_resolves_known_ticker(self):
        with patch("src.agents.filing_analyst.urllib.request.urlopen", _mock_urlopen_tickers):
            assert resolve_cik("AAPL") == "320193"
            assert resolve_cik("MSFT") == "789019"
            assert resolve_cik("TSLA") == "1318605"

    def test_case_insensitive(self):
        with patch("src.agents.filing_analyst.urllib.request.urlopen", _mock_urlopen_tickers):
            assert resolve_cik("aapl") == "320193"

    def test_unknown_ticker_returns_empty(self):
        with patch("src.agents.filing_analyst.urllib.request.urlopen", _mock_urlopen_tickers):
            assert resolve_cik("ZZZZ") == ""

    def test_caches_after_first_load(self):
        with patch("src.agents.filing_analyst.urllib.request.urlopen", _mock_urlopen_tickers):
            resolve_cik("AAPL")
            # Cache is now populated — second call shouldn't need HTTP
        # Clear the mock but keep the cache
        with patch(
            "src.agents.filing_analyst.urllib.request.urlopen",
            side_effect=AssertionError("should not be called"),
        ):
            # This should use cache, not call urlopen
            assert resolve_cik("MSFT") == "789019"

    def test_network_failure_returns_empty(self):
        import urllib.error
        with patch(
            "src.agents.filing_analyst.urllib.request.urlopen",
            side_effect=urllib.error.URLError("timeout"),
        ):
            assert resolve_cik("AAPL") == ""


class TestFilingAnalystAgent:
    """Tests for FilingAnalystAgent."""

    def setup_method(self):
        _ticker_cik_cache.clear()

    def test_system_prompt_content(self) -> None:
        agent = FilingAnalystAgent()
        prompt = agent.system_prompt
        assert "risk" in prompt.lower()
        assert "MD&A" in prompt
        assert "CapEx" in prompt

    @pytest.mark.asyncio
    async def test_run_without_input(self) -> None:
        agent = FilingAnalystAgent()
        response = await agent.run("")
        assert isinstance(response, AgentResponse)
        assert len(response.content) > 0

    @pytest.mark.asyncio
    async def test_ticker_auto_resolves_to_cik(self) -> None:
        """When given a ticker, agent resolves CIK and fetches filings."""
        agent = FilingAnalystAgent()
        with patch("src.agents.filing_analyst.urllib.request.urlopen", _mock_urlopen_filings):
            response = await agent.run("Search filings", ticker="AAPL")
        assert "320193" in response.content
        assert response.metadata.get("cik") == "320193"
        assert response.metadata.get("filing_count", 0) > 0

    @pytest.mark.asyncio
    async def test_cik_used_directly(self) -> None:
        """When CIK is provided, skip ticker resolution."""
        agent = FilingAnalystAgent()
        with patch("src.agents.filing_analyst.urllib.request.urlopen", _mock_urlopen_filings):
            response = await agent.run("Search filings", cik="320193")
        assert "320193" in response.content
        assert response.metadata.get("filing_count", 0) > 0

    @pytest.mark.asyncio
    async def test_ticker_resolution_failure_falls_back_to_search(self) -> None:
        """When ticker can't be resolved, falls back to EDGAR search."""
        import urllib.error

        call_count = 0

        def mock_urlopen(req, timeout=15):
            nonlocal call_count
            call_count += 1
            url = req.full_url if hasattr(req, "full_url") else str(req)
            if "company_tickers.json" in url:
                raise urllib.error.URLError("timeout")
            # Search API returns empty
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({"hits": {"hits": []}}).encode()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        agent = FilingAnalystAgent()
        with patch("src.agents.filing_analyst.urllib.request.urlopen", mock_urlopen):
            response = await agent.run("Search filings", ticker="AAPL")
        assert isinstance(response, AgentResponse)


class TestFilingAnalystLive:
    """Integration tests hitting real SEC EDGAR APIs."""

    def setup_method(self):
        _ticker_cik_cache.clear()

    @pytest.mark.integration
    def test_resolve_cik_msft(self):
        """Resolve MSFT to a real CIK."""
        cik = resolve_cik("MSFT")
        assert cik == "789019"

    @pytest.mark.integration
    def test_resolve_cik_aapl(self):
        """Resolve AAPL to a real CIK."""
        cik = resolve_cik("AAPL")
        assert cik == "320193"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_run_with_ticker_msft(self):
        """Run filing analyst with MSFT ticker — should return real filings."""
        agent = FilingAnalystAgent()
        response = await agent.run("Search filings for MSFT", ticker="MSFT")
        assert isinstance(response, AgentResponse)
        assert "789019" in response.content
        assert response.metadata.get("cik") == "789019"
        assert response.metadata.get("filing_count", 0) > 0
        # Should have actual filing data
        filings = response.metadata.get("filings", [])
        assert len(filings) > 0
        assert filings[0].get("form") == "10-K"
        assert filings[0].get("date")  # has a filing date

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_run_with_ticker_aapl_10q(self):
        """Run filing analyst with AAPL ticker for 10-Q filings."""
        agent = FilingAnalystAgent()
        response = await agent.run("Search filings", ticker="AAPL", form_type="10-Q")
        assert response.metadata.get("cik") == "320193"
        assert response.metadata.get("filing_count", 0) > 0
        assert response.metadata.get("form_type") == "10-Q"
