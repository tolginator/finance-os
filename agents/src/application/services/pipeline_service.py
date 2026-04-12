"""Pipeline service — wraps orchestrator for typed pipeline execution."""

from typing import Any

from src.application.contracts.agents import RunPipelineRequest, RunPipelineResponse
from src.core.agent import BaseAgent
from src.core.orchestrator import AgentTask, Orchestrator


class PipelineService:
    """Runs multi-agent pipelines via the orchestrator.

    Maps typed pipeline requests to AgentTask lists,
    executes via Orchestrator, and returns typed responses.
    """

    def __init__(self, orchestrator: Orchestrator | None = None) -> None:
        self._orchestrator = orchestrator or Orchestrator()

    @property
    def orchestrator(self) -> Orchestrator:
        """The underlying orchestrator."""
        return self._orchestrator

    def register_agent(self, agent: BaseAgent) -> None:
        """Register an agent with the orchestrator."""
        self._orchestrator.register(agent)

    async def run_pipeline(
        self,
        request: RunPipelineRequest,
        *,
        ticker: str = "",
        date: str = "",
    ) -> RunPipelineResponse:
        """Execute a multi-agent pipeline.

        Args:
            request: Pipeline request with task definitions.
            ticker: Optional ticker for memo generation.
            date: Optional date for memo generation.

        Returns:
            RunPipelineResponse with results and optional memo.
        """
        tasks: list[AgentTask] = []
        for task_def in request.tasks:
            agent_name = task_def.get("agent_name", "")
            agent = self._orchestrator.get_agent(agent_name)
            if agent is None:
                continue

            task = AgentTask(
                agent=agent,
                prompt=task_def.get("prompt", ""),
                kwargs=task_def.get("kwargs", {}),
                priority=task_def.get("priority", 0),
                depends_on=task_def.get("depends_on", []),
                task_id=task_def.get("task_id"),
            )
            tasks.append(task)

        pipeline_result = await self._orchestrator.run_pipeline(tasks)

        result_dicts: list[dict[str, Any]] = []
        for r in pipeline_result.results:
            result_dicts.append({
                "task_id": r.task_id or r.agent_name,
                "agent_name": r.agent_name,
                "success": r.success,
                "duration_ms": r.duration_ms,
                "content": r.response.content,
                "metadata": r.response.metadata,
                "error": r.error,
            })

        memo = None
        if ticker and date:
            research_memo = self._orchestrator.generate_memo(
                ticker, date, pipeline_result.results
            )
            memo = {
                "ticker": research_memo.ticker,
                "date": research_memo.date,
                "sections": research_memo.sections,
                "sources": research_memo.sources,
                "summary": research_memo.summary,
            }

        return RunPipelineResponse(
            results=result_dicts,
            total_duration_ms=pipeline_result.total_duration_ms,
            successful=pipeline_result.successful,
            failed=pipeline_result.failed,
            memo=memo,
        )
