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
- **LLM-native**: Pluggable LLM gateway for direct inference (CLI, web) or delegate to host LLM (Copilot, Claude Desktop via MCP)

## Project Structure

```
finance-os/
├── mcp-server/          # TypeScript MCP server (data tools for LLMs)
├── agents/              # Python agent framework + application layer
│   └── src/
│       ├── agents/      # Domain agents (filing, earnings, macro, risk, etc.)
│       ├── core/        # BaseAgent, orchestrator, vector memory
│       ├── application/ # Contracts, LLM gateway, services, config, registry
│       ├── cli/         # CLI entry points (finance-os command)
│       ├── mcp_server.py # Python MCP server (finance-os-mcp command)
│       ├── web_api.py   # FastAPI web server (finance-os-api command)
│       └── pipelines/   # Research digest pipeline
├── web-ui/              # React frontend (Vite + TypeScript)
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
  "azure": {
    "endpoint": "",
    "deployment": "",
    "api_version": "2024-10-21"
  }
}
```

Environment variables (`FINANCE_OS_*`) override config file values — use double underscore for nested fields (e.g. `FINANCE_OS_AZURE__ENDPOINT`). See [docs/architecture.md](docs/architecture.md) for details.

| Field | Values | Description |
|-------|--------|-------------|
| `llm_provider` | `"skip"` (default), `"azure_openai"` | `skip` returns raw agent data without LLM synthesis — ideal for the MCP path where Copilot/Claude reasons over the output. `azure_openai` enables LLM synthesis via Azure OpenAI with Entra ID (OAuth2/OIDC) authentication — no API keys required. |
| `azure.endpoint` | URL string | Azure OpenAI resource endpoint (e.g. `https://my-instance.openai.azure.com`). Required when provider is `"azure_openai"`. |
| `azure.deployment` | Deployment name | Azure OpenAI model deployment name (e.g. `gpt-4.1-mini`). This is the deployment you created in Azure AI Studio. Required when provider is `"azure_openai"`. |
| `azure.api_version` | API version string | Azure OpenAI API version. Default `"2024-10-21"`. |
| `llm_temperature` | `0.0`–`2.0` | Sampling temperature for LLM calls. Default `0.0` (deterministic). |
| `fred_api_key` | API key string | [FRED API](https://fred.stlouisfed.org/docs/api/api_key.html) key for the macro-regime agent. Free to obtain. |
| `sec_edgar_email` | Email address | **Required for SEC API access.** SEC requires a valid contact email in request headers — set this to a real email you control. |

> **Azure authentication**: Uses `DefaultAzureCredential` which supports Azure CLI (`az login`), managed identity, workload identity, and environment credentials. No API keys are stored in config. Requires the `Cognitive Services OpenAI User` RBAC role on the Azure OpenAI resource. See the [Azure Deployment Guide](docs/azure-deployment.md) for step-by-step setup.

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

Use `--synthesize` to pass agent output through the LLM gateway (requires a configured LLM provider). Use `--output json` for structured output.

### Python MCP Server

The Python MCP server exposes agents as tools for any MCP-compatible client (Copilot CLI, Claude Desktop, Cursor, etc.):

```bash
finance-os-mcp              # via console script (stdio transport)
python -m src.mcp_server    # direct invocation
```

Tools available: `analyze_earnings`, `classify_macro`, `research_digest`, `orchestrate`. The `analyze_earnings` tool accepts a ticker symbol and auto-fetches the latest transcript from Yahoo Finance. See [docs/tools.md](docs/tools.md) for details.

### Web API

REST API wrapping the same application layer as CLI and MCP server.

```bash
# Setup (one-time, from agents/ directory)
cd agents
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Start the server
finance-os-api                              # production (127.0.0.1:8000)
uvicorn src.web_api:app --reload            # development with auto-reload
```

Once running, open http://127.0.0.1:8000/docs for interactive Swagger UI.

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/agents` | List available agents |
| GET | `/ticker/{symbol}/summary` | Fetch company summary from Yahoo Finance (cached 5 min) |
| GET | `/ticker/{symbol}/transcript` | Fetch latest earnings transcript (cached 1 hour) |
| POST | `/agents/earnings_interpreter` | Analyze earnings transcripts (accepts ticker or transcript) |
| POST | `/agents/macro_regime` | Classify macro regime |
| POST | `/agents/filing_analyst` | Search SEC filings |
| POST | `/agents/quant_signal` | Generate quant signals |
| POST | `/agents/thesis_guardian` | Evaluate investment theses |
| POST | `/agents/risk_analyst` | Portfolio risk analysis |
| POST | `/agents/adversarial` | Challenge thesis adversarially |
| POST | `/pipeline` | Multi-agent research pipeline |
| POST | `/digest` | Research digest for watchlist |
| POST | `/kg/extract` | Extract entities/relationships into knowledge graph |
| POST | `/kg/query/related` | Find entities related to a given entity |
| POST | `/kg/query/supply-chain` | Trace supply chain from an entity |
| POST | `/kg/query/shared-risks` | Find shared risks across entities |
| GET | `/kg/stats` | Knowledge graph summary statistics |
| GET | `/watchlists` | List all watchlists |
| POST | `/watchlists` | Create a new watchlist |
| GET | `/watchlists/{name}` | Get a specific watchlist |
| PUT | `/watchlists/{name}` | Update tickers in a watchlist |
| DELETE | `/watchlists/{name}` | Delete a watchlist |
| PUT | `/watchlists/{name}/activate` | Set a watchlist as active |

**Example:**

```bash
# Health check
curl http://127.0.0.1:8000/health

# Look up a ticker
curl http://127.0.0.1:8000/ticker/AAPL/summary

# Run a research digest
curl -X POST http://127.0.0.1:8000/digest \
  -H "Content-Type: application/json" \
  -d '{"tickers": ["AAPL", "MSFT"], "lookback_days": 7}'

# Search SEC filings
curl -X POST http://127.0.0.1:8000/agents/filing_analyst \
  -H "Content-Type: application/json" \
  -d '{"ticker": "AAPL", "form_type": "10-K"}'
```

### Web UI

React frontend consuming the Web API. Requires the API server to be running.

```bash
# Terminal 1 — start the API server
cd agents && source .venv/bin/activate && finance-os-api

# Terminal 2 — install dependencies and start the frontend dev server
cd web-ui
npm install
npm run dev    # opens http://localhost:5173 with API proxy
```

The dev server proxies `/api/*` requests to the backend at `http://127.0.0.1:8000`. For production builds:

```bash
cd web-ui && npm run build    # outputs to web-ui/dist/
```

**UI Features:**

| Feature | Description |
|---------|-------------|
| **Ticker Bar** | Enter a ticker symbol to auto-discover company data from Yahoo Finance — name, sector, price, market cap, 52W range, earnings date, and latest transcript |
| **Agent Runner** | Run any agent with a dynamic form. Fields auto-populate from ticker context (e.g. entering AAPL fills transcript and ticker fields automatically). Dirty-field tracking preserves manual edits. |
| **Pipeline Runner** | Define and execute multi-agent pipelines with dependency ordering. Visualizes per-task results and overall duration. Detects dependency cycles before execution. |
| **Knowledge Graph** | Extract entities and relationships from text, then query the graph — related entities, supply chain tracing, shared risk analysis. Displays entity/relationship counts by type. |
| **Watchlists** | Create, switch, and manage named ticker watchlists. Active watchlist auto-loads into the digest panel. |
| **Research Digest** | Run a multi-agent digest for your watchlist tickers. Configure lookback period. View materiality alerts and signal counts. |
| **System Health** | Live API connectivity indicator, agent catalog, and knowledge graph statistics. |

### Copilot Skills

Copilot Skills (`.github/skills/`) teach Copilot how to use finance-os tools together for investment analysis workflows. They are auto-detected by Copilot in IDE and CLI.

| Skill | Trigger | What it does |
|-------|---------|-------------|
| `earnings-analysis` | "analyze earnings for AAPL" | Run earnings interpreter, score sentiment, extract guidance |
| `thesis-evaluation` | "challenge my bull thesis on MSFT" | Adversarial challenge + blind spots + conviction scoring |
| `research-digest` | "daily briefing for my watchlist" | Auto-fetch filings, classify macro, generate alerts |
| `risk-assessment` | "stress test my portfolio" | VaR, concentration, scenario analysis |
| `macro-overview` | "what's the macro regime?" | FRED-based regime classification + implications |

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
