import { describe, it, expect } from "vitest";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { registerEchoTool } from "../src/tools/echo.js";

describe("echo tool", () => {
  it("registers without error", () => {
    const server = new McpServer({ name: "test", version: "0.0.1" });
    expect(() => registerEchoTool(server)).not.toThrow();
  });
});
