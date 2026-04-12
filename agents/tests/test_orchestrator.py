"""Tests for the multi-agent orchestrator."""

from __future__ import annotations

from typing import Any

import pytest

from src.core.agent import AgentResponse, BaseAgent
from src.core.orchestrator import AgentTask, Orchestrator

# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


class MockAgent(BaseAgent):
    """Agent that returns a fixed response."""

    def __init__(self, name: str, response_content: str = "mock output") -> None:
        super().__init__(name, f"Mock {name}")
        self._response = response_content

    async def run(self, prompt: str, **kwargs: Any) -> AgentResponse:
        return AgentResponse(content=self._response)

    @property
    def system_prompt(self) -> str:
        return "Mock agent"


class FailingAgent(BaseAgent):
    """Agent that always raises an exception."""

    def __init__(self, name: str) -> None:
        super().__init__(name, f"Failing {name}")

    async def run(self, prompt: str, **kwargs: Any) -> AgentResponse:
        raise RuntimeError("Agent failed")

    @property
    def system_prompt(self) -> str:
        return "Failing agent"


@pytest.fixture
def orchestrator() -> Orchestrator:
    return Orchestrator()


# ---------------------------------------------------------------------------
# Registration tests
# ---------------------------------------------------------------------------


def test_register_and_get_agent(orchestrator: Orchestrator) -> None:
    agent = MockAgent("analyst")
    orchestrator.register(agent)
    assert orchestrator.get_agent("analyst") is agent


def test_list_agents(orchestrator: Orchestrator) -> None:
    orchestrator.register(MockAgent("beta"))
    orchestrator.register(MockAgent("alpha"))
    assert orchestrator.list_agents() == ["alpha", "beta"]


def test_get_agent_unknown(orchestrator: Orchestrator) -> None:
    assert orchestrator.get_agent("nonexistent") is None


# ---------------------------------------------------------------------------
# run_task tests
# ---------------------------------------------------------------------------


async def test_run_task_success(orchestrator: Orchestrator) -> None:
    agent = MockAgent("analyst", "analysis done")
    task = AgentTask(agent=agent, prompt="analyze")
    result = await orchestrator.run_task(task)

    assert result.success is True
    assert result.agent_name == "analyst"
    assert result.response.content == "analysis done"
    assert result.duration_ms >= 0
    assert result.error is None


async def test_run_task_failure(orchestrator: Orchestrator) -> None:
    agent = FailingAgent("bad")
    task = AgentTask(agent=agent, prompt="fail")
    result = await orchestrator.run_task(task)

    assert result.success is False
    assert result.error == "Agent failed"
    assert result.duration_ms >= 0


# ---------------------------------------------------------------------------
# run_pipeline tests
# ---------------------------------------------------------------------------


async def test_pipeline_independent_tasks(orchestrator: Orchestrator) -> None:
    tasks = [
        AgentTask(agent=MockAgent("a", "out-a"), prompt="go"),
        AgentTask(agent=MockAgent("b", "out-b"), prompt="go"),
    ]
    result = await orchestrator.run_pipeline(tasks)

    assert result.successful == 2
    assert result.failed == 0
    assert len(result.results) == 2
    names = {r.agent_name for r in result.results}
    assert names == {"a", "b"}


async def test_pipeline_with_dependencies(orchestrator: Orchestrator) -> None:
    tasks = [
        AgentTask(agent=MockAgent("base", "base-out"), prompt="go"),
        AgentTask(
            agent=MockAgent("derived", "derived-out"),
            prompt="go",
            depends_on=["base"],
        ),
    ]
    result = await orchestrator.run_pipeline(tasks)

    assert result.successful == 2
    # The base task must appear before derived in results
    names = [r.agent_name for r in result.results]
    assert names.index("base") < names.index("derived")


async def test_pipeline_failed_dependency(orchestrator: Orchestrator) -> None:
    tasks = [
        AgentTask(agent=FailingAgent("base"), prompt="go"),
        AgentTask(
            agent=MockAgent("derived"),
            prompt="go",
            depends_on=["base"],
        ),
    ]
    result = await orchestrator.run_pipeline(tasks)

    assert result.failed == 2
    derived = next(r for r in result.results if r.agent_name == "derived")
    assert derived.success is False
    assert "Dependency failed" in (derived.error or "")


async def test_pipeline_priority_ordering(orchestrator: Orchestrator) -> None:
    tasks = [
        AgentTask(agent=MockAgent("low"), prompt="go", priority=1),
        AgentTask(agent=MockAgent("high"), prompt="go", priority=10),
    ]
    result = await orchestrator.run_pipeline(tasks)

    assert result.successful == 2
    # Higher priority task should appear first in results
    names = [r.agent_name for r in result.results]
    assert names.index("high") < names.index("low")


# ---------------------------------------------------------------------------
# aggregate_results tests
# ---------------------------------------------------------------------------


async def test_aggregate_results_filters_failures(orchestrator: Orchestrator) -> None:
    tasks = [
        AgentTask(agent=MockAgent("good", "content"), prompt="go"),
        AgentTask(agent=FailingAgent("bad"), prompt="go"),
    ]
    pipeline = await orchestrator.run_pipeline(tasks)
    aggregated = orchestrator.aggregate_results(pipeline.results)

    assert "good" in aggregated
    assert "bad" not in aggregated
    assert aggregated["good"] == "content"


# ---------------------------------------------------------------------------
# generate_memo tests
# ---------------------------------------------------------------------------


async def test_generate_memo(orchestrator: Orchestrator) -> None:
    tasks = [
        AgentTask(agent=MockAgent("filings", "10-K analysis"), prompt="go"),
        AgentTask(agent=MockAgent("earnings", "EPS beat"), prompt="go"),
    ]
    pipeline = await orchestrator.run_pipeline(tasks)
    memo = orchestrator.generate_memo("AAPL", "2025-01-15", pipeline.results)

    assert memo.ticker == "AAPL"
    assert memo.date == "2025-01-15"
    assert "filings" in memo.sections
    assert "earnings" in memo.sections
    assert memo.sections["filings"] == "10-K analysis"
    assert set(memo.sources) == {"filings", "earnings"}
    assert "AAPL" in memo.summary
    assert "2025-01-15" in memo.summary
