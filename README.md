# finance-os

Personal Investment Intelligence OS — a modular, LLM-powered investing AI stack with agent orchestration, domain-tuned prompting, custom MCP tools, and deep integration with quant + NLP pipelines.

Not a chatbot. A **system**. The personal Bloomberg terminal + quant lab + research team.

## Goals

- **Automated research**: Ingest SEC filings, earnings transcripts, and macro data — extract signals, score sentiment, flag material changes
- **Thesis monitoring**: Define investment theses with explicit assumptions — get alerts when assumptions weaken or break
- **Risk analysis**: Scenario modeling, stress tests, tail-risk simulation, concentration analysis
- **Adversarial challenge**: Every thesis gets systematically attacked before capital is deployed
- **Quantitative signals**: Transform unstructured text into structured, timestamped, confidence-weighted quant features
- **Multi-agent orchestration**: Agents collaborate and debate to produce consolidated research memos
- **LLM-native**: Pluggable LLM gateway for direct inference (CLI, future web) or delegate to host LLM (Copilot, Claude Desktop via MCP)

## Project Structure

```
finance-os/
├── mcp-server/          # TypeScript MCP server (data tools for LLMs)
├── agents/              # Python agent framework + application layer
│   └── src/
│       ├── agents/      # Domain agents (filing, earnings, macro, risk, etc.)
│       ├── core/        # BaseAgent, orchestrator, vector memory
│       ├── application/ # Shared contracts, LLM gateway, services (planned)
│       └── pipelines/   # Research digest pipeline
├── prompts/             # Shared prompt library
├── docs/                # Architecture, agent, and tool documentation
└── .github/             # CI, copilot instructions, skills, templates
```

See [docs/architecture.md](docs/architecture.md) for the full system architecture, LLM gateway design, and data flow.
See [docs/agents.md](docs/agents.md) for agent descriptions and the orchestration model.
See [docs/tools.md](docs/tools.md) for MCP tool reference and how to add new tools.

## Getting Started

### Prerequisites

- **Node.js** 22+ and npm
- **Python** 3.12+ with venv

### MCP Server (TypeScript)

```bash
cd mcp-server
npm install
npm run build
npm test
```

### Agents (Python)

```bash
cd agents
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Optional dependencies for quant and RAG features:

```bash
pip install -e ".[quant]"    # numpy, pandas, scipy
pip install -e ".[rag]"      # chromadb
```

### Preflight (run before every push)

From the repo root:

```bash
npm run preflight
```

This mirrors CI exactly: build → test → lint (TypeScript), then ruff → pytest (Python). A push that fails CI is a wasted round-trip.

## Development

### Git Workflow

- Never commit to `main` — use worktrees and feature branches
- Branch naming: `<username>/<MeaningfulDescription>`
- Every PR must have a corresponding issue created first
- Run `npm run preflight` before pushing

### Adding a New MCP Tool

1. Create `mcp-server/src/tools/<name>.ts` exporting `registerXxxTool(server)`
2. Register in `src/index.ts`
3. Add tests in `mcp-server/tests/<name>.test.ts`

### Adding a New Agent

1. Create `agents/src/agents/<name>.py` extending `BaseAgent`
2. Implement `run()` and `system_prompt` property
3. Add tests in `agents/tests/test_<name>.py`

## License

MIT
