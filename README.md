# finance-os

Personal Investment Intelligence OS — a modular, LLM-powered investing AI stack with agent orchestration, domain-tuned prompting, custom MCP tools, and deep integration with quant + NLP pipelines.

Not a chatbot. A **system**. The personal Bloomberg terminal + quant lab + research team.

## Goals

- **Automated research**: Ingest SEC filings, earnings transcripts, and macro data — extract signals, score sentiment, flag material changes
- **Thesis monitoring**: Define investment theses with explicit assumptions — get alerts when assumptions weaken or break
- **Risk analysis**: Scenario modeling, stress tests, tail-risk simulation, concentration analysis
- **Adversarial challenge**: Every thesis gets systematically attacked before capital is deployed
- **Quantitative signals**: Transform unstructured text into structured, timestamped, confidence-weighted quant features
- **Multi-agent orchestration**: Agents collaborate and debate to produce consolidated research memos
- **LLM-native**: Pluggable LLM gateway for direct inference (CLI, future web) or delegate to host LLM (Copilot, Claude Desktop via MCP)

## Project Structure

```
finance-os/
├── mcp-server/          # TypeScript MCP server (data tools for LLMs)
├── agents/              # Python agent framework + application layer
│   └── src/
│       ├── agents/      # Domain agents (filing, earnings, macro, risk, etc.)
│       ├── core/        # BaseAgent, orchestrator, vector memory
│       ├── application/ # Contracts, LLM gateway, services, config
│       ├── cli/         # CLI entry points (finance-os command)
│       └── pipelines/   # Research digest pipeline
├── prompts/             # Shared prompt library
├── docs/                # Architecture, agent, and tool documentation
└── .github/             # CI, copilot instructions, skills, templates
```

See [docs/architecture.md](docs/architecture.md) for the full system architecture, LLM gateway design, and data flow.
See [docs/agents.md](docs/agents.md) for agent descriptions and the orchestration model.
See [docs/tools.md](docs/tools.md) for MCP tool reference and how to add new tools.

## Getting Started

### Prerequisites

- **Node.js** 22+ and npm
- **Python** 3.12+ with venv

### MCP Server (TypeScript)

```bash
cd mcp-server
npm install
npm run build
npm test
```

### Agents (Python)

```bash
cd agents
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -m "not integration"    # unit tests only
pytest -m integration          # integration tests (requires API keys)
```

### Configuration

Create `~/.config/finance-os/config.json`:

```json
{
  "fred_api_key": "your-fred-api-key",
  "llm_provider": "skip",
  "sec_edgar_email": "your-email@example.com",
  "azure_openai_endpoint": "https://your-instance.openai.azure.com",
  "azure_openai_deployment": "gpt-4o"
}
```

Environment variables (`FINANCE_OS_*`) override config file values. See [docs/architecture.md](docs/architecture.md) for details.

| Field | Values | Description |
|-------|--------|-------------|
| `llm_provider` | `"skip"` (default), `"azure_openai"` | `skip` returns raw agent data without LLM synthesis — ideal for the MCP path where Copilot/Claude reasons over the output. `azure_openai` enables LLM synthesis via Azure OpenAI with Entra ID (OAuth2/OIDC) authentication — no API keys required. |
| `azure_openai_endpoint` | URL string | Azure OpenAI resource endpoint (e.g. `https://my-instance.openai.azure.com`). Required when provider is `"azure_openai"`. |
| `azure_openai_deployment` | Deployment name | Azure OpenAI model deployment name (e.g. `gpt-4o`). This is the deployment you created in Azure AI Studio. Required when provider is `"azure_openai"`. |
| `azure_openai_api_version` | API version string | Azure OpenAI API version. Default `"2024-10-21"`. |
| `llm_temperature` | `0.0`–`2.0` | Sampling temperature for LLM calls. Default `0.0` (deterministic). |
| `fred_api_key` | API key string | [FRED API](https://fred.stlouisfed.org/docs/api/api_key.html) key for the macro-regime agent. Free to obtain. |
| `sec_edgar_email` | Email address | **Required for SEC API access.** SEC requires a valid contact email in request headers — set this to a real email you control. |

> **Azure authentication**: Uses `DefaultAzureCredential` which supports Azure CLI (`az login`), managed identity, workload identity, and environment credentials. No API keys are stored in config. Requires the `Cognitive Services OpenAI User` RBAC role on the Azure OpenAI resource.

### Agent CLI

After installing the agents package (`pip install -e ".[dev]"`), the `finance-os` command is available:

```bash
finance-os list                                      # List available agents
finance-os config                                    # Show current config
finance-os run macro-regime                          # Run a single agent
finance-os run filing-analyst --ticker AAPL           # With options
finance-os pipeline --ticker AAPL                     # Multi-agent research pipeline
finance-os digest --tickers AAPL,MSFT,GOOG            # Research digest
finance-os --output json run macro-regime             # JSON output
finance-os run adversarial --prompt "Bull case" --synthesize  # LLM synthesis
```

Use `--synthesize` to pass agent output through the LLM gateway (requires `llm_provider: "litellm"` in config). Use `--output json` for structured output.

### Preflight (run before every push)

From the repo root:

```bash
npm run preflight
```

This mirrors CI: build → unit test → lint (TypeScript), then ruff → unit pytest (Python). Integration tests run in CI only on pushes to `main`.

## Development

### Git Workflow

- Never commit to `main` — use worktrees and feature branches
- Make separate, descriptive commits per logical change; squash merge PRs
- Branch naming: `<username>/<MeaningfulDescription>`
- Every PR must have a corresponding issue created first
- Run `npm run preflight` before pushing

### Adding a New MCP Tool

1. Create `mcp-server/src/tools/<name>.ts` exporting `registerXxxTool(server)`
2. Register in `src/index.ts`
3. Add tests in `mcp-server/tests/<name>.test.ts`

### Adding a New Agent

1. Create `agents/src/agents/<name>.py` extending `BaseAgent`
2. Implement `run()` and `system_prompt` property
3. Add tests in `agents/tests/test_<name>.py`

## License

MIT
