"""Base agent class for finance-os domain agents."""


import abc
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentMessage:
    """A message in an agent conversation."""

    role: str  # "user", "assistant", "system"
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResponse:
    """Response from an agent invocation."""

    content: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseAgent(abc.ABC):
    """Abstract base class for all finance-os agents.

    Each domain agent (filing analyst, earnings interpreter, etc.)
    extends this class with specialized system prompts, tool
    definitions, and reasoning strategies.
    """

    def __init__(self, name: str, description: str) -> None:
        self.name = name
        self.description = description
        self._history: list[AgentMessage] = []

    @abc.abstractmethod
    async def run(self, prompt: str, **kwargs: Any) -> AgentResponse:
        """Execute the agent with the given prompt.

        Args:
            prompt: The user's input prompt.
            **kwargs: Additional agent-specific parameters.

        Returns:
            AgentResponse with the agent's output.
        """
        ...

    @property
    @abc.abstractmethod
    def system_prompt(self) -> str:
        """The system prompt that defines this agent's persona and capabilities."""
        ...

    def add_to_history(self, message: AgentMessage) -> None:
        """Append a message to the conversation history."""
        self._history.append(message)

    def clear_history(self) -> None:
        """Reset the conversation history."""
        self._history = []

    @property
    def history(self) -> list[AgentMessage]:
        """The current conversation history."""
        return list(self._history)
