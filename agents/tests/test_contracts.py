"""Tests for application layer contracts."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.application.contracts.agents import (
    AnalyzeEarningsRequest,
    AnalyzeEarningsResponse,
    AssessRiskRequest,
    ChallengeThesisRequest,
    ClassifyMacroRequest,
    EvaluateThesisRequest,
    GenerateSignalsRequest,
    RunDigestRequest,
    RunPipelineRequest,
    SearchFilingsRequest,
)


class TestAnalyzeEarningsContract:
    def test_valid_request(self):
        req = AnalyzeEarningsRequest(transcript="Q3 earnings call transcript...")
        assert req.transcript == "Q3 earnings call transcript..."
        assert req.ticker == ""

    def test_empty_transcript_rejected(self):
        with pytest.raises(ValidationError):
            AnalyzeEarningsRequest(transcript="")

    def test_response_from_metadata(self):
        resp = AnalyzeEarningsResponse(
            content="Report",
            tone="bullish",
            net_sentiment=0.75,
            confidence="HIGH",
            guidance_direction="up",
            guidance_count=3,
            key_phrase_count=12,
        )
        assert resp.tone == "bullish"
        assert resp.net_sentiment == 0.75


class TestClassifyMacroContract:
    def test_defaults(self):
        req = ClassifyMacroRequest()
        assert req.api_key == ""
        assert req.indicators == []

    def test_with_indicators(self):
        req = ClassifyMacroRequest(api_key="test", indicators=["GDP", "UNRATE"])
        assert len(req.indicators) == 2


class TestSearchFilingsContract:
    def test_defaults(self):
        req = SearchFilingsRequest()
        assert req.form_type == "10-K"

    def test_with_ticker(self):
        req = SearchFilingsRequest(ticker="AAPL")
        assert req.ticker == "AAPL"


class TestGenerateSignalsContract:
    def test_with_decimal_sentiment(self):
        req = GenerateSignalsRequest(sentiment=Decimal("0.85"))
        assert req.sentiment == Decimal("0.85")

    def test_defaults(self):
        req = GenerateSignalsRequest()
        assert req.method == "equal_weight"
        assert req.signals == []


class TestEvaluateThesisContract:
    def test_with_data(self):
        thesis = {
            "ticker": "AAPL", "hypothesis": "Growth",
            "assumptions": [], "status": "active",
        }
        req = EvaluateThesisRequest(
            theses=[thesis],
            data={"revenue_growth": Decimal("0.15")},
        )
        assert len(req.theses) == 1
        assert req.data["revenue_growth"] == Decimal("0.15")


class TestAssessRiskContract:
    def test_defaults(self):
        req = AssessRiskRequest()
        assert req.positions == []
        assert req.scenarios == []
        assert req.returns == []


class TestChallengeThesisContract:
    def test_with_claims(self):
        req = ChallengeThesisRequest(claims=["Revenue will grow 20%"])
        assert len(req.claims) == 1

    def test_with_prompt_only(self):
        req = ChallengeThesisRequest(prompt="AAPL will outperform")
        assert req.claims == []


class TestRunPipelineContract:
    def test_valid_tasks(self):
        req = RunPipelineRequest(tasks=[
            {"agent_name": "macro-regime", "prompt": "Classify"},
            {"agent_name": "risk", "prompt": "Assess risk", "depends_on": ["macro-regime"]},
        ])
        assert len(req.tasks) == 2


class TestRunDigestContract:
    def test_defaults(self):
        req = RunDigestRequest(tickers=["AAPL", "MSFT"])
        assert req.lookback_days == 7
        assert req.alert_threshold == 0.5
        assert req.sources == []
