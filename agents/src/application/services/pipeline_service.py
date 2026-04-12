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
            agent = self._orchestrator.get_agent(task_def.agent_name)
            if agent is None:
                continue

            task = AgentTask(
                agent=agent,
                prompt=task_def.prompt,
                kwargs=task_def.kwargs,
                priority=task_def.priority,
                depends_on=task_def.depends_on,
                task_id=task_def.task_id or None,
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
            memo_sections: dict[str, str] = {}
            for r in pipeline_result.results:
                if not r.success:
                    continue
                section_key = r.task_id or r.agent_name
                if section_key in memo_sections:
                    section_key = f"{section_key} ({r.agent_name})"
                memo_sections[section_key] = r.response.content

            sources = [r.agent_name for r in pipeline_result.results if r.success]
            analyzed = ", ".join(sources) if sources else "none"
            memo = {
                "ticker": ticker,
                "date": date,
                "sections": memo_sections,
                "sources": sources,
                "summary": f"Research memo for {ticker} on {date}. Analyzed by: {analyzed}.",
            }

        return RunPipelineResponse(
            results=result_dicts,
            total_duration_ms=pipeline_result.total_duration_ms,
            successful=pipeline_result.successful,
            failed=pipeline_result.failed,
            memo=memo,
        )
