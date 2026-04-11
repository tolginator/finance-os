# MCP Tools

## Available Tools

| Tool | Purpose | Status |
|---|---|---|
| echo | Placeholder test tool | ✅ Implemented |
| financial-data | Stock quotes, fundamentals, historical prices | Planned |
| sec-filings | EDGAR 10-K/10-Q/8-K fetch, parse, section extraction | Planned |
| portfolio | Portfolio diagnostics — exposures, drawdowns, concentration | Planned |
| qif | QIF data access — transactions, accounts, categories | Planned |

## Adding a New Tool

1. Create a file in `mcp-server/src/tools/`
2. Export a `registerXxxTool(server: McpServer)` function
3. Call it from `src/index.ts`
4. Add tests in `mcp-server/tests/`
