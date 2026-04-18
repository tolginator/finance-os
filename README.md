# finance-os

Macro ETF Portfolio Intelligence — a modular, LLM-powered system for macroeconomic outlook-driven investment evaluation and goal-driven portfolio rebalancing.

Built for a **wealthy family** ($2M–$10M investable assets): capital preservation with moderate growth, tax-efficient ETF portfolios, retirement readiness, and multi-generational wealth building. US-focused with global economy considerations.

Not a stock picker. Not a chatbot. A **portfolio intelligence system**.

## Goals

- **Macro outlook**: Multi-dimensional regime classification (growth, rates, inflation, global trade) from FRED, BLS, Treasury, IMF, and World Bank data
- **Portfolio evaluation**: Dimensioned health metrics — policy drift, concentration risk, macro alignment, liquidity adequacy, tax drag, scenario exposure
- **Goal-driven rebalancing**: Retirement (3–4% SWR, capital preservation) and wealth building (growth tilt, accumulation) with custom goal support
- **Scenario stress testing**: Historical scenarios (2008, 2022, stagflation, etc.) applied to your portfolio with loss estimates
- **ETF taxonomy**: Look-through exposure analysis — asset class, sector, geography, duration breakdown
- **Policy-first**: Macro tilts are bounded by your Investment Policy Statement — the system never overrides strategic allocation
- **Credible data only**: Government and institutional sources. No social network data.

## Project Structure

```
finance-os/
├── mcp-server/          # TypeScript MCP server (data tools for LLMs)
├── agents/              # Python agent framework + application layer
│   └── src/
│       ├── agents/      # Domain agents (macro, risk, outlook, evaluator, rebalancer)
│       ├── core/        # BaseAgent, orchestrator, vector memory
│       ├── application/ # Contracts, LLM gateway, services, config, registry
│       │   └── services/
│       │       ├── household_service.py   # Portfolio CRUD, import (CSV/QIF)
│       │       ├── etf_taxonomy.py        # ETF → asset class mapping
│       │       ├── ticker_service.py      # ETF summary lookup (Yahoo Finance)
│       │       └── ...
│       ├── cli/         # CLI entry points (finance-os command)
│       ├── mcp_server.py # Python MCP server (finance-os-mcp command)
│       ├── web_api.py   # FastAPI web server (finance-os-api command)
│       └── pipelines/   # Data ingestion pipelines
├── web-ui/              # React frontend (Vite + TypeScript)
├── prompts/             # Shared prompt library
├── docs/                # Architecture, agent, and tool documentation
└── .github/             # CI, copilot instructions, skills, templates
```

See [docs/architecture.md](docs/architecture.md) for the full system architecture.
See [docs/agents.md](docs/agents.md) for agent descriptions and the orchestration model.

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
  "bls_api_key": "your-bls-api-key",
  "llm_provider": "skip",
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
| `llm_provider` | `"skip"` (default), `"azure_openai"` | `skip` returns raw agent data without LLM synthesis — ideal for the MCP path where Copilot/Claude reasons over the output. `azure_openai` enables LLM synthesis via Azure OpenAI. |
| `azure.endpoint` | URL string | Azure OpenAI resource endpoint. Required when provider is `"azure_openai"`. |
| `azure.deployment` | Deployment name | Azure OpenAI model deployment name. Required when provider is `"azure_openai"`. |
| `azure.api_version` | API version string | Azure OpenAI API version. Default `"2024-10-21"`. |
| `llm_temperature` | `0.0`–`2.0` | Sampling temperature for LLM calls. Default `0.0` (deterministic). |
| `fred_api_key` | API key string | [FRED API](https://fred.stlouisfed.org/docs/api/api_key.html) key for macro data. Free to obtain. |
| `bls_api_key` | API key string | [BLS API](https://www.bls.gov/developers/) key for employment and CPI data. Free to obtain. |

> **Azure authentication**: Uses `DefaultAzureCredential` which supports Azure CLI (`az login`), managed identity, workload identity, and environment credentials. No API keys are stored in config.

### Data Sources

All data comes from credible government and institutional sources. **No social network data.**

| Source | Data | Auth | Cost |
|--------|------|------|------|
| [FRED](https://fred.stlouisfed.org/) | GDP, employment, inflation, rates, spreads, sentiment, production | API key | Free |
| [Yahoo Finance](https://finance.yahoo.com/) | ETF prices, holdings (best-effort), expense ratios, categories | None | Free |
| [BLS](https://www.bls.gov/developers/) | Detailed CPI components, employment by sector, productivity | API key | Free |
| [Treasury.gov](https://home.treasury.gov/data) | Yield curves, real yields, fiscal data, auction results | None | Free |
| [IMF Data](https://data.imf.org/) | Global GDP forecasts, trade balances, exchange rates | None | Free |
| [World Bank](https://data.worldbank.org/) | Development indicators, global growth trends | None | Free |

### Agent CLI

After installing the agents package (`pip install -e ".[dev]"`), the `finance-os` command is available:

```bash
finance-os list                                      # List available agents
finance-os config                                    # Show current config
finance-os run macro-regime                          # Classify macro regime
finance-os run risk-analyst                          # Portfolio risk analysis
finance-os run quant-signal                          # Generate macro signals
finance-os pipeline --ticker VTI                     # Multi-agent research pipeline
finance-os --output json run macro-regime            # JSON output
```

### Python MCP Server

The Python MCP server exposes agents as tools for any MCP-compatible client (Copilot CLI, Claude Desktop, Cursor, etc.):

```bash
finance-os-mcp              # via console script (stdio transport)
python -m src.mcp_server    # direct invocation
```

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

**Current Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/agents` | List available agents |
| GET | `/ticker/{symbol}/summary` | Fetch ETF/company summary from Yahoo Finance (cached 5 min) |
| GET | `/ticker/{symbol}/transcript` | Fetch latest earnings transcript (cached 1 hour) |
| POST | `/agents/macro_regime` | Classify macro regime from FRED data |
| POST | `/agents/quant_signal` | Generate quant signals |
| POST | `/agents/risk_analyst` | Portfolio risk analysis |
| POST | `/pipeline` | Multi-agent research pipeline |
| POST | `/digest` | Research digest for watchlist |
| GET | `/watchlists` | List all watchlists |
| POST | `/watchlists` | Create a new watchlist |
| GET | `/watchlists/{name}` | Get a specific watchlist |
| PUT | `/watchlists/{name}` | Update tickers in a watchlist |
| DELETE | `/watchlists/{name}` | Delete a watchlist |
| PUT | `/watchlists/{name}/activate` | Set a watchlist as active |

**Planned Endpoints (coming in Phases 1–4):**

| Method | Path | Description |
|--------|------|-------------|
| GET/POST | `/portfolio/*` | Household portfolio CRUD, import |
| POST | `/agents/macro_outlook` | Forward-looking macro outlook with asset-class tilts |
| POST | `/agents/portfolio_evaluator` | Dimensioned portfolio evaluation |
| POST | `/agents/rebalance` | Goal-driven rebalancing recommendations |
| GET | `/scenarios` | Scenario library for stress testing |

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

### Preflight (run before every push)

From the repo root:

```bash
npm run preflight
```

This mirrors CI: build → unit test → lint (TypeScript), then ruff → unit pytest (Python). Integration tests run in CI only on pushes to `main`.

## Asset Class Taxonomy

The system uses a two-layer taxonomy for ETF classification:

**Canonical** (for allocation decisions): US Equity, International Developed, Emerging Markets, US Treasuries, IG Corporate Bonds, High Yield, TIPS/Inflation-Linked, Real Assets (REITs/Commodities), Cash/Money Market

**Diagnostic** (for deeper analysis): Large/Small cap, Value/Growth, Sector, Duration buckets, Credit quality, Currency exposure

## Wealthy Family Persona

The system is calibrated for a wealthy family, not an average household:

- **$2M–$10M investable assets** — beyond basic financial planning, below institutional complexity
- **Can retire anytime** — capital preservation priority, not accumulation-only
- **3–4% safe withdrawal rate** — sustainable, inflation-adjusted spending
- **Tax-efficiency matters** — account type awareness (taxable, IRA, Roth, 401k, HSA, Trust)
- **Multi-generational** — wealth transfer considerations, not just single-lifetime planning
- **Not lavish** — comfortable lifestyle maintenance, not luxury optimization

## Development

### Git Workflow

- Never commit to `main` — use worktrees and feature branches
- Make separate, descriptive commits per logical change; squash merge PRs
- Branch naming: `<username>/<MeaningfulDescription>`
- Every PR must have a corresponding issue created first
- Run `npm run preflight` before pushing

## License

MIT
