"""Earnings interpreter agent — analyzes earnings call transcripts.

Detects tone shifts, sentiment drift, management confidence,
guidance changes, and key language patterns in earnings calls.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from src.core.agent import AgentResponse, BaseAgent

# Sentiment lexicons tuned for earnings calls
POSITIVE_TERMS: frozenset[str] = frozenset({
    "strong", "exceeded", "outperformed", "accelerated", "momentum",
    "robust", "confident", "favorable", "growth", "record",
    "improvement", "upside", "optimistic", "tailwind", "resilient",
    "expanded", "strengthened", "opportunity", "ahead", "beat",
})

NEGATIVE_TERMS: frozenset[str] = frozenset({
    "headwind", "challenged", "decline", "weakness", "uncertain",
    "softness", "pressure", "deterioration", "cautious", "risk",
    "disappointing", "miss", "below", "contraction", "deceleration",
    "impairment", "restructuring", "downturn", "adverse", "concern",
})

HEDGING_TERMS: frozenset[str] = frozenset({
    "may", "might", "could", "possibly", "potentially",
    "uncertain", "depends", "subject to", "contingent", "if",
})

GUIDANCE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"(?:full[- ]year|fy|annual)\s+(?:guidance|outlook|forecast)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:raise|lower|maintain|reiterate|revise)\w*\s+"
        r"(?:our\s+)?(?:guidance|outlook)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:expect|anticipate|project)\w*\s+"
        r"(?:revenue|earnings|eps|ebitda)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:range|target)\s+of\s+\$[\d,.]+ to \$[\d,.]+",
        re.IGNORECASE,
    ),
]


@dataclass
class SentimentScore:
    """Sentiment analysis result for a text segment."""

    positive_count: int
    negative_count: int
    hedging_count: int
    total_words: int

    @property
    def net_sentiment(self) -> float:
        """Net sentiment as a normalized score [-1.0, 1.0]."""
        total_signals = self.positive_count + self.negative_count
        if total_signals == 0:
            return 0.0
        return (self.positive_count - self.negative_count) / total_signals

    @property
    def confidence_level(self) -> str:
        """Management confidence based on hedging ratio."""
        if self.total_words == 0:
            return "UNKNOWN"
        hedging_ratio = self.hedging_count / self.total_words
        if hedging_ratio < 0.005:
            return "HIGH"
        elif hedging_ratio < 0.015:
            return "MODERATE"
        else:
            return "LOW"


@dataclass
class GuidanceExtraction:
    """Extracted guidance statements from transcript."""

    statements: list[str] = field(default_factory=list)
    direction: str = "NEUTRAL"  # RAISED, LOWERED, MAINTAINED, NEUTRAL


@dataclass
class TranscriptAnalysis:
    """Complete analysis of an earnings transcript."""

    overall_sentiment: SentimentScore
    qa_sentiment: SentimentScore | None
    prepared_sentiment: SentimentScore | None
    guidance: GuidanceExtraction
    key_phrases: list[str]
    tone_summary: str


def score_sentiment(text: str) -> SentimentScore:
    """Score sentiment of a text using the earnings lexicon.

    Args:
        text: Text to analyze.

    Returns:
        SentimentScore with positive, negative, hedging counts.
    """
    words = text.lower().split()
    total = len(words)
    word_set = set(words)

    positive = len(word_set & POSITIVE_TERMS)
    negative = len(word_set & NEGATIVE_TERMS)

    # Count hedging with multi-word support
    hedging = 0
    lower_text = text.lower()
    for term in HEDGING_TERMS:
        if term in lower_text:
            hedging += lower_text.count(term)

    return SentimentScore(
        positive_count=positive,
        negative_count=negative,
        hedging_count=hedging,
        total_words=total,
    )


def extract_guidance(text: str) -> GuidanceExtraction:
    """Extract guidance statements from transcript text.

    Args:
        text: Earnings transcript text.

    Returns:
        GuidanceExtraction with matched statements and direction.
    """
    statements: list[str] = []
    for pattern in GUIDANCE_PATTERNS:
        for match in pattern.finditer(text):
            start = max(0, match.start() - 50)
            end = min(len(text), match.end() + 100)
            context = text[start:end].strip()
            context = re.sub(r"\s+", " ", context)
            statements.append(context)

    direction = "NEUTRAL"
    lower = text.lower()
    raised_pat = r"rais\w+\s+(?:our\s+)?(?:[\w-]+\s+)*(?:guidance|outlook)"
    lowered_pat = r"lower\w+\s+(?:our\s+)?(?:[\w-]+\s+)*(?:guidance|outlook)"
    maintained_pat = (
        r"(?:maintain|reiterat)\w+\s+"
        r"(?:our\s+)?(?:[\w-]+\s+)*(?:guidance|outlook)"
    )
    if re.search(raised_pat, lower):
        direction = "RAISED"
    elif re.search(lowered_pat, lower):
        direction = "LOWERED"
    elif re.search(maintained_pat, lower):
        direction = "MAINTAINED"

    return GuidanceExtraction(statements=statements, direction=direction)


def split_transcript_sections(text: str) -> tuple[str, str]:
    """Split transcript into prepared remarks and Q&A sections.

    Args:
        text: Full earnings call transcript.

    Returns:
        Tuple of (prepared_remarks, qa_section). Either may be empty.
    """
    qa_markers = [
        r"question[- ]?and[- ]?answer",
        r"q\s*&\s*a\s+session",
        r"operator[:\s]+.*(?:first|our first)\s+question",
    ]

    for marker in qa_markers:
        match = re.search(marker, text, re.IGNORECASE)
        if match:
            return text[:match.start()], text[match.start():]

    return text, ""


def analyze_transcript(text: str) -> TranscriptAnalysis:
    """Perform full analysis of an earnings transcript.

    Args:
        text: Complete earnings call transcript text.

    Returns:
        TranscriptAnalysis with sentiment, guidance, and key findings.
    """
    overall = score_sentiment(text)
    prepared_text, qa_text = split_transcript_sections(text)

    prepared = score_sentiment(prepared_text) if prepared_text else None
    qa = score_sentiment(qa_text) if qa_text else None

    guidance = extract_guidance(text)

    # Extract notable phrases (sentences with high signal terms)
    sentences = re.split(r"[.!?]+", text)
    key_phrases: list[str] = []
    signal_terms = POSITIVE_TERMS | NEGATIVE_TERMS
    for sentence in sentences:
        words = set(sentence.lower().split())
        matches = words & signal_terms
        if len(matches) >= 2:
            cleaned = re.sub(r"\s+", " ", sentence.strip())
            if 10 < len(cleaned) < 300:
                key_phrases.append(cleaned)
                if len(key_phrases) >= 10:
                    break

    # Determine tone summary
    net = overall.net_sentiment
    confidence = overall.confidence_level
    if net > 0.3:
        tone = f"BULLISH (confidence: {confidence})"
    elif net < -0.3:
        tone = f"BEARISH (confidence: {confidence})"
    else:
        tone = f"NEUTRAL (confidence: {confidence})"

    if qa and prepared:
        qa_net = qa.net_sentiment
        prep_net = prepared.net_sentiment
        if abs(qa_net - prep_net) > 0.3:
            tone += (
                f" — tone shift detected: prepared={prep_net:+.2f}, "
                f"Q&A={qa_net:+.2f}"
            )

    return TranscriptAnalysis(
        overall_sentiment=overall,
        qa_sentiment=qa,
        prepared_sentiment=prepared,
        guidance=guidance,
        key_phrases=key_phrases,
        tone_summary=tone,
    )


def format_analysis(analysis: TranscriptAnalysis) -> str:
    """Format a TranscriptAnalysis into readable output.

    Args:
        analysis: The completed transcript analysis.

    Returns:
        Formatted multi-line analysis string.
    """
    lines = [
        "## Earnings Call Analysis\n",
        f"### Tone: {analysis.tone_summary}\n",
        "### Overall Sentiment",
        f"- Net sentiment: {analysis.overall_sentiment.net_sentiment:+.2f}",
        f"- Positive signals: {analysis.overall_sentiment.positive_count}",
        f"- Negative signals: {analysis.overall_sentiment.negative_count}",
        f"- Hedging instances: {analysis.overall_sentiment.hedging_count}",
        f"- Confidence: {analysis.overall_sentiment.confidence_level}",
    ]

    if analysis.prepared_sentiment:
        lines.extend([
            "\n### Prepared Remarks",
            f"- Net sentiment: {analysis.prepared_sentiment.net_sentiment:+.2f}",
            f"- Confidence: {analysis.prepared_sentiment.confidence_level}",
        ])

    if analysis.qa_sentiment:
        lines.extend([
            "\n### Q&A Session",
            f"- Net sentiment: {analysis.qa_sentiment.net_sentiment:+.2f}",
            f"- Confidence: {analysis.qa_sentiment.confidence_level}",
        ])

    lines.extend([
        "\n### Guidance",
        f"- Direction: {analysis.guidance.direction}",
    ])
    if analysis.guidance.statements:
        lines.append("- Key statements:")
        for stmt in analysis.guidance.statements[:5]:
            lines.append(f"  - \"{stmt}\"")

    if analysis.key_phrases:
        lines.append("\n### Key Phrases")
        for phrase in analysis.key_phrases[:5]:
            lines.append(f"- \"{phrase}\"")

    return "\n".join(lines)


class EarningsInterpreterAgent(BaseAgent):
    """Agent that analyzes earnings call transcripts.

    Specializes in detecting tone shifts, sentiment drift,
    management confidence levels, and guidance changes
    in quarterly earnings calls.
    """

    def __init__(self) -> None:
        super().__init__(
            name="earnings_interpreter",
            description=(
                "Analyzes earnings call transcripts for tone, "
                "sentiment, and guidance changes"
            ),
        )

    @property
    def system_prompt(self) -> str:
        """System prompt for earnings interpretation."""
        return (
            "You are a senior equity analyst specializing in "
            "earnings call analysis with 15 years of experience "
            "across all sectors. Your role is to:\n\n"
            "1. **Tone Analysis**: Detect shifts in management "
            "tone between prepared remarks and Q&A — evasion, "
            "defensiveness, unusual optimism, or hedging.\n\n"
            "2. **Sentiment Scoring**: Quantify positive vs "
            "negative language using domain-specific lexicons "
            "calibrated for earnings calls.\n\n"
            "3. **Guidance Interpretation**: Extract forward-looking "
            "guidance, determine if raised/lowered/maintained, "
            "and assess achievability.\n\n"
            "4. **Management Confidence**: Measure hedging language "
            "frequency, response completeness, and willingness to "
            "provide specifics as confidence proxies.\n\n"
            "5. **Key Language Patterns**: Flag material keywords — "
            "restructuring, impairment, acceleration, pipeline, "
            "backlog, visibility.\n\n"
            "Output structured analysis with:\n"
            "- Overall tone rating (BULLISH/NEUTRAL/BEARISH)\n"
            "- Sentiment scores for prepared remarks vs Q&A\n"
            "- Guidance direction and key statements\n"
            "- Management confidence level (HIGH/MODERATE/LOW)\n"
            "- Notable language patterns and red flags"
        )

    async def run(self, prompt: str, **kwargs: Any) -> AgentResponse:
        """Analyze an earnings call transcript.

        Args:
            prompt: The transcript text or analysis request.
            **kwargs: May include 'transcript' for explicit text.

        Returns:
            AgentResponse with structured earnings analysis.
        """
        transcript = kwargs.get("transcript", prompt)

        if not transcript or not str(transcript).strip():
            return AgentResponse(
                content=(
                    "No transcript provided. Pass the earnings call "
                    "text as the prompt or via transcript= kwarg."
                ),
                metadata={"error": "missing_transcript"},
            )

        text = str(transcript)
        analysis = analyze_transcript(text)
        output = format_analysis(analysis)

        return AgentResponse(
            content=output,
            metadata={
                "tone": analysis.tone_summary,
                "net_sentiment": analysis.overall_sentiment.net_sentiment,
                "confidence": analysis.overall_sentiment.confidence_level,
                "guidance_direction": analysis.guidance.direction,
                "guidance_count": len(analysis.guidance.statements),
                "key_phrase_count": len(analysis.key_phrases),
            },
        )
