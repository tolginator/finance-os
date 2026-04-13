# MCP Tools

## Overview

finance-os has two MCP servers:

1. **TypeScript MCP server** (`mcp-server/`) — data tools that fetch, parse, and compute financial data. These are stateless request handlers callable by any LLM via the Model Context Protocol.

2. **Python MCP server** (`agents/src/mcp_server.py`) — agent tools that expose the Python agent framework to LLMs. Wraps the shared application layer via FastMCP with stdio transport. When a host LLM calls these tools, the LLM gateway is skipped (the host LLM does the reasoning).

Both servers are configured as separate MCP servers in the client (Copilot, Claude Desktop, etc.).

## TypeScript Tool Catalog

| Tool | Module | Purpose | Status |
|---|---|---|---|
| `echo` | `echo.ts` | Test/placeholder tool | ✅ |
| `financial-data` | `financial-data.ts` | Stock quotes and fundamentals via Yahoo Finance | ✅ |
| `sec-filings` | `sec-filings.ts` | SEC EDGAR filing fetch, parse, section extraction | ✅ |
| `portfolio` | `portfolio.ts` | Portfolio diagnostics — exposures, drawdowns, HHI concentration | ✅ |
| `qif` | `qif.ts` | QIF personal finance data — transactions, accounts, categories | ✅ |

## TypeScript Tool Details

### financial-data

Fetches real-time stock quotes from Yahoo Finance (no API key required).

- **Input**: comma-separated ticker symbols
- **Output**: price, volume, P/E, market cap, 52-week range, dividend yield

### sec-filings

Integrates with SEC EDGAR for company filings.

- **Actions**: `list` (browse filings), `fetch` (full text), `section` (extract specific section)
- **Sections**: risk-factors, mda, business, financials, legal
- **Inputs**: ticker or CIK, optional form type filter (10-K, 10-Q, 8-K)

### portfolio

Portfolio-level analysis and diagnostics.

- **Actions**: `exposure` (sector/asset-class breakdown), `drawdown` (max/current from peak), `concentration` (HHI with DIVERSIFIED/MODERATE/CONCENTRATED classification), `summary` (combined metrics)
- **Input**: array of holdings (ticker, shares, cost basis, current price, sector, asset class)

### qif

Queries personal financial data from Quicken Interchange Format files.

- **Actions**: `summary`, `accounts`, `categories`, `transactions`, `investments`
- **Filters**: date range, account, category, limit
- **Parser**: handles banking, investment, and split transactions

## Python Agent Tool Catalog

The Python MCP server exposes agents via the application layer's typed contracts. Run with `finance-os-mcp` or `python -m src.mcp_server` (stdio transport).

| Tool | Contract | Purpose | Status |
|---|---|---|---|
| `analyze_earnings` | `AnalyzeEarningsRequest/Response` | Sentiment, tone, guidance extraction from transcripts | ✅ |
| `classify_macro` | `ClassifyMacroRequest/Response` | Macro regime classification from FRED indicators | ✅ |
| `research_digest` | `RunDigestRequest/Response` | Research digest with alerts and materiality scoring | ✅ |
| `orchestrate` | `RunPipelineRequest/Response` | Multi-agent orchestrated pipeline with memo generation | ✅ |

### Tool details

#### analyze_earnings

Analyzes an earnings call transcript for tone, sentiment, and forward guidance.

- **Input**: `transcript` (required), `ticker` (optional)
- **Output**: `tone`, `net_sentiment`, `confidence`, `guidance_direction`, `guidance_count`, `key_phrase_count`, `content`

#### classify_macro

Classifies the current macroeconomic regime from FRED data.

- **Input**: `indicators` (optional FRED series IDs — uses sensible defaults if omitted)
- **Output**: `regime` (expansion/contraction/transition), `indicators_fetched`, `indicators_with_data`, `content`
- **Note**: FRED API key is read from server-side config, not exposed as a tool input

#### research_digest

Runs a research digest for a watchlist of tickers.

- **Input**: `tickers` (required), `lookback_days` (default 7), `alert_threshold` (default 0.5)
- **Output**: `ticker_count`, `entry_count`, `alert_count`, `material_count`, `content`

#### orchestrate

Runs a multi-agent pipeline with dependency ordering.

- **Input**: `tasks` (required — list of task definitions with `agent_name`, `prompt`, optional `kwargs`, `priority`, `depends_on`, `task_id`), `ticker`, `date`
- **Output**: `results`, `total_duration_ms`, `successful`, `failed`, `memo`
- **Note**: Rejects unknown agent names upfront (no silent skip). Valid agents: `macro_regime`, `filing_analyst`, `earnings_interpreter`, `quant_signal`, `thesis_guardian`, `risk_analyst`, `adversarial`

### LLM Gateway behavior in MCP path

When called via MCP, the host LLM does the reasoning — the LLM gateway is **skipped**. Agents return structured data and the host LLM synthesizes the narrative. This means the Python MCP tools are thin wrappers: validate input → invoke agent service → return structured response.

## Adding a New TypeScript Tool

1. Create `mcp-server/src/tools/<name>.ts`
2. Export a `registerXxxTool(server: McpServer)` function
3. Define input schema with zod
4. Register via `server.tool("name", "description", { schema }, handler)`
5. Import and call from `src/index.ts`
6. Add tests in `mcp-server/tests/<name>.test.ts`
7. Return `{ content: [{ type: "text", text: result }] }` from the handler

## Adding a New Python Agent Tool

1. If the agent exists, add a contract pair in `agents/src/application/contracts/agents.py`
2. Add a service method in `agents/src/application/services/agent_service.py`
3. Add a `@mcp.tool()` function in `agents/src/mcp_server.py`
4. Register the agent in `agents/src/application/registry.py` (if new agent)
5. Add tests in `agents/tests/test_services.py` and `agents/tests/test_mcp_server.py`
