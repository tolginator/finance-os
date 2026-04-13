"""Tests for the FastAPI web API layer.

Uses FastAPI TestClient with mocked services to verify endpoint behavior
without making external API or LLM calls.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.application.contracts.agents import (
    AnalyzeEarningsResponse,
    AssessRiskResponse,
    ChallengeThesisResponse,
    ClassifyMacroResponse,
    EvaluateThesisResponse,
    GenerateSignalsResponse,
    RunDigestResponse,
    RunPipelineResponse,
    SearchFilingsResponse,
)
from src.web_api import app, get_config


@pytest.fixture
def client():
    """TestClient for the FastAPI app."""
    return TestClient(app)


# --- Health & Info ---


class TestHealth:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_list_agents_returns_catalog(self, client):
        resp = client.get("/agents")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 7
        names = {a["name"] for a in data}
        assert "macro_regime" in names
        assert "filing_analyst" in names
        assert "adversarial" in names
        for agent in data:
            assert "name" in agent
            assert "description" in agent


# --- Agent Endpoints ---


def _mock_response(response_cls, **kwargs):
    """Build a mock service response."""
    defaults = {"content": "test output"}
    defaults.update(kwargs)
    return response_cls(**defaults)


class TestEarningsEndpoint:
    @patch("src.web_api.AgentService")
    def test_analyze_earnings_success(self, mock_cls, client):
        mock_svc = mock_cls.return_value
        mock_svc.analyze_earnings = AsyncMock(return_value=_mock_response(
            AnalyzeEarningsResponse,
            tone="positive", net_sentiment=0.7, confidence="high",
            guidance_direction="raised", guidance_count=3, key_phrase_count=5,
        ))
        resp = client.post("/agents/earnings_interpreter", json={
            "transcript": "Good quarter, revenue up 15%",
            "ticker": "AAPL",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["tone"] == "positive"
        assert data["guidance_count"] == 3

    def test_analyze_earnings_empty_transcript_422(self, client):
        resp = client.post("/agents/earnings_interpreter", json={
            "transcript": "",
        })
        assert resp.status_code == 422


class TestMacroEndpoint:
    @patch("src.web_api.AgentService")
    def test_classify_macro_success(self, mock_cls, client):
        mock_svc = mock_cls.return_value
        mock_svc.classify_macro = AsyncMock(return_value=_mock_response(
            ClassifyMacroResponse,
            regime="expansion", indicators_fetched=5, indicators_with_data=4,
        ))
        resp = client.post("/agents/macro_regime", json={
            "indicators": ["GDP", "UNRATE"],
        })
        assert resp.status_code == 200
        assert resp.json()["regime"] == "expansion"

    @patch("src.web_api.AgentService")
    def test_classify_macro_injects_api_key(self, mock_cls, client):
        mock_svc = mock_cls.return_value
        mock_svc.classify_macro = AsyncMock(return_value=_mock_response(
            ClassifyMacroResponse,
            regime="transition", indicators_fetched=0, indicators_with_data=0,
        ))
        resp = client.post("/agents/macro_regime", json={})
        assert resp.status_code == 200
        call_args = mock_svc.classify_macro.call_args[0][0]
        assert call_args.api_key == get_config().fred_api_key


class TestFilingEndpoint:
    @patch("src.web_api.AgentService")
    def test_search_filings_success(self, mock_cls, client):
        mock_svc = mock_cls.return_value
        mock_svc.search_filings = AsyncMock(return_value=_mock_response(
            SearchFilingsResponse,
            cik="320193", form_type="10-K", filing_count=5,
        ))
        resp = client.post("/agents/filing_analyst", json={
            "ticker": "AAPL",
        })
        assert resp.status_code == 200
        assert resp.json()["filing_count"] == 5


class TestQuantSignalEndpoint:
    @patch("src.web_api.AgentService")
    def test_generate_signals_success(self, mock_cls, client):
        mock_svc = mock_cls.return_value
        mock_svc.generate_signals = AsyncMock(return_value=_mock_response(
            GenerateSignalsResponse,
            agent="quant_signal", composite={"score": 0.7}, signals=[],
        ))
        resp = client.post("/agents/quant_signal", json={
            "signals": [{"name": "momentum", "value": 0.8, "weight": 1.0, "direction": "long"}],
        })
        assert resp.status_code == 200
        assert resp.json()["composite"]["score"] == 0.7


class TestThesisGuardianEndpoint:
    @patch("src.web_api.AgentService")
    def test_evaluate_thesis_success(self, mock_cls, client):
        mock_svc = mock_cls.return_value
        mock_svc.evaluate_thesis = AsyncMock(return_value=_mock_response(
            EvaluateThesisResponse,
            theses_checked=2, alerts_generated=1, critical_alerts=0,
        ))
        resp = client.post("/agents/thesis_guardian", json={
            "theses": [{"ticker": "AAPL", "hypothesis": "bull"}],
        })
        assert resp.status_code == 200
        assert resp.json()["theses_checked"] == 2


class TestRiskEndpoint:
    @patch("src.web_api.AgentService")
    def test_assess_risk_success(self, mock_cls, client):
        mock_svc = mock_cls.return_value
        mock_svc.assess_risk = AsyncMock(return_value=_mock_response(
            AssessRiskResponse,
        ))
        resp = client.post("/agents/risk_analyst", json={})
        assert resp.status_code == 200
        assert resp.json()["content"] == "test output"


class TestAdversarialEndpoint:
    @patch("src.web_api.AgentService")
    def test_challenge_thesis_success(self, mock_cls, client):
        mock_svc = mock_cls.return_value
        mock_svc.challenge_thesis = AsyncMock(return_value=_mock_response(
            ChallengeThesisResponse,
            conviction_score="0.65", counter_count=4, blind_spot_count=2,
        ))
        resp = client.post("/agents/adversarial", json={
            "claims": ["AAPL will grow revenue 20% YoY"],
        })
        assert resp.status_code == 200
        assert resp.json()["counter_count"] == 4


# --- Pipeline & Digest ---


class TestPipelineEndpoint:
    @patch("src.web_api.create_pipeline_service")
    def test_run_pipeline_success(self, mock_create, client):
        mock_svc = mock_create.return_value
        mock_svc.run_pipeline = AsyncMock(return_value=RunPipelineResponse(
            results=[{"task_id": "t1", "status": "success"}],
            total_duration_ms=150,
            successful=1,
            failed=0,
            memo=None,
        ))
        resp = client.post("/pipeline?ticker=AAPL", json={
            "tasks": [
                {"agent_name": "macro_regime", "prompt": "classify", "task_id": "t1"},
            ],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["successful"] == 1
        assert data["total_duration_ms"] == 150

    def test_run_pipeline_unknown_agent_400(self, client):
        resp = client.post("/pipeline", json={
            "tasks": [
                {"agent_name": "nonexistent_agent", "prompt": "test"},
            ],
        })
        assert resp.status_code == 400
        assert "nonexistent_agent" in resp.json()["detail"]

    def test_run_pipeline_empty_agent_name_422(self, client):
        resp = client.post("/pipeline", json={
            "tasks": [
                {"agent_name": "", "prompt": "test"},
            ],
        })
        assert resp.status_code == 422


class TestDigestEndpoint:
    @patch("src.web_api.DigestService")
    def test_run_digest_success(self, mock_cls, client):
        mock_svc = mock_cls.return_value
        mock_svc.run_digest = AsyncMock(return_value=RunDigestResponse(
            ticker_count=2,
            entry_count=5,
            alert_count=1,
            material_count=1,
            content="AAPL: positive; MSFT: neutral",
        ))
        resp = client.post("/digest", json={
            "tickers": ["AAPL", "MSFT"],
            "lookback_days": 7,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["ticker_count"] == 2
        assert data["entry_count"] == 5

    @patch("src.web_api.DigestService")
    def test_run_digest_custom_threshold(self, mock_cls, client):
        mock_svc = mock_cls.return_value
        mock_svc.run_digest = AsyncMock(return_value=RunDigestResponse(
            ticker_count=1, entry_count=0, alert_count=0,
            material_count=0, content="No material changes",
        ))
        resp = client.post("/digest", json={
            "tickers": ["IVV"],
            "alert_threshold": "0.8",
        })
        assert resp.status_code == 200
        call_req = mock_svc.run_digest.call_args[0][0]
        assert call_req.alert_threshold == Decimal("0.8")


# --- Error Handling ---


class TestErrorHandling:
    @patch("src.web_api.AgentService")
    def test_domain_value_error_returns_400(self, mock_cls, client):
        mock_svc = mock_cls.return_value
        mock_svc.analyze_earnings = AsyncMock(
            side_effect=ValueError("Invalid transcript format")
        )
        resp = client.post("/agents/earnings_interpreter", json={
            "transcript": "some text",
        })
        assert resp.status_code == 400
        assert "Invalid transcript format" in resp.json()["detail"]


# --- CORS ---


class TestCORS:
    def test_preflight_options_returns_cors_headers(self, client):
        resp = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.headers.get("access-control-allow-origin") is not None
        assert "GET" in resp.headers.get("access-control-allow-methods", "")

    def test_response_includes_cors_header(self, client):
        resp = client.get("/health", headers={"Origin": "http://localhost:3000"})
        assert resp.headers.get("access-control-allow-origin") is not None
