"""Pipeline context propagation — maps upstream agent outputs to downstream kwargs.

Keeps the orchestrator generic by handling agent-specific field extraction
in the application layer. Each mapping declares which metadata field from
a producer agent feeds which kwarg of a consumer agent.
"""

from typing import Any

from src.core.orchestrator import AgentResult

# Mapping: (producer_agent, metadata_key) → consumer_kwarg
# When building kwargs for a consumer task, we scan its completed dependencies
# and extract these fields from their metadata.
CONTEXT_MAPPINGS: list[dict[str, str]] = [
    {
        "producer": "macro_regime",
        "metadata_key": "regime",
        "consumer_kwarg": "regime",
    },
    {
        "producer": "earnings_interpreter",
        "metadata_key": "net_sentiment",
        "consumer_kwarg": "sentiment",
    },
    {
        "producer": "earnings_interpreter",
        "metadata_key": "guidance_direction",
        "consumer_kwarg": "direction",
    },
]


def is_soft_failure(result: AgentResult) -> bool:
    """Check if an agent result is a soft failure (success=True but metadata has error).

    Soft failures happen when an agent returns a helpful error message
    (e.g., "API key required") instead of raising an exception.
    """
    return result.success and "error" in result.response.metadata


def extract_context(
    completed: dict[str, AgentResult],
    depends_on: list[str],
) -> dict[str, Any]:
    """Extract propagated context from completed dependency results.

    Scans completed dependencies for metadata fields defined in
    CONTEXT_MAPPINGS and returns a dict of consumer kwargs.

    Args:
        completed: Map of task_id → AgentResult for completed tasks.
        depends_on: Task IDs this task depends on.

    Returns:
        Dict of kwargs to merge into the consumer task.
    """
    context: dict[str, Any] = {}

    # Build a lookup of agent_name → result for completed dependencies
    dep_results: dict[str, AgentResult] = {}
    for task_id in depends_on:
        result = completed.get(task_id)
        if result and result.success and not is_soft_failure(result):
            dep_results[result.agent_name] = result

    for mapping in CONTEXT_MAPPINGS:
        producer = mapping["producer"]
        metadata_key = mapping["metadata_key"]
        consumer_kwarg = mapping["consumer_kwarg"]

        result = dep_results.get(producer)
        if result and metadata_key in result.response.metadata:
            context[consumer_kwarg] = result.response.metadata[metadata_key]

    return context
