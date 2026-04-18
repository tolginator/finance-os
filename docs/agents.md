# Agents

## Overview

All agents extend `BaseAgent` in `agents/src/core/agent.py`, which defines:
- `run(prompt, **kwargs) -> AgentResponse` — async execution
- `system_prompt` — the agent's persona and capabilities
- Conversation history management

### Current state: no LLM calls

Agents currently perform deterministic data processing (regex, heuristics, statistics) and construct prompts, but **do not call an LLM directly**. This is by design for the MCP path, where the host LLM (Copilot, Claude Desktop) does the reasoning. For the CLI and web paths, the **LLM gateway** in the application layer handles inference — see [architecture.md](architecture.md#llm-gateway).

## Agent Catalog

### Active Agents

| Agent | Module | Purpose |
|---|---|---|
| Macro Regime | `macro_regime.py` | Classifies macro environment (growth/rates/inflation/trade regimes) from FRED data |
| Quant Signal | `quant_signal.py` | Transforms macro insights into structured, confidence-weighted quant features |
| Risk Agent | `risk_agent.py` | VaR/CVaR, volatility, scenario stress tests, correlation analysis, factor decomposition |

### Planned Agents (in development)

| Agent | Module | Purpose |
|---|---|---|
| Macro Outlook | `macro_outlook.py` | Synthesizes multi-source macro data into forward-looking asset-class tilts bounded by policy allocation |
| Portfolio Evaluator | `portfolio_evaluator.py` | Dimensioned portfolio evaluation — policy drift, concentration, macro alignment, liquidity, tax drag, scenario exposure |
| Rebalancing | `rebalancing.py` | Goal-driven rebalancing recommendations — directional (v1), account-aware (v2), tax-lot-aware (v3) |

### Retiring Agents (being removed after new UI is ready)

| Agent | Module | Reason |
|---|---|---|
| Filing Analyst | `filing_analyst.py` | Stock-picking focused — extracts SEC filing deltas, risk language shifts |
| Earnings Interpreter | `earnings_interpreter.py` | Stock-picking focused — individual company transcript analysis |
| Thesis Guardian | `thesis_guardian.py` | Stock-picking focused — per-ticker thesis monitoring |
| Adversarial | `adversarial.py` | Stock-picking focused — individual company thesis challenger |

These agents remain functional during the transition but will be removed from the registry, API endpoints, MCP tools, and UI once the portfolio-centric UI redesign (Phase 5A) is complete.

## Orchestration

The `Orchestrator` (`agents/src/core/orchestrator.py`) coordinates agents:

- **Agent registry** — register and discover agents by name
- **Task identity** — tasks have explicit `task_id`, enabling the same agent to run multiple times in a pipeline
- **Dependency-aware pipeline** — tasks declare dependencies by task ID; independent tasks run in parallel via `asyncio.gather`
- **Priority ordering** — higher-priority tasks execute first within each dependency level
- **Graceful failure** — failed tasks don't crash the pipeline; dependent tasks get error messages
- **Research memos** — aggregate agent outputs into structured memos with sections and source attribution

### Application Services

The application layer (`agents/src/application/services/`) provides typed wrappers:

- **`AgentService`** — maps Pydantic request/response contracts to agent `run()` calls. Validates inputs, normalizes metadata, and caches agent instances.
- **`PipelineService`** — wraps orchestrator with task definitions from typed contracts, optional memo generation.
- **`DigestService`** — wraps research pipeline with typed I/O and formatted output.
- **`HouseholdService`** (planned) — portfolio CRUD, CSV/QIF import, schema validation, change journaling.
- **`ETFTaxonomyService`** (planned) — ETF → asset class mapping, look-through exposure aggregation.
- **`TickerService`** — ETF/company summary and transcript lookup from Yahoo Finance with caching and dedup.

### New Agent Integration Pattern

Each new agent follows the existing pattern:
1. Create agent class extending `BaseAgent` in `src/agents/`
2. Add to `AGENT_CATALOG` in `src/application/registry.py`
3. Create Pydantic request/response contracts in `src/application/contracts/`
4. Add `AgentService` method wrapping the agent
5. Add API endpoint in `src/web_api.py`
6. Add MCP tool in `src/mcp_server.py`
7. Add tests for all layers

## Data Sources

### Active

| Source | Used By | Data |
|---|---|---|
| FRED | Macro Regime, Macro Outlook (planned) | GDP, employment, inflation, rates, spreads, sentiment, production |
| Yahoo Finance | Ticker Service, ETF Taxonomy (planned) | ETF prices, holdings, expense ratios, categories |

### Planned

| Source | Used By | Data |
|---|---|---|
| BLS | Macro Outlook | Detailed CPI components, employment by sector, productivity |
| Treasury.gov | Macro Outlook | Yield curves, real yields, fiscal data |
| IMF | Macro Outlook | Global GDP, trade balances, exchange rates |
| World Bank | Macro Outlook | Development indicators, global growth |

### Retired

| Source | Reason |
|---|---|
| SEC EDGAR | Stock-picking focused — individual company filings not needed for macro ETF analysis |

## MCP Server (Python)

The Python MCP server (`agents/src/mcp_server.py`) exposes agents as tools for any MCP-compatible client via stdio transport.

### Running

```bash
cd agents && source .venv/bin/activate
finance-os-mcp          # via console script
python -m src.mcp_server  # direct invocation
```

### Tool Catalog

| Tool | Wraps | Purpose |
|---|---|---|
| `classify_macro` | `AgentService.classify_macro()` | Macro regime classification from FRED data |
| `research_digest` | `DigestService.run_digest()` | Watchlist digest — materiality scoring, alerts |
| `orchestrate` | `PipelineService.run_pipeline()` | Multi-agent pipeline with dependency ordering |

Planned tools: `macro_outlook`, `evaluate_portfolio`, `rebalance`

### Design

- **Per-request services** — fresh agent instances per tool call to avoid state leakage
- **Structured responses** — tools return dicts; MCP protocol handles serialization
- **Server-side config** — secrets (FRED API key) come from `AppConfig`, not tool inputs
- **Agent validation** — `orchestrate` rejects unknown agent names upfront
- **LLM gateway skipped** — host LLM reasons; agents return structured data

## Web API (FastAPI)

The Web API (`agents/src/web_api.py`) exposes the same application layer services over HTTP/REST.

### Running

```bash
cd agents && source .venv/bin/activate
finance-os-api            # via console script (127.0.0.1:8000)
uvicorn src.web_api:app --reload  # development mode
```

### Design

- **Per-request services** — fresh agent instances per request to avoid state leakage
- **Pydantic contracts** — same request/response models as MCP server; FastAPI auto-validates and generates OpenAPI schema
- **Error mapping** — domain `ValueError` → HTTP 400; Pydantic validation → 422
- **CORS** — enabled for local frontend development
- **LLM gateway available** — Web API path can invoke LLM gateway for synthesis
