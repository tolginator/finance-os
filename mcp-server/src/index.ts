import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { registerEchoTool } from "./tools/echo.js";
import { registerFinancialDataTool } from "./tools/financial-data.js";
import { registerQifTool } from "./tools/qif.js";
import { registerPortfolioTool } from "./tools/portfolio.js";
import { registerSecFilingsTool } from "./tools/sec-filings.js";

const server = new McpServer({
  name: "finance-os",
  version: "0.1.0",
});

registerEchoTool(server);
registerFinancialDataTool(server);
registerQifTool(server);
registerPortfolioTool(server);
registerSecFilingsTool(server);

async function main(): Promise<void> {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("finance-os MCP server running on stdio");
}

main().catch((error: unknown) => {
  console.error("Fatal error:", error);
  process.exit(1);
});
