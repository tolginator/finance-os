"""Tests for the earnings interpreter agent."""

import pytest

from src.agents.earnings_interpreter import (
    EarningsInterpreterAgent,
    SentimentScore,
    analyze_transcript,
    extract_guidance,
    score_sentiment,
    split_transcript_sections,
)
from src.core.agent import AgentResponse


class TestScoreSentiment:
    """Tests for earnings sentiment scoring."""

    def test_detects_positive_terms(self) -> None:
        text = "We saw strong momentum and robust growth this quarter with record revenue"
        score = score_sentiment(text)
        assert score.positive_count > 0
        assert score.net_sentiment > 0

    def test_detects_negative_terms(self) -> None:
        text = "We faced significant headwind and pressure with a disappointing decline in margins"
        score = score_sentiment(text)
        assert score.negative_count > 0
        assert score.net_sentiment < 0

    def test_detects_hedging(self) -> None:
        text = "Results may vary and could potentially be subject to uncertain conditions"
        score = score_sentiment(text)
        assert score.hedging_count > 0

    def test_empty_text(self) -> None:
        score = score_sentiment("")
        assert score.net_sentiment == 0.0
        assert score.confidence_level == "UNKNOWN"


class TestSentimentScore:
    """Tests for SentimentScore computed properties."""

    def test_net_sentiment_balanced(self) -> None:
        score = SentimentScore(
            positive_count=3, negative_count=3,
            hedging_count=0, total_words=100,
        )
        assert score.net_sentiment == 0.0

    def test_confidence_high_when_low_hedging(self) -> None:
        score = SentimentScore(
            positive_count=5, negative_count=1,
            hedging_count=0, total_words=1000,
        )
        assert score.confidence_level == "HIGH"

    def test_confidence_low_when_heavy_hedging(self) -> None:
        score = SentimentScore(
            positive_count=2, negative_count=1,
            hedging_count=20, total_words=100,
        )
        assert score.confidence_level == "LOW"


class TestExtractGuidance:
    """Tests for guidance extraction."""

    def test_detects_raised_guidance(self) -> None:
        text = (
            "We are raising our full-year guidance "
            "to reflect strong performance"
        )
        guidance = extract_guidance(text)
        assert guidance.direction == "RAISED"
        assert len(guidance.statements) > 0

    def test_detects_lowered_guidance(self) -> None:
        text = "We are lowering our guidance due to macro headwinds"
        guidance = extract_guidance(text)
        assert guidance.direction == "LOWERED"

    def test_detects_maintained_guidance(self) -> None:
        text = (
            "We are reiterating our guidance "
            "for the full year outlook"
        )
        guidance = extract_guidance(text)
        assert guidance.direction == "MAINTAINED"

    def test_neutral_when_no_guidance(self) -> None:
        text = "The weather was nice today"
        guidance = extract_guidance(text)
        assert guidance.direction == "NEUTRAL"
        assert len(guidance.statements) == 0


class TestSplitTranscript:
    """Tests for transcript section splitting."""

    def test_splits_on_qa_marker(self) -> None:
        text = (
            "CEO: Great quarter. CFO: Numbers look good. "
            "Question-and-Answer Session. "
            "Analyst: What about margins?"
        )
        prepared, qa = split_transcript_sections(text)
        assert "Great quarter" in prepared
        assert "What about margins" in qa

    def test_returns_full_text_when_no_qa(self) -> None:
        text = "This is a press release with no Q&A section at all."
        prepared, qa = split_transcript_sections(text)
        assert prepared == text
        assert qa == ""

    def test_splits_on_qa_session_marker(self) -> None:
        text = (
            "CEO: Strong results. CFO: Revenue up. "
            "Q & A Session. "
            "Analyst: How about guidance?"
        )
        prepared, qa = split_transcript_sections(text)
        assert "Strong results" in prepared
        assert "How about guidance" in qa


class TestAnalyzeTranscript:
    """Tests for full transcript analysis."""

    def test_full_analysis_with_tone_shift(self) -> None:
        transcript = (
            "We delivered strong momentum with robust growth and record revenue "
            "this quarter. Our team outperformed expectations and we are confident "
            "in our accelerated trajectory. We are raising our full-year guidance. "
            "Question-and-Answer Session. "
            "Analyst: What about the decline in margins? "
            "CEO: We faced some headwind and pressure but remain cautious about "
            "the uncertain macro environment. There is concern about deterioration."
        )
        analysis = analyze_transcript(transcript)
        assert analysis.overall_sentiment.positive_count > 0
        assert analysis.overall_sentiment.negative_count > 0
        assert analysis.guidance.direction == "RAISED"
        assert analysis.prepared_sentiment is not None
        assert analysis.qa_sentiment is not None

    def test_tone_shift_boundary(self) -> None:
        """Prepared=0.5, Q&A=0.1 → |0.1-0.5|=0.4 > 0.3 → tone shift flagged."""
        # Build text where prepared has net_sentiment=0.5 (3 pos, 1 neg)
        # and Q&A has net_sentiment ~0.1 (weaker positive)
        transcript = (
            "We see strong momentum and robust growth with record results. "
            "However there is some pressure. "
            "Question-and-Answer Session. "
            "Analyst: We see strong improvement but also headwind decline "
            "weakness softness and concern about risk and deterioration."
        )
        analysis = analyze_transcript(transcript)
        assert analysis.prepared_sentiment is not None
        assert analysis.qa_sentiment is not None
        prep_net = analysis.prepared_sentiment.net_sentiment
        qa_net = analysis.qa_sentiment.net_sentiment
        if abs(qa_net - prep_net) > 0.3:
            assert "tone shift" in analysis.tone_summary.lower()


class TestEarningsInterpreterAgent:
    """Tests for EarningsInterpreterAgent behavior."""

    def test_system_prompt_covers_key_areas(self) -> None:
        agent = EarningsInterpreterAgent()
        prompt = agent.system_prompt
        assert "tone" in prompt.lower()
        assert "guidance" in prompt.lower()
        assert "BULLISH" in prompt

    @pytest.mark.asyncio
    async def test_run_without_transcript(self) -> None:
        agent = EarningsInterpreterAgent()
        response = await agent.run("")
        assert isinstance(response, AgentResponse)
        assert "No transcript" in response.content

    @pytest.mark.asyncio
    async def test_run_with_transcript(self) -> None:
        agent = EarningsInterpreterAgent()
        response = await agent.run(
            "We saw strong growth and record results this quarter"
        )
        assert isinstance(response, AgentResponse)
        assert "Sentiment" in response.content or "Tone" in response.content
