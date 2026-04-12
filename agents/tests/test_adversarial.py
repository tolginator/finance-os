"""Tests for the adversarial agent."""

from decimal import Decimal

import pytest

from src.agents.adversarial import (
    AdversarialAgent,
    BlindSpot,
    CounterArgument,
    challenge_thesis,
    compute_conviction,
    detect_blind_spots,
    generate_counter_for_type,
    identify_claim_type,
)
from src.core.agent import AgentResponse, BaseAgent

# ---------------------------------------------------------------------------
# identify_claim_type
# ---------------------------------------------------------------------------


class TestIdentifyClaimType:
    """Tests for claim type classification."""

    @pytest.mark.parametrize(
        ("claim", "expected"),
        [
            ("Revenue is growing 30% year-over-year", "growth"),
            ("We expect rapid expansion in new markets", "growth"),
            ("The stock is undervalued relative to peers", "value"),
            ("Trading at a discount to book value", "value"),
            ("Strong upward trend in price", "momentum"),
            ("Relative strength is improving", "momentum"),
            ("Company has a strong balance sheet", "quality"),
            ("Wide moat protects margins", "quality"),
            ("Rising interest rates will help banks", "macro"),
            ("Inflation is expected to moderate", "macro"),
        ],
    )
    def test_known_types(self, claim: str, expected: str) -> None:
        assert identify_claim_type(claim) == expected

    def test_unknown_claim_returns_other(self) -> None:
        assert identify_claim_type("The sky is blue") == "other"
        assert identify_claim_type("") == "other"


# ---------------------------------------------------------------------------
# generate_counter_for_type
# ---------------------------------------------------------------------------


class TestGenerateCounterForType:
    """Tests for counter-argument generation."""

    @pytest.mark.parametrize(
        ("claim_type", "expected_evidence", "expected_strength"),
        [
            ("growth", "historical", "MODERATE"),
            ("value", "structural", "MODERATE"),
            ("momentum", "cyclical", "WEAK"),
            ("quality", "competitive", "MODERATE"),
            ("macro", "historical", "STRONG"),
            ("other", "structural", "WEAK"),
        ],
    )
    def test_counter_attributes(
        self,
        claim_type: str,
        expected_evidence: str,
        expected_strength: str,
    ) -> None:
        ca = generate_counter_for_type("test claim", claim_type)
        assert isinstance(ca, CounterArgument)
        assert ca.claim == "test claim"
        assert ca.evidence_type == expected_evidence
        assert ca.strength == expected_strength
        assert len(ca.counter) > 0

    def test_unknown_type_falls_back_to_other(self) -> None:
        ca = generate_counter_for_type("weird claim", "nonexistent")
        assert ca.strength == "WEAK"
        assert ca.evidence_type == "structural"


# ---------------------------------------------------------------------------
# detect_blind_spots
# ---------------------------------------------------------------------------


class TestDetectBlindSpots:
    """Tests for blind-spot detection."""

    def test_complete_thesis_no_blind_spots(self) -> None:
        thesis = (
            "The company faces regulatory headwinds but has strong competitive "
            "positioning. Valuation is attractive at 12x earnings. Management "
            "execution has been excellent. The macro environment with interest "
            "rates falling is supportive."
        )
        spots = detect_blind_spots(thesis)
        assert spots == []

    def test_empty_thesis_all_blind_spots(self) -> None:
        spots = detect_blind_spots("")
        categories = {s.category for s in spots}
        assert categories == {"regulatory", "competitive", "valuation", "execution", "macro"}

    def test_partial_coverage(self) -> None:
        thesis = "The competitive landscape is favorable and regulation is stable."
        spots = detect_blind_spots(thesis)
        categories = {s.category for s in spots}
        assert "regulatory" not in categories
        assert "competitive" not in categories
        assert "valuation" in categories
        assert "execution" in categories
        assert "macro" in categories

    def test_blind_spot_attributes(self) -> None:
        spots = detect_blind_spots("nothing relevant here")
        for spot in spots:
            assert isinstance(spot, BlindSpot)
            assert spot.risk_level in {"HIGH", "MEDIUM", "LOW"}
            assert len(spot.description) > 0


# ---------------------------------------------------------------------------
# compute_conviction
# ---------------------------------------------------------------------------


class TestComputeConviction:
    """Tests for conviction score computation."""

    def test_no_issues_full_conviction(self) -> None:
        assert compute_conviction([], []) == Decimal("1.0")

    def test_strong_counter_reduces_more_than_moderate(self) -> None:
        strong = compute_conviction(
            [CounterArgument("c", "x", "historical", "STRONG")], []
        )
        moderate = compute_conviction(
            [CounterArgument("c", "x", "historical", "MODERATE")], []
        )
        weak = compute_conviction(
            [CounterArgument("c", "x", "historical", "WEAK")], []
        )
        assert strong < moderate < weak < Decimal("1.0")

    def test_more_issues_lower_conviction(self) -> None:
        one = compute_conviction(
            [CounterArgument("c", "x", "historical", "STRONG")], []
        )
        two = compute_conviction(
            [CounterArgument("c", "x", "historical", "STRONG")] * 2, []
        )
        assert two < one

    def test_blind_spots_reduce_conviction(self) -> None:
        high = compute_conviction(
            [], [BlindSpot("regulatory", "desc", "HIGH")]
        )
        low = compute_conviction(
            [], [BlindSpot("macro", "desc", "LOW")]
        )
        assert high < low < Decimal("1.0")

    def test_combined_issues_reduce_more_than_either_alone(self) -> None:
        counters = [CounterArgument("c", "x", "historical", "STRONG")]
        spots = [BlindSpot("exec", "desc", "MEDIUM")]
        combined = compute_conviction(counters, spots)
        counters_only = compute_conviction(counters, [])
        spots_only = compute_conviction([], spots)
        assert combined < counters_only
        assert combined < spots_only

    def test_clamps_to_zero(self) -> None:
        counters = [
            CounterArgument("c", "x", "historical", "STRONG")
            for _ in range(10)
        ]
        score = compute_conviction(counters, [])
        assert score == Decimal("0")

    def test_never_exceeds_one(self) -> None:
        assert compute_conviction([], []) <= Decimal("1")


# ---------------------------------------------------------------------------
# challenge_thesis (integration)
# ---------------------------------------------------------------------------


class TestChallengeThesis:
    """Tests for the full challenge pipeline."""

    def test_produces_all_fields(self) -> None:
        result = challenge_thesis(
            "Revenue is growing fast.",
            ["Revenue is growing fast"],
        )
        assert result.original_thesis == "Revenue is growing fast."
        assert len(result.counter_arguments) == 1
        assert len(result.blind_spots) > 0
        assert Decimal("0") <= result.conviction_score <= Decimal("1")
        assert len(result.summary) > 0

    def test_more_claims_lower_conviction(self) -> None:
        few = challenge_thesis("test thesis", ["rates rising"])
        many = challenge_thesis(
            "test thesis",
            ["rates rising", "revenue growing", "undervalued", "strong balance sheet"],
        )
        assert many.conviction_score < few.conviction_score

    def test_empty_claims(self) -> None:
        result = challenge_thesis("some thesis", [])
        assert result.counter_arguments == []
        assert result.conviction_score <= Decimal("1")

    def test_comprehensive_thesis_higher_conviction(self) -> None:
        comprehensive = (
            "The company faces regulatory headwinds but has strong competitive "
            "positioning. Valuation is attractive. Management execution is "
            "excellent. The macro economy is supportive."
        )
        sparse = "The stock will go up."
        r1 = challenge_thesis(comprehensive, ["stock up"])
        r2 = challenge_thesis(sparse, ["stock up"])
        assert r1.conviction_score > r2.conviction_score


# ---------------------------------------------------------------------------
# AdversarialAgent
# ---------------------------------------------------------------------------


class TestAdversarialAgent:
    """Tests for the AdversarialAgent class."""

    def test_is_base_agent_subclass(self) -> None:
        agent = AdversarialAgent()
        assert isinstance(agent, BaseAgent)

    def test_agent_name_and_description(self) -> None:
        agent = AdversarialAgent()
        assert agent.name == "adversarial"
        assert len(agent.description) > 0

    def test_system_prompt_mentions_challenge_concepts(self) -> None:
        agent = AdversarialAgent()
        prompt = agent.system_prompt.lower()
        assert "adversarial" in prompt or "challenge" in prompt
        assert "counter" in prompt
        assert "blind spot" in prompt or "blind spots" in prompt

    @pytest.mark.asyncio
    async def test_run_returns_agent_response(self) -> None:
        agent = AdversarialAgent()
        response = await agent.run("Revenue is growing and the stock is undervalued.")
        assert isinstance(response, AgentResponse)
        assert len(response.content) > 0
        assert "conviction_score" in response.metadata

    @pytest.mark.asyncio
    async def test_run_with_explicit_claims(self) -> None:
        agent = AdversarialAgent()
        response = await agent.run(
            "Bull thesis on AAPL",
            claims=["Revenue growing 20%", "Strong balance sheet"],
        )
        assert isinstance(response, AgentResponse)
        assert int(response.metadata["counter_count"]) == 2
