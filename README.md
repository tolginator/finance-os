# finance-os

Personal Investment Intelligence OS — a modular, LLM-powered investing AI stack with agent orchestration, domain-tuned prompting, custom MCP tools, and deep integration with quant + NLP pipelines.

Not a chatbot. A **system**.

## Architecture

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

## Components

### MCP Server (`mcp-server/`)

TypeScript MCP server exposing investment tools to LLMs:

- **Financial Data** — stock quotes, fundamentals, historical prices
- **SEC Filings** — EDGAR 10-K/10-Q/8-K fetch, parse, section extraction
- **Portfolio Diagnostics** — exposures, drawdowns, concentration, liquidity risk
- **QIF Data Access** — query personal transaction data from Quicken exports

### Agents (`agents/`)

Python domain-tuned agents that collaborate or debate:

- **Filing Analyst** — extracts deltas, risk language shifts, capex changes
- **Earnings Interpreter** — tone analysis, sentiment drift, management confidence
- **Macro Regime** — classifies macro environment from text + data
- **Quant Signal** — transforms textual insights into structured quant features
- **Thesis Guardian** — monitors theses, flags broken assumptions
- **Risk Agent** — scenario analysis, stress tests, tail-risk simulations
- **Adversarial** — systematic thesis challenger

### Prompt Library (`prompts/`)

Shared prompt templates for expert-level financial analysis:

- Role-stacking (multi-persona collaboration)
- Constraint-driven (stepwise reasoning with evidence)
- Adversarial (thesis attack from multiple angles)
- Multi-document synthesis (cross-company, cross-filing)

## Getting Started

### MCP Server

```bash
cd mcp-server
npm install
npm run build
npm test
```

### Agents

```bash
cd agents
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

### Preflight (run before every push)

```bash
npm run preflight
```

## Tech Stack

| Layer | Technology |
|---|---|
| MCP Server | TypeScript, `@modelcontextprotocol/sdk` |
| Agents | Python, NumPy, pandas |
| Vector DB | ChromaDB (v0) |
| LLM Backend | Claude / GPT-4 / open models (configurable) |
| Data Sources | SEC EDGAR, FRED, Yahoo Finance, QIF |

## License

MIT
