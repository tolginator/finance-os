"""Adversarial agent — systematic thesis challenger for investment reasoning.

Generates counter-arguments, identifies blind spots, and stress-tests
investment theses to surface risks and strengthen conviction.
"""


from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from src.core.agent import AgentResponse, BaseAgent

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class CounterArgument:
    """A structured counter-argument against a specific investment claim.

    Attributes:
        claim: The original claim being challenged.
        counter: The counter-argument text.
        evidence_type: Category of evidence — "historical", "structural",
            "cyclical", or "competitive".
        strength: How compelling the counter is — "STRONG", "MODERATE", or "WEAK".
    """

    claim: str
    counter: str
    evidence_type: str  # "historical", "structural", "cyclical", "competitive"
    strength: str  # "STRONG", "MODERATE", "WEAK"


@dataclass
class BlindSpot:
    """A risk category missing from the investment thesis.

    Attributes:
        category: The risk area — "macro", "competitive", "regulatory",
            "execution", or "valuation".
        description: Explanation of the blind spot.
        risk_level: Severity — "HIGH", "MEDIUM", or "LOW".
    """

    category: str  # "macro", "competitive", "regulatory", "execution", "valuation"
    description: str
    risk_level: str  # "HIGH", "MEDIUM", "LOW"


@dataclass
class ChallengeResult:
    """Outcome of challenging an investment thesis.

    Attributes:
        original_thesis: The thesis text that was challenged.
        counter_arguments: Generated counter-arguments.
        blind_spots: Detected blind spots in the thesis.
        conviction_score: 0–1 score of how well the thesis survives challenge.
        summary: Human-readable summary of the challenge.
    """

    original_thesis: str
    counter_arguments: list[CounterArgument] = field(default_factory=list)
    blind_spots: list[BlindSpot] = field(default_factory=list)
    conviction_score: Decimal = Decimal("1.0")
    summary: str = ""


# ---------------------------------------------------------------------------
# Claim type keywords
# ---------------------------------------------------------------------------

_CLAIM_KEYWORDS: dict[str, list[str]] = {
    "growth": [
        "growth", "growing", "revenue increase", "expan", "scaling",
        "accelerat", "top-line",
    ],
    "value": [
        "undervalued", "cheap", "discount", "low p/e", "below intrinsic",
        "margin of safety", "book value",
    ],
    "momentum": [
        "trend", "momentum", "breakout", "moving average", "relative strength",
        "outperform",
    ],
    "quality": [
        "strong balance sheet", "high roic", "moat", "competitive advantage",
        "quality", "durable", "cash flow generation",
    ],
    "macro": [
        "rates", "interest rate", "inflation", "gdp", "monetary policy",
        "fiscal", "cycle", "recession", "macro",
    ],
}

# ---------------------------------------------------------------------------
# Counter-argument templates by claim type
# ---------------------------------------------------------------------------

_COUNTER_TEMPLATES: dict[str, dict[str, str]] = {
    "growth": {
        "counter": (
            "Historical growth rarely sustains at above-market rates for "
            "extended periods. Mean reversion is the norm, not the exception."
        ),
        "evidence_type": "historical",
        "strength": "MODERATE",
    },
    "value": {
        "counter": (
            "Value traps often appear cheap on traditional metrics while "
            "fundamentals continue to deteriorate beneath the surface."
        ),
        "evidence_type": "structural",
        "strength": "MODERATE",
    },
    "momentum": {
        "counter": (
            "Momentum reversals are common and can be sudden. Strategies "
            "relying on continuation face significant drawdown risk."
        ),
        "evidence_type": "cyclical",
        "strength": "WEAK",
    },
    "quality": {
        "counter": (
            "Quality metrics can deteriorate rapidly due to competitive "
            "disruption, management turnover, or capital misallocation."
        ),
        "evidence_type": "competitive",
        "strength": "MODERATE",
    },
    "macro": {
        "counter": (
            "Macro predictions have poor track records even among "
            "professional forecasters. Basing a thesis on macro "
            "calls introduces significant model risk."
        ),
        "evidence_type": "historical",
        "strength": "STRONG",
    },
    "other": {
        "counter": (
            "This claim lacks specificity, making it difficult to "
            "evaluate and easy to confirm with selective evidence."
        ),
        "evidence_type": "structural",
        "strength": "WEAK",
    },
}

# ---------------------------------------------------------------------------
# Blind-spot detection patterns
# ---------------------------------------------------------------------------

_BLIND_SPOT_CHECKS: list[dict[str, str]] = [
    {
        "keywords": "regulat",
        "category": "regulatory",
        "description": (
            "Thesis does not address regulatory risk — potential policy changes, "
            "compliance costs, or licensing threats."
        ),
        "risk_level": "HIGH",
    },
    {
        "keywords": "compet",
        "category": "competitive",
        "description": (
            "Thesis does not discuss competitive dynamics — new entrants, "
            "pricing pressure, or market share shifts."
        ),
        "risk_level": "MEDIUM",
    },
    {
        "keywords": "valuat",
        "category": "valuation",
        "description": (
            "Thesis lacks valuation analysis — no mention of multiples, "
            "DCF, or relative value assessment."
        ),
        "risk_level": "MEDIUM",
    },
    {
        "keywords": "execution|management",
        "category": "execution",
        "description": (
            "Thesis ignores execution risk — management capability, "
            "operational complexity, or integration challenges."
        ),
        "risk_level": "MEDIUM",
    },
    {
        "keywords": "macro|economy|interest rate",
        "category": "macro",
        "description": (
            "Thesis does not consider macroeconomic backdrop — interest "
            "rates, inflation, or economic cycle positioning."
        ),
        "risk_level": "LOW",
    },
]

# ---------------------------------------------------------------------------
# Strength penalties for conviction scoring
# ---------------------------------------------------------------------------

_COUNTER_PENALTY: dict[str, str] = {
    "STRONG": "0.15",
    "MODERATE": "0.10",
    "WEAK": "0.05",
}

_BLIND_SPOT_PENALTY: dict[str, str] = {
    "HIGH": "0.10",
    "MEDIUM": "0.05",
    "LOW": "0.02",
}


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def identify_claim_type(claim: str) -> str:
    """Classify an investment claim into a category based on keywords.

    Args:
        claim: Free-text investment claim to classify.

    Returns:
        One of "growth", "value", "momentum", "quality", "macro", or "other".
    """
    lower = claim.lower()
    for claim_type, keywords in _CLAIM_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                return claim_type
    return "other"


def generate_counter_for_type(claim: str, claim_type: str) -> CounterArgument:
    """Generate a structured counter-argument for a given claim type.

    Args:
        claim: The original investment claim.
        claim_type: The classified type (from ``identify_claim_type``).

    Returns:
        A ``CounterArgument`` with templated counter text.
    """
    template = _COUNTER_TEMPLATES.get(claim_type, _COUNTER_TEMPLATES["other"])
    return CounterArgument(
        claim=claim,
        counter=template["counter"],
        evidence_type=template["evidence_type"],
        strength=template["strength"],
    )


def detect_blind_spots(thesis: str) -> list[BlindSpot]:
    """Scan a thesis for missing risk categories.

    Args:
        thesis: The full investment thesis text.

    Returns:
        List of ``BlindSpot`` objects for each unaddressed risk area.
    """
    lower = thesis.lower()
    spots: list[BlindSpot] = []
    for check in _BLIND_SPOT_CHECKS:
        keywords = check["keywords"].split("|")
        if not any(kw in lower for kw in keywords):
            spots.append(BlindSpot(
                category=check["category"],
                description=check["description"],
                risk_level=check["risk_level"],
            ))
    return spots


def compute_conviction(
    counter_arguments: list[CounterArgument],
    blind_spots: list[BlindSpot],
) -> Decimal:
    """Compute a conviction score after applying counter-arguments and blind spots.

    Starts at 1.0 and subtracts penalties for each counter-argument and blind
    spot based on their severity. The result is clamped to [0, 1].

    Args:
        counter_arguments: Counter-arguments generated against claims.
        blind_spots: Detected blind spots in the thesis.

    Returns:
        A ``Decimal`` conviction score between 0 and 1.
    """
    score = Decimal("1.0")
    for ca in counter_arguments:
        penalty = Decimal(_COUNTER_PENALTY.get(ca.strength, "0.05"))
        score -= penalty
    for bs in blind_spots:
        penalty = Decimal(_BLIND_SPOT_PENALTY.get(bs.risk_level, "0.02"))
        score -= penalty
    return max(Decimal("0"), min(score, Decimal("1")))


def challenge_thesis(thesis: str, claims: list[str]) -> ChallengeResult:
    """Run the full adversarial challenge pipeline on an investment thesis.

    Classifies each claim, generates counter-arguments, detects blind spots,
    computes a conviction score, and produces a summary.

    Args:
        thesis: The full investment thesis text.
        claims: Individual claims extracted from the thesis.

    Returns:
        A ``ChallengeResult`` with all challenge outputs.
    """
    counters: list[CounterArgument] = []
    for claim in claims:
        claim_type = identify_claim_type(claim)
        counters.append(generate_counter_for_type(claim, claim_type))

    blind_spots = detect_blind_spots(thesis)
    conviction = compute_conviction(counters, blind_spots)

    n_strong = sum(1 for c in counters if c.strength == "STRONG")
    n_mod = sum(1 for c in counters if c.strength == "MODERATE")
    summary = (
        f"Challenged {len(claims)} claim(s) and found {len(blind_spots)} blind spot(s). "
        f"{n_strong} strong and {n_mod} moderate counter-arguments identified. "
        f"Post-challenge conviction: {conviction}."
    )

    return ChallengeResult(
        original_thesis=thesis,
        counter_arguments=counters,
        blind_spots=blind_spots,
        conviction_score=conviction,
        summary=summary,
    )


# ---------------------------------------------------------------------------
# Agent class
# ---------------------------------------------------------------------------


class AdversarialAgent(BaseAgent):
    """Agent that systematically challenges investment theses.

    Acts as a devil's advocate to surface risks, counter-arguments, and
    blind spots that may undermine an investment thesis.
    """

    def __init__(self) -> None:
        super().__init__(
            name="adversarial",
            description=(
                "Challenges investment theses by generating counter-arguments, "
                "identifying blind spots, and stress-testing reasoning"
            ),
        )

    @property
    def system_prompt(self) -> str:
        """System prompt defining the adversarial challenger persona."""
        return (
            "You are a rigorous adversarial analyst whose sole purpose is "
            "to challenge investment theses and stress-test reasoning. "
            "Your role is to:\n\n"
            "1. **Generate Counter-Arguments**: For every bullish claim, "
            "produce a credible bear case grounded in historical precedent, "
            "structural analysis, or competitive dynamics.\n\n"
            "2. **Identify Blind Spots**: Surface risk categories the thesis "
            "fails to address — regulatory, competitive, execution, "
            "valuation, and macro.\n\n"
            "3. **Stress-Test Assumptions**: Challenge growth rates, margin "
            "assumptions, and TAM estimates with base-rate data.\n\n"
            "4. **Score Conviction**: Provide a quantitative conviction score "
            "reflecting how well the thesis survives scrutiny.\n\n"
            "Be intellectually honest. Strong theses should survive your "
            "challenge with high conviction. Weak theses should be exposed. "
            "Never fabricate evidence — only use logical reasoning and "
            "known historical patterns."
        )

    async def run(self, prompt: str, **kwargs: Any) -> AgentResponse:
        """Execute the adversarial challenge pipeline.

        Args:
            prompt: The investment thesis to challenge.
            **kwargs: May include ``claims`` (list[str]) with explicit claims.

        Returns:
            AgentResponse with the challenge result.
        """
        claims: list[str] = kwargs.get("claims", [])
        if not claims:
            # Fall back to treating each sentence as a claim
            claims = [s.strip() for s in prompt.split(".") if s.strip()]

        result = challenge_thesis(prompt, claims)

        lines = ["## Adversarial Challenge\n", result.summary, ""]
        if result.counter_arguments:
            lines.append("### Counter-Arguments")
            for ca in result.counter_arguments:
                lines.append(
                    f"- [{ca.strength}] **{ca.claim}**: {ca.counter} "
                    f"(evidence: {ca.evidence_type})"
                )
            lines.append("")

        if result.blind_spots:
            lines.append("### Blind Spots")
            for bs in result.blind_spots:
                lines.append(f"- [{bs.risk_level}] **{bs.category}**: {bs.description}")
            lines.append("")

        lines.append(f"**Conviction Score**: {result.conviction_score}")

        return AgentResponse(
            content="\n".join(lines),
            metadata={
                "conviction_score": str(result.conviction_score),
                "counter_count": len(result.counter_arguments),
                "blind_spot_count": len(result.blind_spots),
            },
        )
