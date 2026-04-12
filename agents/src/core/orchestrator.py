"""Multi-agent orchestrator for coordinating finance-os domain agents."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from src.core.agent import AgentResponse, BaseAgent


@dataclass
class AgentTask:
    """A task to be executed by an agent in the pipeline."""

    agent: BaseAgent
    prompt: str
    kwargs: dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    depends_on: list[str] = field(default_factory=list)


@dataclass
class AgentResult:
    """Result of a single agent task execution."""

    agent_name: str
    response: AgentResponse
    duration_ms: int
    success: bool
    error: str | None = None


@dataclass
class PipelineResult:
    """Aggregated result of a full pipeline run."""

    results: list[AgentResult]
    total_duration_ms: int
    successful: int
    failed: int


@dataclass
class ResearchMemo:
    """Structured research memo assembled from agent outputs."""

    ticker: str
    date: str
    sections: dict[str, str]
    sources: list[str]
    summary: str


class Orchestrator:
    """Coordinates multiple agents to produce unified research output.

    Agents are registered by name and can be composed into pipelines
    with dependency ordering and priority scheduling.
    """

    def __init__(self) -> None:
        self._registry: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        """Register an agent by name.

        Args:
            agent: The agent instance to register.
        """
        self._registry[agent.name] = agent

    def get_agent(self, name: str) -> BaseAgent | None:
        """Get a registered agent by name.

        Args:
            name: The agent's registered name.

        Returns:
            The agent if found, otherwise None.
        """
        return self._registry.get(name)

    def list_agents(self) -> list[str]:
        """List registered agent names.

        Returns:
            Sorted list of agent names.
        """
        return sorted(self._registry.keys())

    async def run_task(self, task: AgentTask) -> AgentResult:
        """Run a single agent task, capturing timing and errors.

        Args:
            task: The agent task to execute.

        Returns:
            AgentResult with timing, success status, and any error info.
        """
        start = time.monotonic()
        try:
            response = await task.agent.run(task.prompt, **task.kwargs)
            elapsed = int((time.monotonic() - start) * 1000)
            return AgentResult(
                agent_name=task.agent.name,
                response=response,
                duration_ms=elapsed,
                success=True,
            )
        except Exception as exc:  # noqa: BLE001
            elapsed = int((time.monotonic() - start) * 1000)
            return AgentResult(
                agent_name=task.agent.name,
                response=AgentResponse(content=""),
                duration_ms=elapsed,
                success=False,
                error=str(exc),
            )

    async def run_pipeline(self, tasks: list[AgentTask]) -> PipelineResult:
        """Run tasks respecting dependencies and priority.

        Tasks with no dependencies run first (ordered by priority desc).
        Tasks with dependencies wait for their dependencies to complete.
        Failed dependencies cause dependent tasks to fail with an error message.

        Args:
            tasks: List of agent tasks to execute.

        Returns:
            PipelineResult with all results and summary statistics.
        """
        pipeline_start = time.monotonic()
        completed: dict[str, AgentResult] = {}
        remaining = list(tasks)
        all_results: list[AgentResult] = []

        while remaining:
            # Partition into ready and blocked tasks
            ready: list[AgentTask] = []
            blocked: list[AgentTask] = []
            for task in remaining:
                if not task.depends_on:
                    ready.append(task)
                elif all(dep in completed for dep in task.depends_on):
                    # Check if any dependency failed
                    failed_deps = [
                        dep for dep in task.depends_on if not completed[dep].success
                    ]
                    if failed_deps:
                        result = AgentResult(
                            agent_name=task.agent.name,
                            response=AgentResponse(content=""),
                            duration_ms=0,
                            success=False,
                            error=(
                                f"Dependency failed: {', '.join(failed_deps)}"
                            ),
                        )
                        completed[task.agent.name] = result
                        all_results.append(result)
                        continue
                    ready.append(task)
                else:
                    blocked.append(task)

            if not ready:
                # All remaining tasks are blocked with unresolvable deps
                for task in blocked:
                    result = AgentResult(
                        agent_name=task.agent.name,
                        response=AgentResponse(content=""),
                        duration_ms=0,
                        success=False,
                        error="Unresolvable dependency",
                    )
                    completed[task.agent.name] = result
                    all_results.append(result)
                break

            # Sort ready tasks by priority (descending)
            ready.sort(key=lambda t: t.priority, reverse=True)

            # Run ready tasks concurrently
            batch_results = await asyncio.gather(
                *(self.run_task(t) for t in ready)
            )
            for result in batch_results:
                completed[result.agent_name] = result
                all_results.append(result)

            remaining = blocked

        total_ms = int((time.monotonic() - pipeline_start) * 1000)
        successful = sum(1 for r in all_results if r.success)
        failed = len(all_results) - successful

        return PipelineResult(
            results=all_results,
            total_duration_ms=total_ms,
            successful=successful,
            failed=failed,
        )

    def aggregate_results(self, results: list[AgentResult]) -> dict[str, str]:
        """Merge successful agent outputs into a dict of agent_name to content.

        Args:
            results: List of agent results to aggregate.

        Returns:
            Mapping of agent name to response content for successful results.
        """
        return {
            r.agent_name: r.response.content
            for r in results
            if r.success
        }

    def generate_memo(
        self, ticker: str, date: str, results: list[AgentResult]
    ) -> ResearchMemo:
        """Generate a research memo from pipeline results.

        Args:
            ticker: The stock ticker symbol.
            date: The date of the research memo.
            results: Agent results to compile into the memo.

        Returns:
            A structured ResearchMemo with sections from each agent.
        """
        sections = self.aggregate_results(results)
        sources = [r.agent_name for r in results if r.success]
        analyzed = ", ".join(sources) if sources else "none"
        summary = f"Research memo for {ticker} on {date}. Analyzed by: {analyzed}."

        return ResearchMemo(
            ticker=ticker,
            date=date,
            sections=sections,
            sources=sources,
            summary=summary,
        )
