# Architecture

See the [README](../README.md) for the high-level architecture diagram.

## Component Details

### MCP Server

The MCP server exposes investment tools to LLMs via the Model Context Protocol. Each tool is a stateless request handler that validates inputs and returns structured responses.

### Agents

Domain-tuned Python agents that can be orchestrated to collaborate or debate. Each agent has a specialized system prompt, access to specific tools, and a reasoning strategy.

### Prompt Library

Shared prompt templates organized by strategy type. These are used by agents and can be composed for complex multi-step analyses.

## Data Flow

1. **Data Pipelines** ingest from external sources (EDGAR, FRED, Yahoo Finance) into local storage
2. **MCP Tools** provide structured access to this data for LLMs
3. **Agents** orchestrate multi-step reasoning using tools and prompts
4. **Output** is research memos, alerts, signals, or portfolio diagnostics
