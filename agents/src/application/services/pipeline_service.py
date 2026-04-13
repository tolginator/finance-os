"""Pipeline service — wraps orchestrator for typed pipeline execution."""

from typing import Any

from src.application.contracts.agents import RunPipelineRequest, RunPipelineResponse
from src.application.pipeline_context import extract_context, is_soft_failure
from src.core.agent import AgentResponse, BaseAgent
from src.core.orchestrator import AgentResult, AgentTask, Orchestrator


class PipelineService:
    """Runs multi-agent pipelines via the orchestrator.

    Maps typed pipeline requests to AgentTask lists,
    executes via Orchestrator, and returns typed responses.
    Propagates context from completed tasks to dependent tasks.
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
        """Execute a multi-agent pipeline with context propagation.

        Tasks with dependencies receive extracted context from upstream
        agent results (e.g., macro regime feeds into quant signals).
        Soft failures (metadata contains 'error') are treated as failures
        for downstream dependency resolution.

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
                kwargs=dict(task_def.kwargs),
                priority=task_def.priority,
                depends_on=task_def.depends_on,
                task_id=task_def.task_id or None,
            )
            tasks.append(task)

        pipeline_result = await self._run_with_context(tasks)

        result_dicts: list[dict[str, Any]] = []
        for r in pipeline_result:
            result_dicts.append({
                "task_id": r.task_id or r.agent_name,
                "agent_name": r.agent_name,
                "success": r.success and not is_soft_failure(r),
                "duration_ms": r.duration_ms,
                "content": r.response.content,
                "metadata": r.response.metadata,
                "error": r.error,
            })

        total_ms = sum(r.duration_ms for r in pipeline_result)
        successful = sum(1 for d in result_dicts if d["success"])
        failed = len(result_dicts) - successful

        memo = None
        if ticker and date:
            memo_sections: dict[str, str] = {}
            for r in pipeline_result:
                if not r.success or is_soft_failure(r):
                    continue
                section_key = r.task_id or r.agent_name
                if section_key in memo_sections:
                    section_key = f"{section_key} ({r.agent_name})"
                memo_sections[section_key] = r.response.content

            sources = [
                r.agent_name for r in pipeline_result
                if r.success and not is_soft_failure(r)
            ]
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
            total_duration_ms=total_ms,
            successful=successful,
            failed=failed,
            memo=memo,
        )

    async def _run_with_context(
        self, tasks: list[AgentTask]
    ) -> list[AgentResult]:
        """Run pipeline tasks, injecting upstream context into dependent tasks.

        Uses the orchestrator for scheduling and dependency ordering, but
        intercepts between waves to propagate context from completed tasks.
        """
        import asyncio

        completed: dict[str, AgentResult] = {}
        remaining = list(tasks)
        all_results: list[AgentResult] = []

        while remaining:
            ready: list[AgentTask] = []
            blocked: list[AgentTask] = []

            for task in remaining:
                if not task.depends_on:
                    ready.append(task)
                elif all(dep in completed for dep in task.depends_on):
                    failed_deps = [
                        dep for dep in task.depends_on
                        if not completed[dep].success or is_soft_failure(completed[dep])
                    ]
                    if failed_deps:
                        result = AgentResult(
                            agent_name=task.agent.name,
                            response=AgentResponse(content=""),
                            duration_ms=0,
                            success=False,
                            error=f"Dependency failed: {', '.join(failed_deps)}",
                            task_id=task.id,
                        )
                        completed[task.id] = result
                        all_results.append(result)
                        continue

                    # Inject upstream context into task kwargs
                    upstream_context = extract_context(
                        completed, task.depends_on
                    )
                    task.kwargs.update(upstream_context)
                    ready.append(task)
                else:
                    blocked.append(task)

            if not ready:
                for task in blocked:
                    result = AgentResult(
                        agent_name=task.agent.name,
                        response=AgentResponse(content=""),
                        duration_ms=0,
                        success=False,
                        error="Unresolvable dependency",
                        task_id=task.id,
                    )
                    completed[task.id] = result
                    all_results.append(result)
                break

            ready.sort(key=lambda t: t.priority, reverse=True)

            batch_results = await asyncio.gather(
                *(self._orchestrator.run_task(t) for t in ready)
            )
            for idx, result in enumerate(batch_results):
                task_id = ready[idx].id
                completed[task_id] = result
                all_results.append(result)

            remaining = blocked

        return all_results
