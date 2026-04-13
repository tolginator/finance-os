# Agents

## Overview

All agents extend `BaseAgent` in `agents/src/core/agent.py`, which defines:
- `run(prompt, **kwargs) -> AgentResponse` — async execution
- `system_prompt` — the agent's persona and capabilities
- Conversation history management

### Current state: no LLM calls

Agents currently perform deterministic data processing (regex, heuristics, statistics) and construct prompts, but **do not call an LLM directly**. This is by design for the MCP path, where the host LLM (Copilot, Claude Desktop) does the reasoning. For the CLI and future web paths, the **LLM gateway** in the application layer handles inference — see [architecture.md](architecture.md#llm-gateway).

## Agent Catalog

| Agent | Module | Purpose |
|---|---|---|
| Filing Analyst | `filing_analyst.py` | Extracts deltas, risk language shifts, capex changes from SEC filings |
| Earnings Interpreter | `earnings_interpreter.py` | Tone analysis, sentiment drift, management confidence scoring from transcripts |
| Macro Regime | `macro_regime.py` | Classifies macro environment (expansion/contraction/transition) from FRED data |
| Quant Signal | `quant_signal.py` | Transforms textual insights into structured, confidence-weighted quant features |
| Thesis Guardian | `thesis_guardian.py` | Monitors investment theses, evaluates assumptions, flags broken conditions |
| Risk Agent | `risk_agent.py` | VaR/CVaR, volatility, scenario stress tests, correlation analysis |
| Adversarial | `adversarial.py` | Systematic thesis challenger — counter-arguments, blind spots, conviction scoring |

## Orchestration

The `Orchestrator` (`agents/src/core/orchestrator.py`) coordinates agents:

- **Agent registry** — register and discover agents by name
- **Task identity** — tasks have explicit `task_id` (falls back to agent name), enabling the same agent to run multiple times in a pipeline
- **Dependency-aware pipeline** — tasks declare dependencies by task ID; independent tasks run in parallel via `asyncio.gather`
- **Priority ordering** — higher-priority tasks execute first within each dependency level
- **Graceful failure** — failed tasks don't crash the pipeline; dependent tasks get error messages
- **Research memos** — aggregate agent outputs into structured memos with sections and source attribution

### Application Services

The application layer (`agents/src/application/services/`) provides typed wrappers:

- **`AgentService`** — maps Pydantic request/response contracts to agent `run()` calls. Validates inputs, normalizes metadata, and caches agent instances.
- **`PipelineService`** — wraps orchestrator with task definitions from typed contracts, optional memo generation.
- **`DigestService`** — wraps research pipeline with typed I/O and formatted output.

## Vector Memory

The `VectorMemory` class (`agents/src/core/memory.py`) provides RAG capabilities:

- ChromaDB-backed semantic search with metadata filtering (ticker, date, doc type)
- Word-boundary-respecting text chunking with configurable overlap
- Deterministic document IDs for deduplication
- Optional dependency — graceful error if chromadb not installed

## MCP Server (Python)

The Python MCP server (`agents/src/mcp_server.py`) exposes agents as tools for any MCP-compatible client (Copilot CLI, Claude Desktop, Cursor, etc.) via stdio transport.

### Running

```bash
cd agents && source .venv/bin/activate
finance-os-mcp          # via console script
python -m src.mcp_server  # direct invocation
```

### Tool Catalog

| Tool | Wraps | Purpose |
|---|---|---|
| `analyze_earnings` | `AgentService.analyze_earnings()` | Earnings transcript analysis — tone, sentiment, guidance |
| `classify_macro` | `AgentService.classify_macro()` | Macro regime classification from FRED data |
| `research_digest` | `DigestService.run_digest()` | Watchlist digest — materiality scoring, alerts |
| `orchestrate` | `PipelineService.run_pipeline()` | Multi-agent pipeline with dependency ordering |

### Design

- **Per-request services** — fresh agent instances per tool call to avoid state leakage
- **Structured responses** — tools return dicts (not JSON strings); MCP protocol handles serialization
- **Server-side config** — secrets (FRED API key) come from `AppConfig`, not tool inputs
- **Agent validation** — `orchestrate` rejects unknown agent names upfront (no silent skip)
- **LLM gateway skipped** — host LLM reasons; agents return structured data

## Research Pipeline

The `ResearchPipeline` (`agents/src/pipelines/research_digest.py`) automates analysis:

- Ingest data sources (EDGAR filings, transcripts, market data)
- Classify materiality based on sentiment thresholds
- Generate alerts with severity levels (HIGH/MEDIUM/LOW)
- Produce research digests with summaries and actionable items
