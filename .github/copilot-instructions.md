# Copilot Instructions

## Project Context

**finance-os** is a modular, LLM-powered personal investing AI stack — agent orchestration, domain-tuned prompting, custom MCP tools, and deep integration with quant + NLP pipelines. It is a monorepo with a TypeScript MCP server and Python agent framework.

## Architecture

### MCP Server (`mcp-server/`) — TypeScript
- **Runtime**: Node.js with TypeScript
- **Protocol**: Model Context Protocol via `@modelcontextprotocol/sdk`
- **Build**: `tsc` to `dist/`, ES Modules (`"type": "module"`)
- **Tools**: Each tool in `src/tools/` exports a registration function. Tools are stateless request handlers.
- **Resources**: `src/resources/` for MCP resource providers
- **Prompts**: `src/prompts/` for MCP prompt templates
- **Tests**: Vitest in `tests/`

### Agents (`agents/`) — Python
- **Framework**: Custom agent base classes in `src/core/`
- **LLM Abstraction**: Supports Claude (Anthropic) and OpenAI APIs, configurable per agent
- **Domain Agents**: `src/agents/` — filing analyst, earnings interpreter, macro regime, quant signal, thesis guardian, risk, adversarial
- **Quant Tools**: `src/tools/` — regression, factor analysis, Monte Carlo, Bayesian updates
- **Data Pipelines**: `src/pipelines/` — EDGAR, FRED, market data, research digest
- **Tests**: pytest in `tests/`

### Prompt Library (`prompts/`) — Shared
- `roles/` — role-stacking persona prompts
- `analysis/` — analytical prompt templates
- `adversarial/` — thesis-challenging prompts
- `synthesis/` — multi-document synthesis

## Data Flow

```
External APIs (EDGAR, FRED, Yahoo Finance)
        ↓
Data Pipelines (Python) → Local Data Store
        ↓
MCP Tools (TypeScript) ← LLM requests via MCP protocol
        ↓
Agents (Python) — orchestrated multi-agent reasoning
        ↓
Research Output (memos, alerts, signals)
```

## Tech Stack

| Layer | Technology |
|---|---|
| MCP Server | TypeScript, Node.js, `@modelcontextprotocol/sdk` |
| Agents | Python 3.11+, NumPy, pandas, scipy |
| Vector DB | ChromaDB (local, v0) |
| LLM Backend | Claude / GPT-4 / open models (configurable) |
| Data Sources | SEC EDGAR (free), FRED (free), Yahoo Finance (yfinance), QIF files |
| Testing | Vitest (TS), pytest (Python) |
| CI/CD | GitHub Actions |

## Code Guidelines

### General
- **ES Modules**: All TypeScript and JavaScript uses ESM (`"type": "module"`)
- **Dependencies**: Minimize. Justify every new dependency.
- **Dependency versions**: Always use the latest stable version. No legacy compatibility — legacy systems must fail. When a dependency ships a breaking change, update all consuming code to work with the new version. Never pin to old versions to avoid migration work.
- **No secrets**: Do not store PATs or secrets in GitHub Secrets. Use only the built-in `GITHUB_TOKEN` and native GitHub features (e.g., Project auto-add workflows).
- **Error handling**: Graceful degradation. Never crash on malformed input — log warnings and continue.
- **Privacy**: All portfolio/personal data stays local. No PII sent to external APIs unless explicitly configured.

### TypeScript (MCP Server)
- Strict TypeScript (`"strict": true`)
- Use `interface` over `type` for object shapes
- Async/await everywhere, no raw promises
- Each MCP tool is a self-contained module in `src/tools/`
- Tool implementations must validate all inputs and return structured error responses

### Python (Agents)
- Python 3.11+ with type hints everywhere
- PEP 8, `snake_case` for functions/variables, `PascalCase` for classes
- Docstrings on all public functions and classes (Google style)
- Use `pathlib.Path` over `os.path`
- All monetary/financial arithmetic uses `decimal.Decimal`, never `float`
- `#!/usr/bin/env python3` shebang on executable scripts

### Financial Accuracy Rules

These rules exist because this is financial software. Violations produce incorrect dollar amounts.

1. **All monetary arithmetic** uses `decimal.Decimal` (Python) or a decimal library (TypeScript). Never use floating point for money.
2. **Net flow, not gross**: Income shows `income - expense` per category; expense shows `expense - income`.
3. **Data source attribution**: Every data point must trace to its source (API, filing, calculation).
4. **Timestamp everything**: All market data, signals, and analysis must carry timestamps.
5. **No stale data assumptions**: Always check data freshness before analysis.

## Testing

### Running Tests

- **MCP Server**: `cd mcp-server && npm test`
- **Agents**: `cd agents && pytest`
- **Full suite**: `npm test` (from root, runs workspace tests)
- **Python type checking**: `cd agents && mypy src/`
- **Linting**: `npm run lint` (root), `cd agents && ruff check src/`

### Testing Philosophy

Every code change **must** include tests. No exceptions.

#### Positive Tests
- Cover the happy path for each unit of new or changed functionality
- Use concrete, representative test fixtures (not randomly generated data)

#### Negative Tests
- Every boundary condition and error path must have a negative test
- **Never assert on error codes or error message strings** — they couple tests to internals
- **Assert on observable behavior**: return values, thrown vs not thrown, state changes, output shape

```python
# ❌ BAD
assert err.code == "ERR_PARSE_DATE"

# ✅ GOOD
assert len(result.transactions) == 0
# parser should not raise on malformed input
result = parse(malformed)
assert result is not None
```

```typescript
// ❌ BAD
expect(err.code).toBe('ERR_INVALID_TICKER');

// ✅ GOOD
expect(result.quotes).toHaveLength(0);
expect(() => fetchQuote(invalidTicker)).not.toThrow();
```

#### Test Anti-Patterns

| Anti-pattern | Why it's bad |
|---|---|
| Tautology (`assert True`) | Tests nothing |
| Mirror (reimplements production logic) | Breaks when logic changes |
| Duplicate (same behavior twice) | Noise; keep the more expressive one |
| Subsumed (A ⊂ B) | Keep B, remove A |
| Error-code/message matching | Couples to internals |

#### Test Pruning

After completing a feature: remove tautologies, mirrors, duplicates, subsumed tests. Verify negative coverage. Verify no error-code or message-string assertions remain.

## Communication Style

- Be concise and succinct, use as few words as possible. Words are at a premium.
- Do not generate summaries in chat output.

## Git Workflow: Worktrees and Branches

Multiple Copilot CLI sessions may work simultaneously. Always use git worktrees.

### Branch Naming

All branches other than `main` **must** follow: `<username>/<MeaningfulDescription>`

Examples: `tolginator/AddEdgarPipeline`, `copilot/RefactorAgentFramework`

### Making Changes

0. **Never commit to main.** Main is only for PRs and production builds.
1. `git worktree add <path> -b <username>/<task> origin/main`
2. Work exclusively in the worktree.
3. Commit, push, create PR targeting `main`.

### After PR Merge

1. `git fetch origin --prune && git pull origin main`
2. `git worktree remove <path>`
3. `git branch -d <branch> && git push origin --delete <branch>`
4. `git worktree prune`

## Issues and Pull Requests

### Issue Structure

Use **parent issue + sub-issues** for multi-step features:

1. Create parent issue with goals, architecture, progress checklist.
2. Create sub-issues referencing the parent (e.g., "Part of #1").
3. Update parent checklist to link sub-issues.
4. Close sub-issues as merged; close parent when all complete.

### Pull Requests

- Every PR links to issues via closing keywords (`Closes #N`) or references (`Part of #N`).
- Use `gh pr create --title "..." --body "Closes #N"`.
- **Assign every PR to the "finance-os" GitHub Project** (if one exists). If token lacks `read:project` scope, inform the user to assign manually.

## Repository Structure

```
finance-os/
├── package.json                    # Root workspace config
├── .github/
│   ├── copilot-instructions.md     # This file
│   ├── workflows/                  # CI/CD
│   ├── ISSUE_TEMPLATE/             # Issue templates
│   ├── acl/                        # CODEOWNERS, access
│   ├── policies/                   # JIT access policies
│   └── prompts/                    # Default Copilot prompt
├── mcp-server/                     # TypeScript MCP server
│   ├── package.json
│   ├── tsconfig.json
│   ├── src/
│   │   ├── index.ts                # MCP server entry
│   │   ├── tools/                  # MCP tool implementations
│   │   ├── resources/              # MCP resource providers
│   │   └── prompts/                # MCP prompt templates
│   └── tests/
├── agents/                         # Python agent framework
│   ├── pyproject.toml
│   ├── src/
│   │   ├── core/                   # Agent base, orchestrator, memory
│   │   ├── agents/                 # Domain-specific agents
│   │   ├── tools/                  # Quant tools
│   │   └── pipelines/             # Data ingestion pipelines
│   └── tests/
├── prompts/                        # Shared prompt library
│   ├── roles/                      # Role-stacking personas
│   ├── analysis/                   # Analytical templates
│   ├── adversarial/                # Thesis-challenging
│   └── synthesis/                  # Multi-document synthesis
├── data/                           # Local data store (gitignored)
└── docs/                           # Documentation
```

## @azure Rule

When generating code for Azure, invoke `azure_development-get_best_practices` tool if available.
