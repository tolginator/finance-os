# Architecture

## System Overview

```
┌──────────────────────────────────────────────────────────────┐
│                        UX Layer                              │
│  Copilot CLI │ Agent CLI │ Copilot Skills │ Web UI (future)  │
├──────────────────────────────────────────────────────────────┤
│                    Interface Layer                            │
│  TS MCP Server (data tools) │ Python MCP Server (agents)     │
│                             │ Web API / FastAPI (future)      │
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
| MCP Server (agents) | Python, `mcp` SDK (planned) |
| Application Layer | Python, Pydantic, litellm (planned) |
| Agents | Python 3.12+, NumPy, pandas, scipy |
| Vector DB | ChromaDB (local) |
| LLM Gateway | Pluggable — OpenAI, Anthropic, ollama, or host LLM via MCP |
| Data Sources | SEC EDGAR (free), FRED (free API key), Yahoo Finance, QIF |
| CLI | Python (`python -m agents.cli`, planned) |
| Copilot Skills | Markdown workflow definitions (`.github/skills/`, planned) |
| Testing | Vitest (TypeScript), pytest (Python) |
| Linting | ESLint (TypeScript), ruff (Python) |
| CI/CD | GitHub Actions |

## LLM Gateway

The LLM gateway is a first-class component in the application layer, not a bolt-on. It resolves the fundamental question: *who does the LLM reasoning?*

```
┌─────────────────────────────────────────────────────────┐
│                   Application Layer                      │
│                                                          │
│  contracts/     Pydantic request/response models         │
│  llm/           Pluggable inference client               │
│  services/      Agent invocation, orchestration           │
│  config/        Provider selection, model routing          │
└─────────────────────────────────────────────────────────┘
```

### Two inference paths

| Path | How LLM reasoning works |
|---|---|
| **MCP path** (Copilot, Claude Desktop) | Host LLM calls MCP tools → agents return structured data + prompts → host LLM synthesizes. Gateway is **skipped**. |
| **Direct path** (CLI, future Web API) | User invokes agent → application layer calls LLM gateway → agents return data → gateway calls LLM for synthesis. |

### Why this matters

The agents currently build prompts and structure data but **never call an LLM**. This is correct for the MCP path where the host LLM reasons. But the CLI and web paths need their own LLM inference — the gateway provides it without duplicating agent logic.

### Provider flexibility

The gateway is pluggable:
- **Cloud**: OpenAI, Anthropic, Google (via litellm or native SDKs)
- **Local**: ollama, llama.cpp
- **Skip**: MCP consumers can bypass the gateway entirely

## Data Flow

### MCP Path (Copilot / Claude Desktop)
```
Host LLM ──→ MCP Protocol ──→ TS MCP Server ──→ Data Tools (Yahoo, EDGAR, etc.)
         └─→ MCP Protocol ──→ Py MCP Server ──→ Application Layer ──→ Agents
                                                  (gateway skipped)
```

### Direct Path (CLI / future Web)
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

## Component Details

### MCP Server (`mcp-server/`)

The TypeScript MCP server exposes investment **data tools** to LLMs via the Model Context Protocol. Each tool is a self-contained module in `src/tools/` that exports a `registerXxxTool(server)` function. Tools are stateless request handlers that validate inputs via zod schemas and return structured responses.

Entry point: `src/index.ts` registers all tools and starts the server on stdio transport.

### Application Layer (`agents/src/application/`, planned)

The shared core that all interfaces wrap. Contains:
- **Contracts** — Pydantic request/response models for every agent operation
- **LLM gateway** — pluggable inference client with provider routing
- **Services** — agent invocation, orchestration coordination, pipeline triggers
- **Config** — provider selection, model routing, API key management

CLI, Python MCP server, and future Web API are thin wrappers over this layer.

### Agent Framework (`agents/`)

Domain-tuned Python agents built on a shared `BaseAgent` ABC (`src/core/agent.py`). Each agent has:
- A specialized system prompt defining its persona and capabilities
- An async `run()` method for execution
- Access to conversation history

The orchestrator (`src/core/orchestrator.py`) coordinates agents via dependency-aware pipelines with priority ordering and parallel execution.

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
| 3 | Integration layer (application layer + LLM gateway, CLI, Python MCP, Skills) | 🔜 Next |
| 4 | Advanced (knowledge graph, alt data, fine-tuning) — Copilot-first | Planned |
| 5 | Web layer (FastAPI + Web UI) — after Copilot CLI is mostly complete | Planned |
