"""CLI command implementations."""

import argparse
import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from src.application.config import AppConfig
from src.application.contracts.agents import (
    AnalyzeEarningsRequest,
    AssessRiskRequest,
    ChallengeThesisRequest,
    ClassifyMacroRequest,
    EvaluateThesisRequest,
    GenerateSignalsRequest,
    RunDigestRequest,
    RunPipelineRequest,
    SearchFilingsRequest,
    TaskDefinition,
)
from src.application.llm.gateway import LLMGateway, create_gateway
from src.application.registry import AGENT_CATALOG, create_pipeline_service
from src.application.services.agent_service import AgentService
from src.application.services.digest_service import DigestService

# Agent name aliases: accept hyphens or underscores
AGENT_ALIASES: dict[str, str] = {
    "macro-regime": "macro_regime",
    "filing-analyst": "filing_analyst",
    "earnings-interpreter": "earnings_interpreter",
    "quant-signal": "quant_signal",
    "thesis-guardian": "thesis_guardian",
    "risk-analyst": "risk_analyst",
}


def _normalize_agent_name(name: str) -> str:
    """Normalize agent name: accept hyphens or underscores."""
    return AGENT_ALIASES.get(name, name.replace("-", "_"))


def _load_config() -> AppConfig:
    """Load application config."""
    return AppConfig()


def _create_gateway(config: AppConfig, model_override: str = "") -> LLMGateway:
    """Create LLM gateway from config with optional model override."""
    if config.llm_provider == "azure_openai":
        deployment = model_override or config.azure.deployment
        return create_gateway(
            provider_type="azure_openai",
            endpoint=config.azure.endpoint,
            deployment=deployment,
            api_version=config.azure.api_version,
        )
    model = model_override or config.llm_default_model
    return create_gateway(
        provider_type=config.llm_provider,
        default_model=model,
    )


def _json_serial(obj: object) -> Any:
    """JSON serializer for objects not serializable by default."""
    if isinstance(obj, Decimal):
        return str(obj)
    msg = f"Type {type(obj)} not serializable"
    raise TypeError(msg)


def _output(data: dict[str, Any], args: argparse.Namespace) -> None:
    """Print output in the requested format."""
    if args.output == "json":
        print(json.dumps(data, default=_json_serial, indent=2))
    else:
        content = data.get("content", "")
        if content:
            print(content)
        # Print key metadata fields
        for key, value in data.items():
            if key == "content":
                continue
            if value and value != 0:
                print(f"  {key}: {value}")


async def run_agent(args: argparse.Namespace) -> None:
    """Run a single agent."""
    agent_name = _normalize_agent_name(args.agent)
    config = _load_config()
    service = AgentService()

    result: dict[str, Any]
    match agent_name:
        case "macro_regime":
            api_key = args.api_key or config.fred_api_key
            request = ClassifyMacroRequest(api_key=api_key)
            response = await service.classify_macro(request)
            result = response.model_dump(mode="json")

        case "filing_analyst":
            request = SearchFilingsRequest(ticker=args.ticker)
            response = await service.search_filings(request)
            result = response.model_dump(mode="json")

        case "earnings_interpreter":
            transcript = args.prompt or "No transcript provided"
            request = AnalyzeEarningsRequest(
                transcript=transcript, ticker=args.ticker
            )
            response = await service.analyze_earnings(request)
            result = response.model_dump(mode="json")

        case "quant_signal":
            request = GenerateSignalsRequest()
            response = await service.generate_signals(request)
            result = response.model_dump(mode="json")

        case "thesis_guardian":
            request = EvaluateThesisRequest(theses=[])
            response = await service.evaluate_thesis(request)
            result = response.model_dump(mode="json")

        case "risk_analyst":
            request = AssessRiskRequest()
            response = await service.assess_risk(request)
            result = response.model_dump(mode="json")

        case "adversarial":
            prompt = args.prompt or "Challenge these claims"
            request = ChallengeThesisRequest(prompt=prompt)
            response = await service.challenge_thesis(request)
            result = response.model_dump(mode="json")

        case _:
            known = ", ".join(info["name"] for info in AGENT_CATALOG)
            msg = f"Unknown agent: {args.agent}. Available: {known}"
            raise ValueError(msg)

    if args.synthesize and config.llm_provider != "skip":
        gateway = _create_gateway(config, args.model)
        synthesis = await gateway.synthesize(
            system_prompt="You are a financial analyst assistant.",
            agent_output=result.get("content", ""),
        )
        result["synthesis"] = synthesis.content

    _output(result, args)


# Default research pipeline: agents and their prompts for a given ticker
DEFAULT_PIPELINE_AGENTS = [
    ("macro_regime", "Classify current macro regime"),
    ("filing_analyst", "Search recent filings for {ticker}"),
    ("quant_signal", "Generate signals"),
    ("thesis_guardian", "Evaluate theses"),
    ("risk_analyst", "Assess portfolio risk"),
    ("adversarial", "Challenge the investment thesis for {ticker}"),
]


async def run_pipeline(args: argparse.Namespace) -> None:
    """Run multi-agent research pipeline."""
    config = _load_config()
    service = create_pipeline_service()

    # Build task list
    if args.agents:
        selected = [_normalize_agent_name(a.strip()) for a in args.agents.split(",")]
        pipeline_agents = [
            (name, prompt) for name, prompt in DEFAULT_PIPELINE_AGENTS
            if name in selected
        ]
    else:
        pipeline_agents = DEFAULT_PIPELINE_AGENTS

    tasks = [
        TaskDefinition(
            agent_name=name,
            prompt=prompt.format(ticker=args.ticker),
            task_id=f"{name}-{args.ticker}",
        )
        for name, prompt in pipeline_agents
    ]

    request = RunPipelineRequest(tasks=tasks)
    date = args.date or datetime.now(tz=UTC).strftime("%Y-%m-%d")
    response = await service.run_pipeline(request, ticker=args.ticker, date=date)

    result = response.model_dump(mode="json")

    if args.synthesize and config.llm_provider != "skip":
        gateway = _create_gateway(config, args.model)
        memo_content = ""
        if response.memo:
            memo_content = json.dumps(response.memo, default=_json_serial)
        synthesis = await gateway.synthesize(
            system_prompt="You are a financial analyst. Synthesize this research memo.",
            agent_output=memo_content,
        )
        result["synthesis"] = synthesis.content

    _output(result, args)


async def run_digest(args: argparse.Namespace) -> None:
    """Run research digest."""
    tickers = [t.strip().upper() for t in args.tickers.split(",")]

    request = RunDigestRequest(
        tickers=tickers,
        lookback_days=args.lookback_days,
        alert_threshold=Decimal(str(args.alert_threshold)),
    )
    service = DigestService()
    response = await service.run_digest(request)

    result = response.model_dump(mode="json")
    _output(result, args)


def list_agents(args: argparse.Namespace) -> None:
    """List available agents."""
    if args.output == "json":
        print(json.dumps(AGENT_CATALOG, indent=2))
    else:
        print("Available agents:\n")
        for info in AGENT_CATALOG:
            aliases = [k for k, v in AGENT_ALIASES.items() if v == info["name"]]
            alias_str = f" (alias: {aliases[0]})" if aliases else ""
            print(f"  {info['name']}{alias_str}")
            print(f"    {info['description']}\n")


def show_config(args: argparse.Namespace) -> None:
    """Show current configuration (masks sensitive values)."""
    config = _load_config()
    data = {
        "llm_provider": config.llm_provider,
        "llm_default_model": config.llm_default_model,
        "llm_temperature": config.llm_temperature,
        "fred_api_key": _mask(config.fred_api_key),
        "sec_edgar_email": config.sec_edgar_email or "(not set)",
        "azure_endpoint": config.azure.endpoint or "(not set)",
        "azure_deployment": config.azure.deployment or "(not set)",
        "azure_api_version": config.azure.api_version,
    }
    if args.output == "json":
        print(json.dumps(data, indent=2))
    else:
        print("Finance OS Configuration:\n")
        for key, value in data.items():
            print(f"  {key}: {value}")


def _mask(value: str) -> str:
    """Mask a sensitive value, showing only last 4 chars."""
    if len(value) <= 4:
        return "****" if value else "(not set)"
    return "****" + value[-4:]
