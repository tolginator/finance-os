"""Tests for pipeline context propagation."""


from src.application.pipeline_context import (
    CONTEXT_MAPPINGS,
    extract_context,
    is_soft_failure,
)
from src.core.agent import AgentResponse
from src.core.orchestrator import AgentResult


class TestIsSoftFailure:
    """Detect soft failures from metadata."""

    def test_success_with_error_metadata(self) -> None:
        result = AgentResult(
            agent_name="macro_regime",
            response=AgentResponse(
                content="API key required",
                metadata={"error": "missing_api_key"},
            ),
            duration_ms=0,
            success=True,
        )
        assert is_soft_failure(result)

    def test_success_without_error(self) -> None:
        result = AgentResult(
            agent_name="macro_regime",
            response=AgentResponse(
                content="EXPANSION",
                metadata={"regime": "EXPANSION"},
            ),
            duration_ms=100,
            success=True,
        )
        assert not is_soft_failure(result)

    def test_hard_failure(self) -> None:
        result = AgentResult(
            agent_name="macro_regime",
            response=AgentResponse(content=""),
            duration_ms=0,
            success=False,
            error="Connection timeout",
        )
        assert not is_soft_failure(result)


class TestExtractContext:
    """Extract upstream context from completed dependencies."""

    def test_extracts_regime_from_macro(self) -> None:
        completed = {
            "macro": AgentResult(
                agent_name="macro_regime",
                response=AgentResponse(
                    content="EXPANSION",
                    metadata={"regime": "EXPANSION", "indicators_fetched": 5},
                ),
                duration_ms=100,
                success=True,
            ),
        }
        context = extract_context(completed, ["macro"])
        assert context["regime"] == "EXPANSION"

    def test_extracts_sentiment_from_earnings(self) -> None:
        completed = {
            "earnings": AgentResult(
                agent_name="earnings_interpreter",
                response=AgentResponse(
                    content="Bullish tone",
                    metadata={
                        "net_sentiment": 0.75,
                        "guidance_direction": "raised",
                    },
                ),
                duration_ms=50,
                success=True,
            ),
        }
        context = extract_context(completed, ["earnings"])
        assert context["sentiment"] == 0.75
        assert context["direction"] == "raised"

    def test_combines_multiple_producers(self) -> None:
        completed = {
            "macro": AgentResult(
                agent_name="macro_regime",
                response=AgentResponse(
                    content="EXPANSION",
                    metadata={"regime": "EXPANSION"},
                ),
                duration_ms=100,
                success=True,
            ),
            "earnings": AgentResult(
                agent_name="earnings_interpreter",
                response=AgentResponse(
                    content="Bullish",
                    metadata={"net_sentiment": 0.5, "guidance_direction": "maintained"},
                ),
                duration_ms=50,
                success=True,
            ),
        }
        context = extract_context(completed, ["macro", "earnings"])
        assert context["regime"] == "EXPANSION"
        assert context["sentiment"] == 0.5
        assert context["direction"] == "maintained"

    def test_skips_soft_failures(self) -> None:
        completed = {
            "macro": AgentResult(
                agent_name="macro_regime",
                response=AgentResponse(
                    content="API key required",
                    metadata={"error": "missing_api_key"},
                ),
                duration_ms=0,
                success=True,
            ),
        }
        context = extract_context(completed, ["macro"])
        assert "regime" not in context

    def test_skips_hard_failures(self) -> None:
        completed = {
            "macro": AgentResult(
                agent_name="macro_regime",
                response=AgentResponse(content=""),
                duration_ms=0,
                success=False,
                error="timeout",
            ),
        }
        context = extract_context(completed, ["macro"])
        assert context == {}

    def test_skips_missing_dependencies(self) -> None:
        context = extract_context({}, ["macro", "earnings"])
        assert context == {}

    def test_only_extracts_from_listed_dependencies(self) -> None:
        completed = {
            "macro": AgentResult(
                agent_name="macro_regime",
                response=AgentResponse(
                    content="EXPANSION",
                    metadata={"regime": "EXPANSION"},
                ),
                duration_ms=100,
                success=True,
            ),
        }
        # Doesn't list "macro" as a dependency
        context = extract_context(completed, ["filings"])
        assert "regime" not in context


class TestContextMappings:
    """Verify mapping definitions are consistent."""

    def test_all_mappings_have_required_keys(self) -> None:
        for mapping in CONTEXT_MAPPINGS:
            assert "producer" in mapping
            assert "metadata_key" in mapping
            assert "consumer_kwarg" in mapping

    def test_no_duplicate_consumer_kwargs(self) -> None:
        kwargs = [m["consumer_kwarg"] for m in CONTEXT_MAPPINGS]
        assert len(kwargs) == len(set(kwargs))
