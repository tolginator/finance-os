"""Tests for the Python MCP server."""

import json

import pytest

from src.mcp_server import VALID_AGENT_NAMES, mcp


class TestToolRegistration:
    """Verify tool discovery and schemas."""

    async def test_all_expected_tools_registered(self) -> None:
        tools = await mcp.list_tools()
        names = {t.name for t in tools}
        assert names == {"analyze_earnings", "classify_macro", "research_digest", "orchestrate"}

    async def test_analyze_earnings_schema(self) -> None:
        tools = await mcp.list_tools()
        tool = next(t for t in tools if t.name == "analyze_earnings")
        props = tool.inputSchema["properties"]
        assert "transcript" in props
        assert "ticker" in props
        assert "transcript" in tool.inputSchema.get("required", [])

    async def test_classify_macro_schema(self) -> None:
        tools = await mcp.list_tools()
        tool = next(t for t in tools if t.name == "classify_macro")
        props = tool.inputSchema["properties"]
        assert "indicators" in props
        # No required fields — all have defaults
        assert tool.inputSchema.get("required", []) == []

    async def test_research_digest_schema(self) -> None:
        tools = await mcp.list_tools()
        tool = next(t for t in tools if t.name == "research_digest")
        props = tool.inputSchema["properties"]
        assert "tickers" in props
        assert "lookback_days" in props
        assert "alert_threshold" in props
        assert "tickers" in tool.inputSchema.get("required", [])

    async def test_orchestrate_schema(self) -> None:
        tools = await mcp.list_tools()
        tool = next(t for t in tools if t.name == "orchestrate")
        props = tool.inputSchema["properties"]
        assert "tasks" in props
        assert "ticker" in props
        assert "date" in props
        assert "tasks" in tool.inputSchema.get("required", [])


class TestAnalyzeEarnings:
    """Test the analyze-earnings tool."""

    async def test_returns_structured_response(self) -> None:
        content_list, _ = await mcp.call_tool(
            "analyze_earnings",
            {"transcript": "Revenue increased 20% year over year to $10 billion."},
        )
        parsed = json.loads(content_list[0].text)
        assert "content" in parsed
        assert "tone" in parsed
        assert "net_sentiment" in parsed
        assert "confidence" in parsed
        assert "guidance_direction" in parsed
        assert isinstance(parsed["guidance_count"], int)
        assert isinstance(parsed["key_phrase_count"], int)

    async def test_with_ticker(self) -> None:
        content_list, _ = await mcp.call_tool(
            "analyze_earnings",
            {"transcript": "Strong quarter for cloud services.", "ticker": "MSFT"},
        )
        parsed = json.loads(content_list[0].text)
        assert "content" in parsed

    async def test_empty_transcript_rejected(self) -> None:
        with pytest.raises(Exception):
            await mcp.call_tool("analyze_earnings", {"transcript": ""})


class TestClassifyMacro:
    """Test the classify-macro tool."""

    async def test_returns_structured_response(self) -> None:
        content_list, _ = await mcp.call_tool("classify_macro", {})
        parsed = json.loads(content_list[0].text)
        assert "content" in parsed
        assert "regime" in parsed
        assert isinstance(parsed["indicators_fetched"], int)
        assert isinstance(parsed["indicators_with_data"], int)
        # Regime may be empty if no FRED API key is configured
        if parsed["regime"]:
            assert parsed["regime"].lower() in ("expansion", "contraction", "transition")

    async def test_custom_indicators(self) -> None:
        content_list, _ = await mcp.call_tool(
            "classify_macro", {"indicators": ["GDP", "UNRATE"]}
        )
        parsed = json.loads(content_list[0].text)
        # Without a FRED API key, indicators_fetched may be 0
        assert isinstance(parsed["indicators_fetched"], int)

    async def test_api_key_not_in_schema(self) -> None:
        """FRED API key should come from server config, not tool input."""
        tools = await mcp.list_tools()
        tool = next(t for t in tools if t.name == "classify_macro")
        props = tool.inputSchema["properties"]
        assert "api_key" not in props


class TestResearchDigest:
    """Test the research-digest tool."""

    async def test_returns_structured_response(self) -> None:
        content_list, _ = await mcp.call_tool(
            "research_digest", {"tickers": ["AAPL", "MSFT"]}
        )
        parsed = json.loads(content_list[0].text)
        assert parsed["ticker_count"] == 2
        assert isinstance(parsed["entry_count"], int)
        assert isinstance(parsed["alert_count"], int)
        assert isinstance(parsed["material_count"], int)
        assert "content" in parsed

    async def test_custom_lookback(self) -> None:
        content_list, _ = await mcp.call_tool(
            "research_digest", {"tickers": ["GOOGL"], "lookback_days": 30}
        )
        parsed = json.loads(content_list[0].text)
        assert parsed["ticker_count"] == 1


class TestOrchestrate:
    """Test the orchestrate tool."""

    async def test_single_task_pipeline(self) -> None:
        content_list, _ = await mcp.call_tool(
            "orchestrate",
            {
                "tasks": [
                    {
                        "agent_name": "macro_regime",
                        "prompt": "Classify regime",
                        "task_id": "macro-1",
                    }
                ],
                "ticker": "SPY",
            },
        )
        parsed = json.loads(content_list[0].text)
        assert parsed["successful"] >= 0
        assert isinstance(parsed["total_duration_ms"], int)
        assert isinstance(parsed["results"], list)

    async def test_multi_task_pipeline(self) -> None:
        content_list, _ = await mcp.call_tool(
            "orchestrate",
            {
                "tasks": [
                    {
                        "agent_name": "macro_regime",
                        "prompt": "Classify regime",
                        "task_id": "macro",
                    },
                    {
                        "agent_name": "adversarial",
                        "prompt": "Challenge the bullish thesis",
                        "task_id": "challenge",
                    },
                ],
            },
        )
        parsed = json.loads(content_list[0].text)
        assert len(parsed["results"]) == 2

    async def test_unknown_agent_raises(self) -> None:
        with pytest.raises(Exception, match="Unknown agent"):
            await mcp.call_tool(
                "orchestrate",
                {
                    "tasks": [
                        {"agent_name": "nonexistent_agent", "prompt": "Do something"}
                    ]
                },
            )

    async def test_empty_tasks(self) -> None:
        content_list, _ = await mcp.call_tool("orchestrate", {"tasks": []})
        parsed = json.loads(content_list[0].text)
        assert parsed["successful"] == 0
        assert parsed["results"] == []


class TestValidAgentNames:
    """Test the VALID_AGENT_NAMES constant."""

    def test_contains_all_catalog_agents(self) -> None:
        expected = {
            "macro_regime", "filing_analyst", "earnings_interpreter",
            "quant_signal", "thesis_guardian", "risk_analyst", "adversarial",
        }
        assert VALID_AGENT_NAMES == expected
