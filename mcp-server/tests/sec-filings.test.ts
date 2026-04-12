import { describe, it, expect } from "vitest";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { registerSecFilingsTool } from "../src/tools/sec-filings.js";

describe("sec-filings tool", () => {
  it("registers without error", () => {
    const server = new McpServer({ name: "test", version: "0.0.1" });
    expect(() => registerSecFilingsTool(server)).not.toThrow();
  });
});
