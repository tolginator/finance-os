# MCP Tools

## Overview

finance-os has two MCP servers:

1. **TypeScript MCP server** (`mcp-server/`) — data tools that fetch, parse, and compute financial data. These are stateless request handlers callable by any LLM via the Model Context Protocol.

2. **Python MCP server** (planned, `agents/src/mcp_server.py`) — agent tools that expose the Python agent framework to LLMs. Wraps the shared application layer. When a host LLM calls these tools, the LLM gateway is skipped (the host LLM does the reasoning).

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

## Python Agent Tool Catalog (planned)

The Python MCP server will expose agents via the application layer's typed contracts. Each tool maps to a Pydantic request/response pair in `agents/src/application/contracts/agents.py`.

| Tool | Contract | Purpose | Status |
|---|---|---|---|
| `analyze-earnings` | `AnalyzeEarningsRequest/Response` | Sentiment, tone, guidance extraction from transcripts | Planned |
| `classify-macro` | `ClassifyMacroRequest/Response` | Macro regime classification from FRED indicators | Planned |
| `search-filings` | `SearchFilingsRequest/Response` | SEC EDGAR filing search and listing | Planned |
| `generate-signals` | `GenerateSignalsRequest/Response` | Composite quant signal scoring | Planned |
| `evaluate-thesis` | `EvaluateThesisRequest/Response` | Thesis assumption evaluation against observed data | Planned |
| `assess-risk` | `AssessRiskRequest/Response` | VaR/CVaR, scenarios, stress tests | Planned |
| `challenge-thesis` | `ChallengeThesisRequest/Response` | Adversarial counter-arguments, blind spots, conviction | Planned |
| `run-pipeline` | `RunPipelineRequest/Response` | Multi-agent orchestrated pipeline with memo generation | Planned |
| `run-digest` | `RunDigestRequest/Response` | Research digest with alerts and materiality scoring | Planned |

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
3. Register the tool in `agents/src/mcp_server.py` (when Python MCP server exists)
4. Add tests in `agents/tests/test_services.py` and `agents/tests/test_mcp_server.py`
