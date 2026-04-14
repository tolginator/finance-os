# Architecture

## System Overview

```
┌──────────────────────────────────────────────────────────────┐
│                        UX Layer                              │
│  Copilot CLI │ Agent CLI │ Copilot Skills │ Web API │ Web UI (future)  │
├──────────────────────────────────────────────────────────────┤
│                    Interface Layer                            │
│  TS MCP Server (data tools) │ Python MCP Server (agents)     │
│                             │ FastAPI Web API                 │
├──────────────────────────────────────────────────────────────┤
│                  Application Layer                            │
│  Pydantic Contracts │ LLM Gateway │ Agent Services            │
├──────────────────────────────────────────────────────────────┤
│                   Orchestration Layer                         │
│         Agent Framework (multi-agent collaboration)           │
├──────────┬──────────┬──────────┬──────────┬─────────┬────────┤
│  Filing  │ Earnings │  Macro   │  Thesis  │  Risk   │ Adver- │
│  Analyst │  Call    │  Regime  │ Guardian │  Agent  │ sarial │
│  Agent   │ Interp.  │  Agent   │          │         │        │
├──────────┴──────────┴──────────┴──────────┴─────────┴────────┤
│                    MCP Tool Layer                             │
│  Financial │ SEC     │ Quant   │ Portfolio│ Alt             │
│  Data Tool │ Filings │ Model   │ Diag.   │ Data            │
├──────────────────────────────────────────────────────────────┤
│                   Data Pipeline                               │
│  EDGAR │ FRED │ Yahoo Finance │ QIF │ Vector DB              │
├──────────────────────────────────────────────────────────────┤
│               RAG + Knowledge Layer                           │
│  Vector Store │ Knowledge Graph │ Thesis DB                   │
└──────────────────────────────────────────────────────────────┘
```

## Tech Stack

| Layer | Technology |
|---|---|
| MCP Server (data tools) | TypeScript, Node.js, `@modelcontextprotocol/sdk` |
| MCP Server (agents) | Python, `mcp` SDK (FastMCP, stdio transport) |
| Application Layer | Python, Pydantic 2.11+, pydantic-settings 2.9+, azure-identity 1.19+ |
| Agents | Python 3.12+, NumPy, pandas, scipy |
| Vector DB | ChromaDB (local) |
| LLM Gateway | Pluggable — OpenAI, Anthropic, ollama, or host LLM via MCP |
| Data Sources | SEC EDGAR (free), FRED (free API key), Yahoo Finance, QIF |
| CLI | Python (`finance-os` console script) |
| Copilot Skills | Markdown workflow definitions (`.github/skills/`) — earnings, thesis, digest, risk, macro |
| Testing | Vitest (TypeScript), pytest with markers (Python) — unit and integration separated |
| Linting | ESLint (TypeScript), ruff (Python) |
| CI/CD | GitHub Actions |

## LLM Gateway

The LLM gateway is a first-class component in the application layer. It resolves the fundamental question: *who does the LLM reasoning?*

```
┌─────────────────────────────────────────────────────────┐
│                   Application Layer                      │
│                                                          │
│  contracts/     Pydantic request/response models         │
│  llm/           LLMProvider protocol + implementations   │
│  services/      AgentService, PipelineService, Digest    │
│  config.py      AppConfig (config file + FINANCE_OS_* env vars)  │
└─────────────────────────────────────────────────────────┘
```

### Two inference paths

```
                         ┌─────────────────────────────────────────────┐
                         │           MCP Path (Copilot / Claude)       │
                         │                                             │
  User ──→ Copilot ──→ Host LLM ──→ MCP Server ──→ Agent Service     │
                 ↑         │              ↑              │             │
                 │         │              │              ↓             │
                 │         │         SkipProvider    Agents run()      │
                 │         │         (no LLM call)   (data + prompts)  │
                 │         │                             │             │
                 │         ←── synthesizes from ─────────┘             │
                 │              agent output                           │
                 └─────────── returns to user                         │
                         └─────────────────────────────────────────────┘

                         ┌─────────────────────────────────────────────┐
                         │           CLI Path (Direct)                 │
                         │                                             │
  User ──→ finance-os ──→ AppConfig ──→ Agent Service                 │
              CLI              │              │                        │
               │               │              ↓                        │
               │               │         Agents run()                  │
               │               │         (data + prompts)              │
               │               │              │                        │
               │               │              ↓                        │
               │      --synthesize?     structured output              │
               │           │                  │                        │
               │      ┌────┴────┐             │                        │
               │      │   YES   │       ┌─────┴─────┐                 │
               │      ↓         │       │    NO     │                  │
               │  LLM Gateway   │       ↓           │                 │
               │      │         │  print as-is      │                 │
               │      ↓         │  (text / json)    │                 │
               │  LiteLLMProvider       │           │                  │
               │      │         │       │           │                  │
               │      ↓         │       │           │                  │
               │  OpenAI /      │       │           │                  │
               │  Anthropic /   │       │           │                  │
               │  Ollama        │       │           │                  │
               │      │         │       │           │                  │
               │      ↓         │       │           │                  │
               │  synthesized   │       │           │                  │
               │  narrative     │       │           │                  │
               │      └─────────┴───────┴───→ User  │                 │
               │                                                       │
               └───────────────────────────────────────────────────────┘
```

**Key difference**: In the MCP path, the host LLM (Copilot/Claude) does all reasoning — agents just return data. In the CLI path, agents return data by default; the LLM gateway is only invoked when `--synthesize` is explicitly requested.

| Path | Who reasons? | Gateway | LLM cost |
|---|---|---|---|
| **MCP** (Copilot, Claude Desktop) | Host LLM | `SkipProvider` (no-op) | Included in host |
| **CLI** (no `--synthesize`) | Nobody — raw output | Not called | Zero |
| **CLI** (`--synthesize`) | LLM via gateway | `LiteLLMProvider` | Pay-per-call |
| **Web API** | LLM via gateway | `LiteLLMProvider` | Pay-per-call |

## Data Flow

### MCP Path (Copilot / Claude Desktop)
```
Host LLM ──→ MCP Protocol ──→ TS MCP Server ──→ Data Tools (Yahoo, EDGAR, etc.)
         └─→ MCP Protocol ──→ Py MCP Server ──→ Application Layer ──→ Agents
                                                  (gateway skipped)
```

### Direct Path (CLI / Web API)
```
User ──→ CLI / Web API ──→ Application Layer ──→ Agents ──→ structured data
                                │                              │
                                └── LLM Gateway ←──────────────┘
                                        │
                                        ↓
                                  LLM inference
                                        │
                                        ↓
                                 synthesized output
```

### Web API Path Detail
```
Client ──→ HTTP request ──→ FastAPI ──→ Application Layer ──→ Agents
  ↑           (JSON)           │              │                  │
  │                            │         AppConfig               │
  │                            │         (@lru_cache)            │
  │                            │              │                  │
  │                            │         Fresh service           │
  │                            │         per request             │
  │                            │              │                  │
  │                            ↓              ↓                  │
  │                      Pydantic         AgentService /         │
  │                      validation       PipelineService /      │
  │                      (422 on fail)    DigestService           │
  │                            │              │                  │
  │                            │         ValueError ──→ 400      │
  │                            │              │                  │
  │                            ↓              ↓                  │
  └──── JSON response ←── model_dump(mode="json") ←─────────────┘
```

## Component Details

### MCP Server (`mcp-server/`)

The TypeScript MCP server exposes investment **data tools** to LLMs via the Model Context Protocol. Each tool is a self-contained module in `src/tools/` that exports a `registerXxxTool(server)` function. Tools are stateless request handlers that validate inputs via zod schemas and return structured responses.

Entry point: `src/index.ts` registers all tools and starts the server on stdio transport.

### Application Layer (`agents/src/application/`)

The shared core that all interfaces wrap. Implemented as:

- **Contracts** (`contracts/agents.py`) — Pydantic request/response models for every agent operation (9 request/response pairs covering all 7 agents, pipeline, and digest). Models match actual agent capabilities.
- **LLM Gateway** (`llm/`) — pluggable inference via `LLMProvider` protocol:
  - `LiteLLMProvider` — multi-provider routing (OpenAI, Anthropic, ollama, etc.)
  - `SkipProvider` — MCP path where host LLM reasons
  - `LLMGateway` — routes requests, `synthesize()` for agent output → narrative
  - `create_gateway()` — factory for creating configured gateways ("skip", "litellm")
- **Services** (`services/`) — typed wrappers over agents:
  - `AgentService` — maps Pydantic request/response contracts to agent `run()` calls. Validates inputs, normalizes metadata, and caches agent instances.
  - `PipelineService` — wraps orchestrator with task_id support and memo generation
  - `DigestService` — wraps research pipeline with typed I/O
- **Config** (`config.py`) — `AppConfig` via pydantic-settings. Loads from `~/.config/finance-os/config.json` (user settings) and `FINANCE_OS_*` environment variables (highest priority).

CLI, Python MCP server, and Web API are thin wrappers over this layer.

### Web API (`agents/src/web_api.py`)

FastAPI REST service exposing the application layer over HTTP. Same shared services as CLI and MCP server — the Web API is the third thin wrapper.

**Entry points:**
- `finance-os-api` — console script (uvicorn on 127.0.0.1:8000)
- `uvicorn src.web_api:app --reload` — development mode

**Endpoints:**

| Method | Path | Service | Description |
|--------|------|---------|-------------|
| GET | `/health` | — | Health check |
| GET | `/agents` | — | List agent catalog |
| POST | `/agents/earnings_interpreter` | `AgentService.analyze_earnings()` | Earnings transcript analysis |
| POST | `/agents/macro_regime` | `AgentService.classify_macro()` | Macro regime classification |
| POST | `/agents/filing_analyst` | `AgentService.search_filings()` | SEC filing search |
| POST | `/agents/quant_signal` | `AgentService.generate_signals()` | Quant signal generation |
| POST | `/agents/thesis_guardian` | `AgentService.evaluate_thesis()` | Thesis evaluation |
| POST | `/agents/risk_analyst` | `AgentService.assess_risk()` | Portfolio risk analysis |
| POST | `/agents/adversarial` | `AgentService.challenge_thesis()` | Adversarial challenge |
| POST | `/pipeline` | `PipelineService.run_pipeline()` | Multi-agent pipeline |
| POST | `/digest` | `DigestService.run_digest()` | Research digest |

**Design:**
- **Per-request services** — fresh `AgentService` / `PipelineService` / `DigestService` per request (agents maintain internal history, so shared instances would leak state)
- **Lazy config** — `AppConfig` loaded via `@lru_cache` on first request, not at import time
- **Pydantic validation** — request bodies auto-validated by FastAPI; invalid input → 422
- **Domain errors** — `ValueError` from agents mapped to HTTP 400 (not 500)
- **CORS** — enabled for local frontend development (`allow_origins=["*"]`)
- **OpenAPI** — auto-generated schema at `/docs` (Swagger UI) and `/redoc`

### Agent Framework (`agents/`)

Domain-tuned Python agents built on a shared `BaseAgent` ABC (`src/core/agent.py`). Each agent has:
- A specialized system prompt defining its persona and capabilities
- An async `run()` method for execution
- Access to conversation history

The orchestrator (`src/core/orchestrator.py`) coordinates agents via dependency-aware pipelines with priority ordering and parallel execution. Tasks are identified by `task_id` (or agent name for backwards compatibility), enabling the same agent to run multiple times in a single pipeline.

The vector memory layer (`src/core/memory.py`) provides ChromaDB-backed RAG for document retrieval with metadata filtering.

### Research Pipeline (`agents/src/pipelines/`)

Automated pipeline that ingests data sources, routes them through agents, classifies materiality, generates alerts, and produces research digests.

### Prompt Library (`prompts/`)

Shared prompt templates organized by strategy:
- **Roles** — role-stacking multi-persona prompts
- **Analysis** — constraint-driven analytical templates
- **Adversarial** — thesis-challenging prompts
- **Synthesis** — multi-document cross-reference prompts

## Phasing

| Phase | Focus | Status |
|---|---|---|
| 0 | Repository foundation, MCP server, agent framework | ✅ Complete |
| 1 | Core tools and agents (SEC, earnings, macro, quant, portfolio) | ✅ Complete |
| 2 | Intelligence layer (thesis, risk, adversarial, orchestrator, pipeline) | ✅ Complete |
| 3 | Integration layer (application layer + LLM gateway, CLI, Python MCP, Skills) | ✅ Complete |
| 4 | Advanced (knowledge graph, alt data, fine-tuning) — Copilot-first | Planned |
| 5 | Web layer (FastAPI + Web UI) | 🔧 In Progress |

### Phase 5 Progress

| Component | Issue | Status |
|---|---|---|
| Web API (FastAPI) | #58 | ✅ Complete |
| Web UI | #57 | Planned |

### Phase 3 Progress

| Component | Issue | Status |
|---|---|---|
| Application layer (contracts, LLM gateway, services, config) | #49 | ✅ Complete |
| Agent CLI | #50 | ✅ Complete |
| Python MCP server | #51 | ✅ Complete |
| Copilot Skills | #53 | ✅ Complete |
