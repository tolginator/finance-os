# Copilot Instructions

## Project Context

**finance-os** is a macro ETF portfolio intelligence system — macroeconomic outlook-driven investment evaluation and goal-driven portfolio rebalancing for a wealthy family ($2M–$10M investable). Monorepo with a TypeScript MCP server, Python agent framework, FastAPI web API, and React frontend.

**Target persona**: Wealthy family that can retire anytime keeping their lifestyle comfortably. Capital preservation + moderate growth. Tax-efficient ETF portfolios. Not average, not ultra-rich.

## Architecture

### MCP Server (`mcp-server/`) — TypeScript
- **Runtime**: Node.js with TypeScript
- **Protocol**: Model Context Protocol via `@modelcontextprotocol/sdk`
- **Build**: `tsc` to `dist/`, ES Modules (`"type": "module"`)
- **Tools**: Each tool in `src/tools/` exports a registration function. Tools are stateless data request handlers.
- **Tests**: Vitest in `tests/`

### Agents (`agents/`) — Python
- **Framework**: Custom agent base classes in `src/core/`
- **LLM Gateway**: Pluggable inference client — supports Azure OpenAI, or skip when host LLM reasons (MCP path)
- **Active Agents**: Macro regime, risk analyst, quant signal (kept from v1). Macro outlook, portfolio evaluator, rebalancer (new, in development).
- **Retiring Agents**: Filing analyst, earnings interpreter, thesis guardian, adversarial (stock-picking focused — being removed after new UI is ready)
- **Application Layer**: `src/application/` — shared contracts (Pydantic), LLM gateway, services. CLI, MCP server, and Web API are thin wrappers.
- **Quant Tools**: `src/tools/` — regression, factor analysis, Monte Carlo, Bayesian updates
- **Data Pipelines**: `src/pipelines/` — FRED, market data, research digest
- **Tests**: pytest in `tests/`

### Data Sources (credible, no social networks)

| Source | Data | Auth |
|--------|------|------|
| FRED (Federal Reserve) | GDP, employment, inflation, rates, spreads, sentiment, production | API key |
| Yahoo Finance (yfinance) | ETF prices, holdings (best-effort), expense ratios, categories | None |
| BLS (Bureau of Labor Statistics) | Detailed CPI components, employment by sector, productivity | API key |
| Treasury.gov | Yield curves, real yields, fiscal data, auction results | None |
| IMF (Data API) | Global GDP forecasts, trade balances, exchange rates | None |
| World Bank (Data API) | Development indicators, global growth | None |

**No social network data. No SEC EDGAR (retiring).**

## LLM Inference Model

Agents perform deterministic data processing and construct prompts but **do not call LLMs directly**. The LLM gateway in the application layer provides inference when needed:

| Path | LLM reasoning | Gateway |
|---|---|---|
| MCP (Copilot, Claude Desktop) | Host LLM reasons | Skipped |
| CLI | LLM gateway calls provider | Used |
| Web API | LLM gateway calls provider | Used |

## Data Flow

```
External APIs (FRED, BLS, Treasury, IMF, World Bank, Yahoo Finance)
        ↓
Data Services (Python) → Provider Abstraction (freshness tracking)
        ↓
Application Layer (contracts + LLM gateway)
        ↓
Agents (Python) — macro outlook, portfolio evaluation, rebalancing
        ↓
Portfolio Intelligence (evaluation, recommendations, stress tests)
```

## Tech Stack

| Layer | Technology |
|---|---|
| MCP Server (data tools) | TypeScript, Node.js, `@modelcontextprotocol/sdk` |
| MCP Server (agents) | Python, `mcp` SDK |
| Application Layer | Python, Pydantic 2.11+, pydantic-settings, azure-identity |
| Agents | Python 3.12+ |
| LLM Gateway | Pluggable — Azure OpenAI, or host LLM via MCP |
| Data Sources | FRED, BLS, Treasury.gov, IMF, World Bank, Yahoo Finance |
| CLI | Python (`finance-os` console script) |
| Web API | Python (`finance-os-api` console script, FastAPI + uvicorn) |
| Web UI | React 19, TypeScript, Vite |
| MCP Server entry | Python (`finance-os-mcp` console script, stdio transport) |
| Copilot Skills | Markdown workflow definitions (`.github/skills/`) |
| Testing | Vitest (TS), pytest (Python) |
| CI/CD | GitHub Actions |

## Asset Class Taxonomy

Two-layer taxonomy for ETF classification:

**Canonical** (for allocation decisions): US Equity, International Developed, Emerging Markets, US Treasuries, IG Corporate Bonds, High Yield, TIPS/Inflation-Linked, Real Assets (REITs/Commodities), Cash/Money Market

**Diagnostic** (for deeper analysis): Large/Small cap, Value/Growth, Sector, Duration buckets, Credit quality, Currency exposure

## Key Design Decisions

1. **Policy-first**: Macro outlook applies bounded tilts around strategic allocation (IPS), never overrides it
2. **Dimensioned evaluation**: No single "health score" — policy drift, concentration, macro alignment, liquidity, tax drag, scenario exposure
3. **Phased rebalancing**: Directional → account-aware → tax-lot (increasing complexity)
4. **Provider abstraction**: All data behind interfaces for future source upgrades; track freshness/confidence
5. **Wealthy family persona**: 3–4% SWR, capital preservation priority, tax-efficiency, multi-generational
6. **No social network data**: Only government, institutional, and market data sources
7. **ETF-level, not stock-level**: All analysis at macro/asset-class/ETF granularity
8. **Decimal precision**: All monetary/financial arithmetic uses `decimal.Decimal`, never `float`

## Code Guidelines

### General
- **ES Modules**: All TypeScript and JavaScript uses ESM (`"type": "module"`)
- **Dependencies**: Minimize. Justify every new dependency.
- **Dependency versions**: Always use the latest stable version. No legacy compatibility — legacy systems must fail. When a dependency ships a breaking change, update all consuming code to work with the new version. Never pin to old versions to avoid migration work. **Legacy compatibility is an anti-pattern.**
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
6. **Tax-lot integrity**: When multiple lots exist per position, never merge or average cost basis. Each lot retains its purchase date and per-share cost.

## Security

Security is not optional. This is financial software handling sensitive portfolio data.

### No Portable Credentials

- **No passwords, secrets, API keys, tokens, or credentials anywhere in the codebase** — not in source files, config files, environment files, comments, tests, documentation, or commit messages.
- **No `.env` files committed to the repository.** Use `.env.example` with placeholder keys only. Actual `.env` files must be in `.gitignore`.
- **No GitHub Secrets for PATs or service credentials.** Use only the built-in `GITHUB_TOKEN` and native GitHub features.
- **No plaintext credential storage.**

### Authentication Standards

- **Prefer credential-free authentication**: OIDC federation, managed identities, workload identity, certificate-based auth.
- **When credentials are unavoidable** (e.g., FRED, BLS API keys): load from environment variables at runtime via `pydantic-settings` (`AppConfig`). Never hardcode, never log, never serialize.

### Defense in Depth

- **All portfolio and personal data stays local.** No PII sent to external APIs unless the user explicitly configures it.
- **Validate all external input** — API responses, file contents, user input. Never trust external data.
- **Log security-relevant events** but **never log credentials or sensitive data**.
- **Fail closed**: if a security check cannot be performed, deny access.

## Testing

### Running Tests

- **MCP Server (unit)**: `cd mcp-server && npm test`
- **Agents (unit)**: `cd agents && source .venv/bin/activate && pytest -m "not integration"`
- **Agents (integration)**: `cd agents && source .venv/bin/activate && pytest -m integration`
- **Full suite (unit)**: `npm test` (from root)
- **Linting**: `npm run lint` (root), `cd agents && ruff check src/ tests/`

### Pre-Push Preflight

**Always run `npm run preflight` from the repo root before pushing.**

```bash
npm run preflight   # must pass before every push
```

### Testing Philosophy

Every code change **must** include tests. No exceptions.

#### Positive Tests
- Cover the happy path for each unit of new or changed functionality
- Use concrete, representative test fixtures

#### Negative Tests
- Every boundary condition and error path must have a negative test
- **Never assert on error codes or error message strings**
- **Assert on observable behavior**: return values, thrown vs not thrown, state changes, output shape

#### Financial Logic Tests
- All monetary calculations must be tested with `Decimal` precision
- Tax-lot selection logic must have edge-case coverage (wash sales, zero-basis lots, same-day trades)
- Rebalancing math must verify current→target drift calculations
- Scenario stress tests must verify arithmetic against known expected losses

#### Test Anti-Patterns

| Anti-pattern | Why it's bad |
|---|---|
| Tautology (`assert True`) | Tests nothing |
| Language validation (constructor/property tests) | Tests that the language works, not your code |
| Mirror (reimplements production logic) | Breaks when logic changes |
| Duplicate (same behavior twice) | Noise; keep the more expressive one |
| Error-code/message matching | Couples to internals |

## Communication Style

- Be concise and succinct, use as few words as possible. Words are at a premium.
- Do not generate summaries in chat output.

## Git Workflow: Worktrees and Branches

Multiple Copilot CLI sessions may work simultaneously. Always use git worktrees.

### Branch Naming

All branches other than `main` **must** follow: `<username>/<MeaningfulDescription>`

### Making Changes

0. **Never commit to main.**
1. `git worktree add <path> -b <username>/<task> origin/main`
2. Work exclusively in the worktree.
3. Make **separate, descriptive commits** for each logical change within a PR.
4. Do **not** amend or force-push.
5. Run `npm run preflight` before pushing.
6. Commit, push, create PR targeting `main`.
7. **Squash merge** when merging PRs into main.

### After PR Merge

1. `git fetch origin --prune && git pull origin main`
2. `git worktree remove <path>`
3. `git branch -d <branch> && git push origin --delete <branch>`
4. `git worktree prune`

## Issues and Pull Requests

### Issue-First Workflow

**Every PR must have a corresponding issue created before the PR.** No exceptions.

1. Before starting work, create an issue describing what will be built.
2. For multi-step features, use **parent issue + sub-issues**.
3. Every PR body must reference its issue(s) via closing keywords (`Closes #N`).

### Pull Requests

- Use `gh pr create --title "..." --body "Closes #N"`.
- **Assign every PR to the "finance-os" GitHub Project** (if one exists).
- **After every push**, wait a few minutes for CI and Copilot code review feedback on the remote. Read all review comments, assess validity, address valid findings with a new commit, push, and resolve the conversations. Repeat this loop until there is no more unresolved feedback.

## @azure Rule

When generating code for Azure, invoke `azure_development-get_best_practices` tool if available.
