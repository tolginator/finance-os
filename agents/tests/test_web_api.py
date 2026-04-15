"""Tests for the FastAPI web API layer.

Uses FastAPI TestClient with mocked services to verify endpoint behavior
without making external API or LLM calls.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import src.web_api as _web_api_module
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
from src.application.registry import AGENT_CATALOG
from src.core.knowledge_graph import KnowledgeGraph
from src.web_api import app, get_config


@pytest.fixture
def client(tmp_path):
    """TestClient with fresh KG graph and temp watchlist store per test."""
    get_config.cache_clear()
    original_graph = _web_api_module._kg_graph
    _web_api_module._kg_graph = KnowledgeGraph()
    from src.application.watchlists import WatchlistStore
    original_store = _web_api_module._watchlist_store
    _web_api_module._watchlist_store = WatchlistStore(
        path=tmp_path / "watchlists.json",
    )
    with TestClient(app) as test_client:
        yield test_client
    _web_api_module._watchlist_store = original_store
    _web_api_module._kg_graph = original_graph
    get_config.cache_clear()


# --- Health & Info ---


class TestHealth:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_list_agents_returns_exact_catalog(self, client):
        resp = client.get("/agents")
        assert resp.status_code == 200
        data = resp.json()
        expected_names = {info["name"] for info in AGENT_CATALOG}
        actual_names = {a["name"] for a in data}
        assert actual_names == expected_names
        for agent in data:
            assert "name" in agent
            assert "description" in agent
            assert len(agent["description"]) > 0


# --- Agent Endpoints ---


def _mock_response(response_cls, **kwargs):
    """Build a mock service response."""
    defaults = {"content": "test output"}
    defaults.update(kwargs)
    return response_cls(**defaults)


class TestEarningsEndpoint:
    @patch("src.web_api.AgentService")
    def test_analyze_earnings_forwards_request(self, mock_cls, client):
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
        call_req = mock_svc.analyze_earnings.call_args[0][0]
        assert call_req.transcript == "Good quarter, revenue up 15%"
        assert call_req.ticker == "AAPL"
        data = resp.json()
        assert data["tone"] == "positive"
        assert data["guidance_count"] == 3

    def test_analyze_earnings_empty_transcript_422(self, client):
        resp = client.post("/agents/earnings_interpreter", json={
            "transcript": "",
        })
        assert resp.status_code == 422

    def test_analyze_earnings_missing_transcript_422(self, client):
        resp = client.post("/agents/earnings_interpreter", json={})
        assert resp.status_code == 422


class TestMacroEndpoint:
    @patch("src.web_api.AgentService")
    def test_classify_macro_forwards_indicators(self, mock_cls, client):
        mock_svc = mock_cls.return_value
        mock_svc.classify_macro = AsyncMock(return_value=_mock_response(
            ClassifyMacroResponse,
            regime="expansion", indicators_fetched=5, indicators_with_data=4,
        ))
        resp = client.post("/agents/macro_regime", json={
            "indicators": ["GDP", "UNRATE"],
        })
        assert resp.status_code == 200
        call_req = mock_svc.classify_macro.call_args[0][0]
        assert call_req.indicators == ["GDP", "UNRATE"]
        assert resp.json()["regime"] == "expansion"

    @patch("src.web_api.get_config")
    @patch("src.web_api.AgentService")
    def test_classify_macro_injects_api_key_when_missing(
        self, mock_cls, mock_get_config, client,
    ):
        sentinel_key = "SENTINEL_FRED_KEY_12345"
        mock_cfg = MagicMock()
        mock_cfg.fred_api_key = sentinel_key
        mock_get_config.return_value = mock_cfg
        mock_svc = mock_cls.return_value
        mock_svc.classify_macro = AsyncMock(return_value=_mock_response(
            ClassifyMacroResponse,
            regime="transition", indicators_fetched=0, indicators_with_data=0,
        ))
        resp = client.post("/agents/macro_regime", json={})
        assert resp.status_code == 200
        call_req = mock_svc.classify_macro.call_args[0][0]
        assert call_req.api_key == sentinel_key

    @patch("src.web_api.AgentService")
    def test_classify_macro_preserves_explicit_api_key(self, mock_cls, client):
        mock_svc = mock_cls.return_value
        mock_svc.classify_macro = AsyncMock(return_value=_mock_response(
            ClassifyMacroResponse,
            regime="expansion", indicators_fetched=0, indicators_with_data=0,
        ))
        resp = client.post("/agents/macro_regime", json={
            "api_key": "USER_PROVIDED_KEY",
        })
        assert resp.status_code == 200
        call_req = mock_svc.classify_macro.call_args[0][0]
        assert call_req.api_key == "USER_PROVIDED_KEY"

    def test_classify_macro_wrong_type_indicators_422(self, client):
        resp = client.post("/agents/macro_regime", json={
            "indicators": "GDP",
        })
        assert resp.status_code == 422


class TestFilingEndpoint:
    @patch("src.web_api.AgentService")
    def test_search_filings_forwards_ticker(self, mock_cls, client):
        mock_svc = mock_cls.return_value
        mock_svc.search_filings = AsyncMock(return_value=_mock_response(
            SearchFilingsResponse,
            cik="320193", form_type="10-K", filing_count=5,
        ))
        resp = client.post("/agents/filing_analyst", json={
            "ticker": "AAPL",
            "form_type": "10-Q",
        })
        assert resp.status_code == 200
        call_req = mock_svc.search_filings.call_args[0][0]
        assert call_req.ticker == "AAPL"
        assert call_req.form_type == "10-Q"
        assert resp.json()["filing_count"] == 5

    @patch("src.web_api.AgentService")
    def test_search_filings_service_error_returns_400(self, mock_cls, client):
        mock_svc = mock_cls.return_value
        mock_svc.search_filings = AsyncMock(
            side_effect=ValueError("CIK not found for ticker"),
        )
        resp = client.post("/agents/filing_analyst", json={"ticker": "INVALID"})
        assert resp.status_code == 400
        assert "detail" in resp.json()


class TestQuantSignalEndpoint:
    @patch("src.web_api.AgentService")
    def test_generate_signals_forwards_input(self, mock_cls, client):
        mock_svc = mock_cls.return_value
        mock_svc.generate_signals = AsyncMock(return_value=_mock_response(
            GenerateSignalsResponse,
            agent="quant_signal", composite={"score": 0.7}, signals=[],
        ))
        signals_input = [
            {"name": "momentum", "value": 0.8, "weight": 1.0, "direction": "long"},
        ]
        resp = client.post("/agents/quant_signal", json={
            "signals": signals_input,
            "method": "weighted",
        })
        assert resp.status_code == 200
        call_req = mock_svc.generate_signals.call_args[0][0]
        assert len(call_req.signals) == 1
        assert call_req.signals[0]["name"] == "momentum"
        assert call_req.method == "weighted"

    def test_generate_signals_invalid_sentiment_422(self, client):
        resp = client.post("/agents/quant_signal", json={
            "sentiment": "not_a_number",
        })
        assert resp.status_code == 422


class TestThesisGuardianEndpoint:
    @patch("src.web_api.AgentService")
    def test_evaluate_thesis_forwards_theses(self, mock_cls, client):
        mock_svc = mock_cls.return_value
        mock_svc.evaluate_thesis = AsyncMock(return_value=_mock_response(
            EvaluateThesisResponse,
            theses_checked=2, alerts_generated=1, critical_alerts=0,
        ))
        theses_input = [{"ticker": "AAPL", "hypothesis": "bull"}]
        resp = client.post("/agents/thesis_guardian", json={
            "theses": theses_input,
        })
        assert resp.status_code == 200
        call_req = mock_svc.evaluate_thesis.call_args[0][0]
        assert call_req.theses == theses_input
        assert resp.json()["theses_checked"] == 2

    def test_evaluate_thesis_missing_theses_422(self, client):
        resp = client.post("/agents/thesis_guardian", json={})
        assert resp.status_code == 422


class TestRiskEndpoint:
    @patch("src.web_api.AgentService")
    def test_assess_risk_forwards_positions(self, mock_cls, client):
        mock_svc = mock_cls.return_value
        mock_svc.assess_risk = AsyncMock(return_value=_mock_response(
            AssessRiskResponse,
        ))
        positions = [{"ticker": "AAPL", "weight": 0.5, "returns": [0.01, -0.02]}]
        resp = client.post("/agents/risk_analyst", json={
            "positions": positions,
        })
        assert resp.status_code == 200
        call_req = mock_svc.assess_risk.call_args[0][0]
        assert len(call_req.positions) == 1
        assert call_req.positions[0]["ticker"] == "AAPL"

    def test_assess_risk_wrong_type_returns_422(self, client):
        resp = client.post("/agents/risk_analyst", json={
            "returns": "not_a_list",
        })
        assert resp.status_code == 422


class TestAdversarialEndpoint:
    @patch("src.web_api.AgentService")
    def test_challenge_thesis_forwards_claims(self, mock_cls, client):
        mock_svc = mock_cls.return_value
        mock_svc.challenge_thesis = AsyncMock(return_value=_mock_response(
            ChallengeThesisResponse,
            conviction_score="0.65", counter_count=4, blind_spot_count=2,
        ))
        claims_input = ["AAPL will grow revenue 20% YoY"]
        resp = client.post("/agents/adversarial", json={
            "claims": claims_input,
        })
        assert resp.status_code == 200
        call_req = mock_svc.challenge_thesis.call_args[0][0]
        assert call_req.claims == claims_input
        assert resp.json()["counter_count"] == 4

    def test_challenge_thesis_wrong_type_claims_422(self, client):
        resp = client.post("/agents/adversarial", json={
            "claims": "not a list",
        })
        assert resp.status_code == 422


# --- Pipeline & Digest ---


class TestPipelineEndpoint:
    @patch("src.web_api.create_pipeline_service")
    def test_run_pipeline_forwards_ticker_and_date(self, mock_create, client):
        mock_svc = mock_create.return_value
        mock_svc.run_pipeline = AsyncMock(return_value=RunPipelineResponse(
            results=[{"task_id": "t1", "status": "success"}],
            total_duration_ms=150,
            successful=1,
            failed=0,
            memo=None,
        ))
        resp = client.post("/pipeline?ticker=AAPL&date=2025-01-15", json={
            "tasks": [
                {"agent_name": "macro_regime", "prompt": "classify", "task_id": "t1"},
            ],
        })
        assert resp.status_code == 200
        _, kwargs = mock_svc.run_pipeline.call_args
        assert kwargs["ticker"] == "AAPL"
        assert kwargs["date"] == "2025-01-15"
        data = resp.json()
        assert data["successful"] == 1
        assert data["total_duration_ms"] == 150

    @patch("src.web_api.create_pipeline_service")
    def test_run_pipeline_unknown_agent_rejects_before_service(
        self, mock_create, client,
    ):
        resp = client.post("/pipeline", json={
            "tasks": [
                {"agent_name": "nonexistent_agent", "prompt": "test"},
            ],
        })
        assert resp.status_code == 400
        mock_create.assert_not_called()

    def test_run_pipeline_empty_agent_name_422(self, client):
        resp = client.post("/pipeline", json={
            "tasks": [
                {"agent_name": "", "prompt": "test"},
            ],
        })
        assert resp.status_code == 422

    @patch("src.web_api.create_pipeline_service")
    def test_run_pipeline_empty_tasks_accepted(self, mock_create, client):
        mock_svc = mock_create.return_value
        mock_svc.run_pipeline = AsyncMock(return_value=RunPipelineResponse(
            results=[],
            total_duration_ms=0,
            successful=0,
            failed=0,
            memo=None,
        ))
        resp = client.post("/pipeline", json={"tasks": []})
        assert resp.status_code == 200
        data = resp.json()
        assert data["results"] == []
        assert data["successful"] == 0


class TestDigestEndpoint:
    @patch("src.web_api.DigestService")
    def test_run_digest_forwards_tickers(self, mock_cls, client):
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
            "lookback_days": 14,
        })
        assert resp.status_code == 200
        call_req = mock_svc.run_digest.call_args[0][0]
        assert call_req.tickers == ["AAPL", "MSFT"]
        assert call_req.lookback_days == 14
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

    def test_run_digest_missing_tickers_422(self, client):
        resp = client.post("/digest", json={})
        assert resp.status_code == 422


# --- Fresh Service Per Request ---


class TestServiceIsolation:
    @patch("src.web_api.AgentService")
    def test_each_request_creates_fresh_agent_service(self, mock_cls, client):
        mock_svc = mock_cls.return_value
        mock_svc.analyze_earnings = AsyncMock(return_value=_mock_response(
            AnalyzeEarningsResponse,
            tone="positive", net_sentiment=0.5, confidence="medium",
            guidance_direction="maintained", guidance_count=1, key_phrase_count=1,
        ))
        client.post("/agents/earnings_interpreter", json={
            "transcript": "first call",
        })
        client.post("/agents/earnings_interpreter", json={
            "transcript": "second call",
        })
        assert mock_cls.call_count == 2


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
        assert resp.json()["detail"] is not None

    def test_malformed_json_body_422(self, client):
        resp = client.post(
            "/agents/earnings_interpreter",
            content=b"not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 422


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


# --- Knowledge Graph Endpoints ---


class TestKGExtract:
    def test_extract_entities_from_text(self, client):
        resp = client.post("/kg/extract", json={
            "text": "Apple Inc. faces cybersecurity and regulatory risk.",
            "source_doc": "10-K-2024",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["entity_count"] >= 1
        assert len(data["entities"]) == data["entity_count"]

    def test_extract_with_ticker(self, client):
        resp = client.post("/kg/extract", json={
            "text": "Apple Inc. reported record revenue.",
            "ticker": "AAPL",
        })
        assert resp.status_code == 200
        data = resp.json()
        apple_entities = [e for e in data["entities"] if "Apple" in e["name"]]
        assert len(apple_entities) >= 1
        assert apple_entities[0]["ticker"] == "AAPL"

    def test_extract_empty_text_422(self, client):
        resp = client.post("/kg/extract", json={"text": ""})
        assert resp.status_code == 422

    def test_extract_missing_text_422(self, client):
        resp = client.post("/kg/extract", json={})
        assert resp.status_code == 422


class TestKGQueryRelated:
    def test_query_related_returns_response(self, client):
        # Seed the graph first
        client.post("/kg/extract", json={
            "text": "Intel Corp. supplies chips to Apple Inc. every year.",
        })
        resp = client.post("/kg/query/related", json={
            "entity_id": "name:intel corp",
            "max_depth": 1,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1
        assert len(data["related"]) == data["count"]

    def test_query_related_nonexistent_entity(self, client):
        resp = client.post("/kg/query/related", json={
            "entity_id": "ticker:NONEXISTENT",
        })
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_query_related_empty_id_422(self, client):
        resp = client.post("/kg/query/related", json={"entity_id": ""})
        assert resp.status_code == 422


class TestKGQuerySupplyChain:
    def test_supply_chain_returns_response(self, client):
        # Seed a supplier relationship
        client.post("/kg/extract", json={
            "text": "Intel Corp. supplies chips to Dell Inc.",
        })
        resp = client.post("/kg/query/supply-chain", json={
            "entity_id": "name:dell inc",
            "direction": "upstream",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["direction"] == "upstream"
        chain_names = [e["name"] for e in data["chain"]]
        assert any("intel" in n.lower() for n in chain_names)

    def test_supply_chain_invalid_direction_422(self, client):
        resp = client.post("/kg/query/supply-chain", json={
            "entity_id": "ticker:AAPL",
            "direction": "sideways",
        })
        assert resp.status_code == 422


class TestKGQuerySharedRisks:
    def test_shared_risks_returns_response(self, client):
        # Seed graph directly — extract doesn't create company→risk relationships
        from src.core.knowledge_graph import Entity, EntityType, Relationship, RelationshipType

        graph = _web_api_module._kg_graph
        graph.add_entity(Entity(name="Apple Inc", entity_type=EntityType.COMPANY, ticker="AAPL"))
        graph.add_entity(Entity(
            name="Microsoft Corp", entity_type=EntityType.COMPANY, ticker="MSFT",
        ))
        graph.add_entity(Entity(name="cybersecurity", entity_type=EntityType.RISK))
        graph.add_relationship(Relationship(
            source_id="ticker:AAPL", target_id="name:cybersecurity",
            rel_type=RelationshipType.PARTNER, evidence="AAPL faces cyber risk",
        ))
        graph.add_relationship(Relationship(
            source_id="ticker:MSFT", target_id="name:cybersecurity",
            rel_type=RelationshipType.PARTNER, evidence="MSFT faces cyber risk",
        ))
        resp = client.post("/kg/query/shared-risks", json={
            "entity_ids": ["ticker:AAPL", "ticker:MSFT"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1
        risk_names = [r["name"] for r in data["shared_risks"]]
        assert any("cyber" in n.lower() for n in risk_names)

    def test_shared_risks_fewer_than_two_422(self, client):
        resp = client.post("/kg/query/shared-risks", json={
            "entity_ids": ["ticker:AAPL"],
        })
        assert resp.status_code == 422


class TestKGStats:
    def test_stats_returns_counts(self, client):
        resp = client.get("/kg/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["entity_count"], int)
        assert isinstance(data["relationship_count"], int)
        assert isinstance(data["entities_by_type"], dict)
        assert isinstance(data["relationships_by_type"], dict)

    def test_stats_reflects_extraction(self, client):
        client.post("/kg/extract", json={
            "text": "Apple Inc. is facing cybersecurity concerns.",
        })
        resp = client.get("/kg/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["entity_count"] >= 1


# --- Watchlists ---


class TestWatchlistList:
    def test_list_returns_default(self, client):
        resp = client.get("/watchlists")
        assert resp.status_code == 200
        data = resp.json()
        assert data["active"] == "default"
        assert "default" in data["watchlists"]
        assert data["active_watchlist"]["tickers"] == []


class TestWatchlistCreate:
    def test_create_new(self, client):
        resp = client.post("/watchlists", json={
            "name": "tech", "tickers": ["NVDA", "AAPL"],
        })
        assert resp.status_code == 201
        assert resp.json()["tickers"] == ["AAPL", "NVDA"]

    def test_create_duplicate_400(self, client):
        client.post("/watchlists", json={"name": "tech"})
        resp = client.post("/watchlists", json={"name": "tech"})
        assert resp.status_code == 400

    def test_create_invalid_name_400(self, client):
        resp = client.post("/watchlists", json={"name": "Bad Name!"})
        assert resp.status_code == 400


class TestWatchlistGet:
    def test_get_existing(self, client):
        resp = client.get("/watchlists/default")
        assert resp.status_code == 200
        assert "tickers" in resp.json()

    def test_get_nonexistent_404(self, client):
        resp = client.get("/watchlists/nonexistent")
        assert resp.status_code == 404


class TestWatchlistUpdate:
    def test_update_tickers(self, client):
        resp = client.put("/watchlists/default", json={
            "tickers": ["MSFT", "GOOG"],
        })
        assert resp.status_code == 200
        assert resp.json()["tickers"] == ["GOOG", "MSFT"]
        resp2 = client.get("/watchlists/default")
        assert resp2.json()["tickers"] == ["GOOG", "MSFT"]

    def test_update_nonexistent_404(self, client):
        resp = client.put("/watchlists/nope", json={"tickers": []})
        assert resp.status_code == 404


class TestWatchlistDelete:
    def test_delete_non_active(self, client):
        client.post("/watchlists", json={"name": "temp"})
        resp = client.delete("/watchlists/temp")
        assert resp.status_code == 204
        resp2 = client.get("/watchlists/temp")
        assert resp2.status_code == 404

    def test_delete_active_400(self, client):
        resp = client.delete("/watchlists/default")
        assert resp.status_code == 400


class TestWatchlistActivate:
    def test_activate_switches(self, client):
        client.post("/watchlists", json={
            "name": "energy", "tickers": ["XOM"],
        })
        resp = client.put("/watchlists/energy/activate")
        assert resp.status_code == 200
        assert resp.json()["active"] == "energy"
        listing = client.get("/watchlists").json()
        assert listing["active"] == "energy"

    def test_activate_nonexistent_404(self, client):
        resp = client.put("/watchlists/nope/activate")
        assert resp.status_code == 404
