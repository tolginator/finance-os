"""CLI argument parsing and dispatch."""

import argparse
import asyncio
import sys

from src.cli.commands import list_agents, run_agent, run_digest, run_pipeline, show_config


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="finance-os",
        description="Finance OS — personal investment intelligence CLI",
    )
    parser.add_argument(
        "--output",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- run <agent> ---
    run_parser = subparsers.add_parser("run", help="Run a single agent")
    run_parser.add_argument("agent", help="Agent name (e.g. macro-regime, filing-analyst)")
    run_parser.add_argument("--ticker", default="", help="Stock ticker symbol")
    run_parser.add_argument("--prompt", default="", help="Free-form prompt text")
    run_parser.add_argument("--api-key", default="", help="Override FRED API key")
    run_parser.add_argument("--model", default="", help="Override LLM model")
    run_parser.add_argument(
        "--synthesize",
        action="store_true",
        help="Synthesize agent output via LLM gateway",
    )

    # --- pipeline ---
    pipeline_parser = subparsers.add_parser(
        "pipeline", help="Run multi-agent research pipeline"
    )
    pipeline_parser.add_argument("--ticker", required=True, help="Stock ticker symbol")
    pipeline_parser.add_argument("--date", default="", help="Analysis date (YYYY-MM-DD)")
    pipeline_parser.add_argument(
        "--agents", default="", help="Comma-separated agent names (default: all)"
    )
    pipeline_parser.add_argument("--model", default="", help="Override LLM model")
    pipeline_parser.add_argument(
        "--synthesize",
        action="store_true",
        help="Synthesize memo via LLM gateway",
    )

    # --- digest ---
    digest_parser = subparsers.add_parser("digest", help="Run research digest")
    digest_parser.add_argument(
        "--tickers", required=True, help="Comma-separated ticker list"
    )
    digest_parser.add_argument(
        "--lookback-days", type=int, default=7, help="Lookback period in days"
    )
    digest_parser.add_argument(
        "--alert-threshold", type=float, default=0.5, help="Materiality threshold"
    )
    digest_parser.add_argument("--model", default="", help="Override LLM model")

    # --- list ---
    subparsers.add_parser("list", help="List available agents")

    # --- config ---
    subparsers.add_parser("config", help="Show current configuration")

    return parser


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        match args.command:
            case "run":
                asyncio.run(run_agent(args))
            case "pipeline":
                asyncio.run(run_pipeline(args))
            case "digest":
                asyncio.run(run_digest(args))
            case "list":
                list_agents(args)
            case "config":
                show_config(args)
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:  # noqa: BLE001
        if args.output == "json":
            import json
            print(json.dumps({"error": str(e)}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
