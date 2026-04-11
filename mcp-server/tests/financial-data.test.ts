import { describe, it, expect } from "vitest";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { registerFinancialDataTool } from "../src/tools/financial-data.js";

describe("financial-data tool", () => {
  it("registers without error", () => {
    const server = new McpServer({ name: "test", version: "0.0.1" });
    expect(() => registerFinancialDataTool(server)).not.toThrow();
  });
});
