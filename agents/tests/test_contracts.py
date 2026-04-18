"""Tests for application layer contracts."""

from decimal import Decimal

from src.application.contracts.agents import (
    AnalyzeEarningsRequest,
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
    def test_accepts_empty_transcript_with_ticker(self):
        req = AnalyzeEarningsRequest(transcript="", ticker="AAPL")
        assert req.ticker == "AAPL"
        assert req.transcript == ""

    def test_accepts_transcript_without_ticker(self):
        req = AnalyzeEarningsRequest(transcript="Some earnings text")
        assert req.transcript == "Some earnings text"


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
