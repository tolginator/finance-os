import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";

/**
 * Placeholder echo tool — proves the MCP server wiring works.
 * Replace with real financial tools as they are built.
 */
export function registerEchoTool(server: McpServer): void {
  server.tool(
    "echo",
    "Echo back the input message (placeholder tool for testing)",
    { message: z.string().describe("The message to echo back") },
    async ({ message }) => ({
      content: [{ type: "text", text: `Echo: ${message}` }],
    })
  );
}
