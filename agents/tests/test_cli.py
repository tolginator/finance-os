"""Tests for CLI argument parsing and command dispatch."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from src.application.registry import AGENT_CATALOG as AGENT_INFO
from src.cli.commands import (
    _mask,
    _normalize_agent_name,
)
from src.cli.main import build_parser, main


class TestArgParsing:
    """Verify argument parsing for all subcommands."""

    def test_run_basic(self):
        parser = build_parser()
        args = parser.parse_args(["run", "macro-regime"])
        assert args.command == "run"
        assert args.agent == "macro-regime"
        assert args.ticker == ""
        assert args.synthesize is False

    def test_run_with_options(self):
        parser = build_parser()
        args = parser.parse_args([
            "run", "filing-analyst",
            "--ticker", "AAPL",
            "--model", "gpt-4o",
            "--synthesize",
        ])
        assert args.agent == "filing-analyst"
        assert args.ticker == "AAPL"
        assert args.model == "gpt-4o"
        assert args.synthesize is True

    def test_pipeline_requires_ticker(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["pipeline"])

    def test_pipeline_with_options(self):
        parser = build_parser()
        args = parser.parse_args([
            "pipeline", "--ticker", "MSFT",
            "--date", "2026-01-15",
            "--agents", "macro-regime,risk-analyst",
        ])
        assert args.ticker == "MSFT"
        assert args.date == "2026-01-15"
        assert args.agents == "macro-regime,risk-analyst"

    def test_digest_requires_tickers(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["digest"])

    def test_digest_with_options(self):
        parser = build_parser()
        args = parser.parse_args([
            "digest", "--tickers", "AAPL,GOOG",
            "--lookback-days", "14",
            "--alert-threshold", "0.7",
        ])
        assert args.tickers == "AAPL,GOOG"
        assert args.lookback_days == 14
        assert args.alert_threshold == 0.7

    def test_list_command(self):
        parser = build_parser()
        args = parser.parse_args(["list"])
        assert args.command == "list"

    def test_config_command(self):
        parser = build_parser()
        args = parser.parse_args(["config"])
        assert args.command == "config"

    def test_output_json(self):
        parser = build_parser()
        args = parser.parse_args(["--output", "json", "list"])
        assert args.output == "json"

    def test_no_command_fails(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])


class TestAgentNameNormalization:
    """Agent names accept hyphens or underscores."""

    def test_hyphen_to_underscore(self):
        assert _normalize_agent_name("macro-regime") == "macro_regime"
        assert _normalize_agent_name("filing-analyst") == "filing_analyst"

    def test_underscore_passthrough(self):
        assert _normalize_agent_name("macro_regime") == "macro_regime"
        assert _normalize_agent_name("adversarial") == "adversarial"

    def test_unknown_name_normalizes(self):
        assert _normalize_agent_name("custom-agent") == "custom_agent"


class TestMasking:
    """Sensitive values are masked in config output."""

    def test_masks_long_value(self):
        assert _mask("abcdefgh1234") == "****1234"

    def test_masks_short_value(self):
        assert _mask("ab") == "****"

    def test_empty_value(self):
        assert _mask("") == "(not set)"


class TestListCommand:
    """List command outputs agent info."""

    def test_list_text(self, capsys):
        parser = build_parser()
        args = parser.parse_args(["list"])
        from src.cli.commands import list_agents
        list_agents(args)
        captured = capsys.readouterr()
        for info in AGENT_INFO:
            assert info["name"] in captured.out

    def test_list_json(self, capsys):
        parser = build_parser()
        args = parser.parse_args(["--output", "json", "list"])
        from src.cli.commands import list_agents
        list_agents(args)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert len(data) == len(AGENT_INFO)
        assert all("name" in entry for entry in data)


class TestConfigCommand:
    """Config command outputs masked configuration."""

    def test_config_masks_api_key(self, capsys, monkeypatch):
        from pathlib import Path

        monkeypatch.setenv("FINANCE_OS_FRED_API_KEY", "supersecretkey123")
        monkeypatch.setenv("FINANCE_OS_BLS_API_KEY", "blssecretkey456")
        monkeypatch.setattr("src.application.config.CONFIG_FILE", Path("/nonexistent"))

        parser = build_parser()
        args = parser.parse_args(["config"])
        from src.cli.commands import show_config
        show_config(args)
        captured = capsys.readouterr()
        assert "supersecretkey123" not in captured.out
        assert "blssecretkey456" not in captured.out
        assert "****" in captured.out

    def test_config_json(self, capsys, monkeypatch):
        monkeypatch.setenv("FINANCE_OS_FRED_API_KEY", "mykey12345")
        monkeypatch.setenv("FINANCE_OS_BLS_API_KEY", "blskey67890")
        from pathlib import Path
        monkeypatch.setattr("src.application.config.CONFIG_FILE", Path("/nonexistent"))

        parser = build_parser()
        args = parser.parse_args(["--output", "json", "config"])
        from src.cli.commands import show_config
        show_config(args)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["fred_api_key"] == "****2345"
        assert data["bls_api_key"] == "****7890"
        assert "mykey12345" not in json.dumps(data)
        assert "blskey67890" not in json.dumps(data)


class TestRunAgent:
    """Run command dispatches to correct agent."""

    @pytest.mark.asyncio
    async def test_run_unknown_agent(self):
        parser = build_parser()
        args = parser.parse_args(["run", "nonexistent"])
        from src.cli.commands import run_agent
        with pytest.raises(ValueError, match="Unknown agent"):
            await run_agent(args)

    @pytest.mark.asyncio
    async def test_run_macro_regime(self, capsys, monkeypatch):
        from pathlib import Path
        from unittest.mock import MagicMock

        monkeypatch.setattr("src.application.config.CONFIG_FILE", Path("/nonexistent"))

        parser = build_parser()
        args = parser.parse_args(["--output", "json", "run", "macro-regime"])

        mock_result = MagicMock()
        mock_result.model_dump.return_value = {
            "content": "Macro regime: expansion",
            "regime": "expansion",
            "indicators_fetched": 3,
            "indicators_with_data": 3,
        }
        mock_method = AsyncMock(return_value=mock_result)
        with patch(
            "src.cli.commands.AgentService.classify_macro", mock_method
        ):
            from src.cli.commands import run_agent
            await run_agent(args)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["regime"] == "expansion"

    @pytest.mark.asyncio
    async def test_run_adversarial_with_prompt(self, capsys, monkeypatch):
        from pathlib import Path
        from unittest.mock import MagicMock

        monkeypatch.setattr("src.application.config.CONFIG_FILE", Path("/nonexistent"))

        parser = build_parser()
        args = parser.parse_args([
            "--output", "json",
            "run", "adversarial",
            "--prompt", "AAPL will beat earnings",
        ])

        mock_result = MagicMock()
        mock_result.model_dump.return_value = {
            "content": "Counter: supply chain risks",
            "conviction_score": "MODERATE",
            "counter_count": 2,
            "blind_spot_count": 1,
        }
        mock_method = AsyncMock(return_value=mock_result)
        with patch(
            "src.cli.commands.AgentService.challenge_thesis", mock_method
        ):
            from src.cli.commands import run_agent
            await run_agent(args)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["conviction_score"] == "MODERATE"


class TestPipeline:
    """Pipeline command runs multi-agent orchestration."""

    @pytest.mark.asyncio
    async def test_pipeline_dispatches(self, capsys, monkeypatch):
        from pathlib import Path
        from unittest.mock import MagicMock

        monkeypatch.setattr("src.application.config.CONFIG_FILE", Path("/nonexistent"))

        parser = build_parser()
        args = parser.parse_args([
            "--output", "json",
            "pipeline", "--ticker", "AAPL",
        ])

        mock_result = MagicMock()
        mock_result.model_dump.return_value = {
            "results": [],
            "total_duration_ms": 100,
            "successful": 0,
            "failed": 0,
            "memo": None,
        }
        mock_result.memo = None
        mock_method = AsyncMock(return_value=mock_result)
        with patch(
            "src.cli.commands.create_pipeline_service"
        ) as mock_factory:
            mock_service = MagicMock()
            mock_service.run_pipeline = mock_method
            mock_service.register_agent = MagicMock()
            mock_factory.return_value = mock_service
            from src.cli.commands import run_pipeline
            await run_pipeline(args)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "total_duration_ms" in data


class TestDigest:
    """Digest command runs research digest."""

    @pytest.mark.asyncio
    async def test_digest_dispatches(self, capsys, monkeypatch):
        from pathlib import Path
        from unittest.mock import MagicMock

        monkeypatch.setattr("src.application.config.CONFIG_FILE", Path("/nonexistent"))

        parser = build_parser()
        args = parser.parse_args([
            "--output", "json",
            "digest", "--tickers", "AAPL,GOOG",
        ])

        mock_result = MagicMock()
        mock_result.model_dump.return_value = {
            "ticker_count": 2,
            "entry_count": 0,
            "alert_count": 0,
            "material_count": 0,
            "content": "Digest for AAPL, GOOG",
        }
        mock_method = AsyncMock(return_value=mock_result)
        with patch(
            "src.cli.commands.DigestService.run_digest", mock_method
        ):
            from src.cli.commands import run_digest
            await run_digest(args)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["ticker_count"] == 2


class TestMainEntryPoint:
    """Main function dispatches correctly."""

    def test_main_list(self, capsys):
        main(["list"])
        captured = capsys.readouterr()
        assert "macro_regime" in captured.out

    def test_main_error_text(self, capsys):
        with pytest.raises(SystemExit):
            main(["run", "nonexistent-xyz"])

    def test_main_error_json(self, capsys):
        with pytest.raises(SystemExit):
            main(["--output", "json", "run", "nonexistent-xyz"])
