# Contributing

Thank you for your interest in contributing to finance-os!

## How to Contribute

1. Fork the repository
2. Create a feature branch (`git worktree add ../finance-os-feature -b username/my-feature origin/main`)
3. Make your changes with tests
4. Commit your changes
5. Push to the branch
6. Open a Pull Request

## Guidelines

- TypeScript MCP tools: strict types, async/await, validate inputs
- Python agents: type hints, Google-style docstrings, `decimal.Decimal` for money
- Every change must include tests (positive + negative)
- Never assert on error messages or codes in tests
- Follow existing code style in each component

## Structure

- `mcp-server/` — TypeScript MCP server changes
- `agents/` — Python agent/pipeline changes
- `prompts/` — Prompt template changes

## Reporting Issues

Use the issue templates provided to report bugs or request features.
