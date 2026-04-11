"""Tests for finance-os agents."""

from src.core.agent import AgentMessage, AgentResponse, BaseAgent


class TestBaseAgent:
    """Tests for BaseAgent abstract class."""

    def test_cannot_instantiate_directly(self) -> None:
        try:
            BaseAgent("test", "test agent")  # type: ignore[abstract]
            assert False, "Should have raised TypeError"
        except TypeError:
            pass

    def test_history_management(self) -> None:
        class DummyAgent(BaseAgent):
            @property
            def system_prompt(self) -> str:
                return "You are a test agent."

            async def run(self, prompt: str, **kwargs: object) -> AgentResponse:
                return AgentResponse(content="ok")

        agent = DummyAgent("test", "test agent")
        assert agent.history == []

        msg = AgentMessage(role="user", content="hello")
        agent.add_to_history(msg)
        assert len(agent.history) == 1

        agent.clear_history()
        assert agent.history == []
