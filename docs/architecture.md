# Architecture

## System Overview

```
┌─────────────────────────────────────────────────────┐
│                   Orchestration Layer                │
│         Agent Framework (multi-agent collab)         │
├──────────┬──────────┬──────────┬──────────┬─────────┤
│  Filing  │ Earnings │  Macro   │  Thesis  │  Risk   │
│  Analyst │  Call    │  Regime  │ Guardian │  Agent  │
│  Agent   │ Interp.  │  Agent   │          │         │
├──────────┴──────────┴──────────┴──────────┴─────────┤
│                    MCP Tool Layer                    │
│  Financial │ SEC     │ Quant   │ Portfolio│ Alt     │
│  Data Tool │ Filings │ Model   │ Diag.   │ Data    │
├─────────────────────────────────────────────────────┤
│                   Data Pipeline                     │
│  EDGAR │ FRED │ Yahoo Finance │ QIF │ Vector DB    │
├─────────────────────────────────────────────────────┤
│               RAG + Knowledge Layer                 │
│  Vector Store │ Knowledge Graph │ Thesis DB         │
└─────────────────────────────────────────────────────┘
```

## Tech Stack

| Layer | Technology |
|---|---|
| MCP Server | TypeScript, Node.js, `@modelcontextprotocol/sdk` |
| Agents | Python 3.12+, NumPy, pandas, scipy |
| Vector DB | ChromaDB (local) |
| LLM Backend | Claude / GPT-4 / open models (configurable) |
| Data Sources | SEC EDGAR (free), FRED (free API key), Yahoo Finance, QIF |
| Testing | Vitest (TypeScript), pytest (Python) |
| Linting | ESLint (TypeScript), ruff (Python) |
| CI/CD | GitHub Actions |

## Data Flow

```
External APIs (EDGAR, FRED, Yahoo Finance)
        ↓
Data Pipelines (Python) → Local Data Store
        ↓
MCP Tools (TypeScript) ← LLM requests via MCP protocol
        ↓
Agents (Python) — orchestrated multi-agent reasoning
        ↓
Research Output (memos, alerts, signals)
```

## Component Details

### MCP Server (`mcp-server/`)

The MCP server exposes investment tools to LLMs via the Model Context Protocol. Each tool is a self-contained module in `src/tools/` that exports a `registerXxxTool(server)` function. Tools are stateless request handlers that validate inputs via zod schemas and return structured responses.

Entry point: `src/index.ts` registers all tools and starts the server on stdio transport.

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
