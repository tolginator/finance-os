# Copilot Instructions

## Project Context

**finance-os** is a modular, LLM-powered personal investing AI stack — agent orchestration, domain-tuned prompting, custom MCP tools, and deep integration with quant + NLP pipelines. It is a monorepo with a TypeScript MCP server and Python agent framework.

## Architecture

### MCP Server (`mcp-server/`) — TypeScript
- **Runtime**: Node.js with TypeScript
- **Protocol**: Model Context Protocol via `@modelcontextprotocol/sdk`
- **Build**: `tsc` to `dist/`, ES Modules (`"type": "module"`)
- **Tools**: Each tool in `src/tools/` exports a registration function. Tools are stateless data request handlers.
- **Resources**: `src/resources/` for MCP resource providers
- **Prompts**: `src/prompts/` for MCP prompt templates
- **Tests**: Vitest in `tests/`

### Agents (`agents/`) — Python
- **Framework**: Custom agent base classes in `src/core/`
- **LLM Gateway**: Pluggable inference client in the application layer — supports OpenAI, Anthropic, ollama, or skip when host LLM reasons (MCP path)
- **Domain Agents**: `src/agents/` — filing analyst, earnings interpreter, macro regime, quant signal, thesis guardian, risk, adversarial
- **Application Layer**: `src/application/` — shared contracts (Pydantic), LLM gateway, services. CLI, MCP server, and Web API are thin wrappers over this.
- **Quant Tools**: `src/tools/` — regression, factor analysis, Monte Carlo, Bayesian updates
- **Data Pipelines**: `src/pipelines/` — EDGAR, FRED, market data, research digest
- **Tests**: pytest in `tests/`

### Prompt Library (`prompts/`) — Shared
- `roles/` — role-stacking persona prompts
- `analysis/` — analytical prompt templates
- `adversarial/` — thesis-challenging prompts
- `synthesis/` — multi-document synthesis

## LLM Inference Model

Agents perform deterministic data processing and construct prompts but **do not call LLMs directly**. The LLM gateway in the application layer provides inference when needed:

| Path | LLM reasoning | Gateway |
|---|---|---|
| MCP (Copilot, Claude Desktop) | Host LLM reasons | Skipped |
| CLI | LLM gateway calls provider | Used |
| Web API | LLM gateway calls provider | Used |

## Data Flow

```
External APIs (EDGAR, FRED, Yahoo Finance)
        ↓
Data Pipelines (Python) → Local Data Store
        ↓
MCP Tools (TypeScript) ← LLM requests via MCP protocol
        ↓
Application Layer (contracts + LLM gateway)
        ↓
Agents (Python) — orchestrated multi-agent reasoning
        ↓
Research Output (memos, alerts, signals)
```

## Tech Stack

| Layer | Technology |
|---|---|
| MCP Server (data tools) | TypeScript, Node.js, `@modelcontextprotocol/sdk` |
| MCP Server (agents) | Python, `mcp` SDK |
| Application Layer | Python, Pydantic 2.11+, pydantic-settings, azure-identity |
| Agents | Python 3.12+, NumPy, pandas, scipy |
| Vector DB | ChromaDB (local) |
| LLM Gateway | Pluggable — OpenAI, Anthropic, ollama, or host LLM via MCP |
| Data Sources | SEC EDGAR (free), FRED (free), Yahoo Finance (yfinance), QIF files |
| CLI | Python (`finance-os` console script) |
| Web API | Python (`finance-os-api` console script, FastAPI + uvicorn) |
| Web UI | React 19, TypeScript, Vite |
| MCP Server entry | Python (`finance-os-mcp` console script, stdio transport) |
| Copilot Skills | Markdown workflow definitions (`.github/skills/`) |
| Testing | Vitest (TS), pytest (Python) |
| CI/CD | GitHub Actions |

## Code Guidelines

### General
- **ES Modules**: All TypeScript and JavaScript uses ESM (`"type": "module"`)
- **Dependencies**: Minimize. Justify every new dependency.
- **Dependency versions**: Always use the latest stable version. No legacy compatibility — legacy systems must fail. When a dependency ships a breaking change, update all consuming code to work with the new version. Never pin to old versions to avoid migration work. **Legacy compatibility is an anti-pattern** — do not use compatibility shims, polyfills, or `__future__` imports that exist only to support older versions.
- **No secrets**: See [Security](#security) section below.
- **Error handling**: Graceful degradation. Never crash on malformed input — log warnings and continue.
- **Privacy**: All portfolio/personal data stays local. No PII sent to external APIs unless explicitly configured.

### TypeScript (MCP Server)
- Strict TypeScript (`"strict": true`)
- Use `interface` over `type` for object shapes
- Async/await everywhere, no raw promises
- Each MCP tool is a self-contained module in `src/tools/`
- Tool implementations must validate all inputs and return structured error responses

### Python (Agents)
- Python 3.12+ with type hints everywhere (use native `X | Y`, `list[str]`, etc. — no `from __future__ import annotations`)
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

## Security

Security is not optional. This is financial software handling sensitive portfolio data.

### No Portable Credentials

- **No passwords, secrets, API keys, tokens, or credentials anywhere in the codebase** — not in source files, config files, environment files, comments, tests, documentation, or commit messages.
- **No `.env` files committed to the repository.** Use `.env.example` with placeholder keys only (e.g., `FRED_API_KEY=your-key-here`). Actual `.env` files must be in `.gitignore`.
- **No GitHub Secrets for PATs or service credentials.** Use only the built-in `GITHUB_TOKEN` and native GitHub features (e.g., OIDC federation for cloud access).
- **No plaintext credential storage** — not in config files, databases, local files, or environment variable dumps.

### Authentication Standards

- **Prefer credential-free authentication**: OIDC federation, managed identities, workload identity, certificate-based auth.
- **When credentials are unavoidable** (e.g., third-party API keys like FRED): load from environment variables at runtime via `pydantic-settings` (`AppConfig`). Never hardcode, never log, never serialize.
- **Reject systems that only support username/password auth** unless they also offer SSO, OIDC, or certificate-based alternatives. Portable credentials are a liability.

### Defense in Depth

- **All portfolio and personal data stays local.** No PII sent to external APIs unless the user explicitly configures it.
- **Validate all external input** — API responses, file contents, user input. Never trust external data.
- **Log security-relevant events** (auth failures, config errors) but **never log credentials or sensitive data**.
- **Fail closed**: if a security check cannot be performed (missing credentials, unreachable auth provider), deny access rather than falling back to insecure defaults.

## Testing

### Running Tests

- **MCP Server (unit)**: `cd mcp-server && npm test`
- **MCP Server (integration)**: `cd mcp-server && npm run test:integration`
- **Agents (unit)**: `cd agents && source .venv/bin/activate && pytest -m "not integration"`
- **Agents (integration)**: `cd agents && source .venv/bin/activate && pytest -m integration`
- **Full suite (unit)**: `npm test` (from root, runs workspace tests)
- **Python type checking**: `cd agents && source .venv/bin/activate && mypy src/`
- **Linting**: `npm run lint` (root), `cd agents && source .venv/bin/activate && ruff check src/ tests/`

> **Note**: Python requires a virtual environment. Set up once: `cd agents && python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`

### Unit vs Integration Tests

Tests are split into **unit** (fast, no external deps) and **integration** (calls external APIs):

| | Python | TypeScript |
|---|---|---|
| Unit files | `tests/*.py` | `tests/*.test.ts` |
| Integration files | `tests/*.py` with `@pytest.mark.integration` | `tests/*.integration.test.ts` |
| Run unit | `pytest -m "not integration"` | `npm test` |
| Run integration | `pytest -m integration` | `npm run test:integration` |

**Rules:**
- Mark any test that calls an external service (FRED, EDGAR, etc.) with `@pytest.mark.integration` (Python) or place it in a `*.integration.test.ts` file (TypeScript).
- Integration tests must **skip gracefully** when credentials are missing (use the `fred_api_key` fixture or similar).
- CI runs unit tests on every PR. Integration tests run only on pushes to `main`.
- `npm run preflight` runs unit tests only.

### Pre-Push Preflight

**Always run `npm run preflight` from the repo root before pushing.** This mirrors CI: build → unit test → lint (TypeScript), then ruff → unit pytest (Python). A push that fails CI is a wasted round-trip. Fix locally first.

```bash
npm run preflight   # must pass before every push
```

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
| Language validation (constructor/property tests) | Tests that the language works, not that your code works. `expect(new Foo(1).x).toBe(1)` is a tautology — the language guarantees this. |
| Mirror (reimplements production logic) | Breaks when logic changes |
| Duplicate (same behavior twice) | Noise; keep the more expressive one |
| Subsumed (A ⊂ B) | A is already covered by B. Keep B, remove A |
| Error-code/message matching | Couples to internals |

**Every test must validate behavior the code implements, not behavior the language guarantees.** If a test would pass with an empty implementation, it's not testing anything. If the same behavior is already asserted in another test, don't assert it again.

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
3. Make **separate, descriptive commits** for each logical change within a PR.
4. Do **not** amend or force-push — keep the commit history intact for review.
5. Run `npm run preflight` — fix any failures before pushing.
6. Commit, push, create PR targeting `main`.
7. **Squash merge** when merging PRs into main (`gh pr merge --squash`).

### After PR Merge

1. `git fetch origin --prune && git pull origin main`
2. `git worktree remove <path>`
3. `git branch -d <branch> && git push origin --delete <branch>`
4. `git worktree prune`

## Issues and Pull Requests

### Issue-First Workflow

**Every PR must have a corresponding issue created before the PR.** No exceptions. Issues are the unit of work; PRs are the delivery mechanism.

1. Before starting work, create an issue describing what will be built.
2. For multi-step features, use **parent issue + sub-issues**:
   - Create parent issue with goals, architecture, progress checklist.
   - Create sub-issues referencing the parent (e.g., "Part of #1").
   - Update parent checklist to link sub-issues.
   - Close sub-issues as merged; close parent when all complete.
3. Every PR body must reference its issue(s) via closing keywords (`Closes #N`) or references (`Part of #N`).

### Pull Requests

- Use `gh pr create --title "..." --body "Closes #N"`.
- **Assign every PR to the "finance-os" GitHub Project** (if one exists). If token lacks `read:project` scope, inform the user to assign manually.

## Repository Structure

```
finance-os/
├── package.json                    # Root workspace config
├── .github/
│   ├── copilot-instructions.md     # This file
│   ├── skills/                     # Copilot Skills (SKILL.md workflows)
│   │   ├── earnings-analysis/      # Earnings transcript analysis
│   │   ├── thesis-evaluation/      # Thesis challenge + conviction scoring
│   │   ├── research-digest/        # Watchlist digest + pipeline
│   │   ├── risk-assessment/        # Portfolio risk + stress tests
│   │   └── macro-overview/         # Macro regime classification
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
│   │   ├── application/            # Shared contracts, LLM gateway, services, registry
│   │   ├── cli/                    # CLI entry points (finance-os command)
│   │   ├── mcp_server.py           # Python MCP server (finance-os-mcp command)
│   │   ├── web_api.py              # FastAPI web server (finance-os-api command)
│   │   ├── tools/                  # Quant tools
│   │   └── pipelines/             # Data ingestion pipelines
│   └── tests/
├── web-ui/                         # React frontend (Vite + TypeScript)
│   ├── src/
│   │   ├── App.tsx                  # Root component
│   │   ├── api.ts                   # API client for Web API
│   │   └── components/              # UI components
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
