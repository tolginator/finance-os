# Copilot Instructions

## Response Rules

- Be concise. Minimize chat output.
- Do not generate summaries.

## Critical Invariants

These override all other rules. Verify compliance before every commit.

1. **Never commit secrets** — no passwords, API keys, tokens, or credentials anywhere in the codebase.
2. **Use `decimal.Decimal` for all monetary arithmetic** — never `float` for money.
3. **Every code change must include tests.**
4. **Never commit to `main`** — use worktrees and branches.
5. **Run `npm run preflight` before every push.**
6. **Use `datetime.now(UTC)` from `datetime`** — never `datetime.utcnow()` (deprecated).

## Project Context

**finance-os** — macro ETF portfolio intelligence system. Macroeconomic outlook-driven investment evaluation and goal-driven portfolio rebalancing for a wealthy family ($2M–$10M investable). Monorepo: TypeScript MCP server, Python agent framework, FastAPI web API, React frontend.

**Persona**: Wealthy family, capital preservation + moderate growth, 3–4% SWR, tax-efficient ETF portfolios, multi-generational.

## Architecture

### MCP Server (`mcp-server/`) — TypeScript
- **Runtime**: Node.js with TypeScript
- **Protocol**: Model Context Protocol via `@modelcontextprotocol/sdk`
- **Build**: `tsc` to `dist/`, ES Modules (`"type": "module"`)
- **Tools**: Each tool in `src/tools/` exports a registration function. Tools are stateless data request handlers.
- **Tests**: Vitest in `tests/`

### Agents (`agents/`) — Python
- **Framework**: Custom agent base classes in `src/core/`
- **LLM Gateway**: Pluggable inference client — Azure OpenAI, or skipped when host LLM reasons (MCP path)
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

Agents do deterministic data processing and prompt construction — they do not call LLMs directly.

| Path | LLM reasoning | Gateway |
|---|---|---|
| MCP (Copilot, Claude Desktop) | Host LLM reasons | Skipped |
| CLI / Web API | LLM gateway calls provider | Used |

## Tech Stack

| Layer | Technology |
|---|---|
| MCP Server (data tools) | TypeScript, Node.js, `@modelcontextprotocol/sdk` |
| MCP Server (agents) | Python, `mcp` SDK |
| Application Layer | Python, Pydantic 2.11+, pydantic-settings, azure-identity |
| Agents | Python 3.12+ |
| LLM Gateway | Pluggable — Azure OpenAI, or host LLM via MCP |
| CLI | Python (`finance-os` console script) |
| Web API | FastAPI + uvicorn (`finance-os-api` console script) |
| Web UI | React 19, TypeScript, Vite |
| Testing | Vitest (TS), pytest (Python) |
| CI/CD | GitHub Actions |

## Asset Class Taxonomy

Two-layer taxonomy for ETF classification:

**Canonical** (for allocation decisions): US Equity, International Developed, Emerging Markets, US Treasuries, IG Corporate Bonds, High Yield, TIPS/Inflation-Linked, Real Assets (REITs/Commodities), Cash/Money Market

**Diagnostic** (for deeper analysis): Large/Small cap, Value/Growth, Sector, Duration buckets, Credit quality, Currency exposure

## Key Design Decisions

1. **Policy-first**: Macro outlook applies bounded tilts around strategic allocation (IPS), never overrides it.
2. **Dimensioned evaluation**: No single "health score" — separate dimensions for drift, concentration, macro alignment, liquidity, tax drag, scenario exposure.
3. **Phased rebalancing**: Directional → account-aware → tax-lot (increasing complexity).
4. **Provider abstraction**: All data behind interfaces; track freshness/confidence.
5. **No social network data**: Only government, institutional, and market data sources.
6. **ETF-level, not stock-level**: All analysis at macro/asset-class/ETF granularity.

## Code Guidelines

### General
- Use ES Modules everywhere (`"type": "module"`).
- Minimize dependencies. Justify every new one.
- Always use the latest stable version of dependencies. Never pin old versions to avoid migration. Update consuming code on breaking changes.
- Graceful degradation on malformed input — log warnings and continue, never crash.

### TypeScript (MCP Server)
- Strict mode (`"strict": true`). Use `interface` over `type` for object shapes.
- Async/await everywhere. No raw promises.
- Each MCP tool is a self-contained module in `src/tools/`. Validate all inputs; return structured error responses.

### Python (Agents)
- Python 3.12+ with type hints everywhere. Use native `X | Y`, `list[str]` — no `from __future__ import annotations`.
- PEP 8: `snake_case` for functions/variables, `PascalCase` for classes.
- Google-style docstrings on all public functions and classes.
- Use `pathlib.Path` over `os.path`.

### Financial Accuracy Rules

1. **Net flow, not gross**: Income shows `income - expense` per category; expense shows `expense - income`.
2. **Data source attribution**: Every data point must trace to its source (API, filing, calculation).
3. **Timestamp everything**: All market data, signals, and analysis must carry timestamps.
4. **No stale data**: Always check data freshness before analysis.
5. **Tax-lot integrity**: Never merge or average cost basis across lots. Each lot retains its purchase date and per-share cost.

## Defensive Coding Checklist

### Quick Decision Table

| Situation | Do this |
|---|---|
| Money/weights/amounts | `decimal.Decimal`, never `float` |
| PATCH update | `model_fields_set` to detect explicit `None` vs absent |
| Optional dict/list missing entries | Merge with defaults in `@model_validator` |
| After `model_copy(update=...)` | Re-validate: `Model.model_validate(obj.model_dump())`, use the returned object |
| Enum in error message | `enum_value.value`, not the enum member |
| Writing persistent files | Atomic write pattern (see Safe File I/O) |
| Mtime-based cache read | Return `model_copy(deep=True)` to prevent mutation leaking |

### Pydantic Model Discipline

1. **String fields**: Add `Field(min_length=1)` + `@field_validator` that strips whitespace and rejects blank.
2. **Numeric bounds**: Validate domain range on every constrained numeric field (e.g., weights in `[0, 1]`).
3. **Request models mirror entity invariants**: If `Goal` validates goal-type invariants, `CreateGoalRequest` must too. Reject invalid input at the API boundary.
4. **Optional collections**: Populate missing entries with defaults in `@model_validator`. A partial dict must be merged with defaults, not left incomplete.
5. **Nullability**: If a field can be `None` at runtime (including via `model_construct`), annotate as `| None`.
6. **`model_copy` bypasses validators** — always re-validate afterward and use the returned object.
7. **PATCH semantics**: Use `model_fields_set` to distinguish "explicitly set to None" from "not provided". Never use `if value is not None`.
8. **Enum in error messages**: Use `.value` so clients see `"wealth_building"` not `"GoalType.WEALTH_BUILDING"`.

### Safe File I/O Pattern

Atomic write pattern for services with persistent state:

1. Use `os.fdopen` (not raw `os.write`) — `os.write` can short-write, silently truncating data.
2. Catch `BaseException` (not `Exception`) in fd/lock cleanup — `KeyboardInterrupt` leaks fds otherwise.
3. Use `st_mtime_ns` (int) for mtime caching — `st_mtime` (float) equality is unreliable across filesystems.
4. Return deep copies from mtime caches — prevents mutation/disk divergence if `_write_atomic` fails after cache update.
5. Use `0o600` permissions for sensitive files. Best-effort `fsync` on parent directory.

Reference: `PolicyService._write_atomic()`, `OverrideStore._save()`.

### Docstrings and PR Descriptions

- Docstrings must match behavior exactly. If a method raises on not-found, do not document "returns False".
- PR descriptions must match the code being shipped. Do not claim unimplemented features.

## Security

### No Portable Credentials

- No passwords, secrets, API keys, tokens, or credentials anywhere in the codebase — not in source, config, env files, comments, tests, docs, or commits.
- No `.env` files committed. Use `.env.example` with placeholders only.
- No GitHub Secrets for PATs or service credentials. Use only `GITHUB_TOKEN`.

### Authentication

- Prefer credential-free: OIDC federation, managed identities, workload identity, certificate-based auth.
- When credentials are unavoidable (FRED, BLS API keys): load from environment variables at runtime via `pydantic-settings` (`AppConfig`). Never hardcode, log, or serialize.

### Defense in Depth

- All portfolio and personal data stays local. No PII sent to external APIs unless explicitly configured.
- Validate all external input (API responses, file contents, user input).
- Log security-relevant events but never log credentials or sensitive data.
- Fail closed: if a security check cannot be performed, deny access.

## Testing

### Commands

| Scope | Command |
|---|---|
| MCP Server (unit) | `cd mcp-server && npm test` |
| Agents (unit) | `cd agents && source .venv/bin/activate && pytest -m "not integration"` |
| Agents (integration) | `cd agents && source .venv/bin/activate && pytest -m integration` |
| Full suite | `npm test` (from root) |
| Lint | `npm run lint` (root) |
| **Preflight (pre-push)** | **`npm run preflight`** (from root) |

### Test Requirements

- Every code change must include tests.
- Cover the happy path with concrete, representative fixtures.
- Every boundary condition and error path must have a negative test.
- Assert on observable behavior (return values, exceptions, state changes), not error message strings.
- All monetary calculations tested with `Decimal` precision.

### Anti-Patterns

| Avoid | Do instead |
|---|---|
| `assert True`, `pass` (placeholder) | Use `model_construct` to bypass outer validation and test the guard directly |
| Testing language features (constructor/property) | Test your logic, not that Python works |
| Mirror test (reimplements production logic) | Use independent expected values |
| Duplicate test (same behavior twice) | Keep the more expressive one |
| `>= expected` when exact value is known | `== expected` — ranges hide regressions |
| `>` for time comparisons | `>=` — strict comparison is flaky on fast machines |
| Testing only returned objects | Write-read cycle: reload from a fresh instance to verify persistence |

## Git Workflow

Use git worktrees. Multiple sessions may work simultaneously.

### Branch Naming

All branches other than `main` **must** follow: `<username>/<MeaningfulDescription>`

### Making Changes

0. Never commit to `main`.
1. `git worktree add <path> -b <username>/<task> origin/main`
2. Work exclusively in the worktree.
3. Separate, descriptive commits for each logical change.
4. Do not amend or force-push.
5. `npm run preflight` before pushing.
6. Commit, push, create PR targeting `main`.
7. Squash merge when merging PRs.

### After PR Merge

1. `git fetch origin --prune && git pull origin main`
2. `git worktree remove <path>`
3. `git branch -d <branch> && git push origin --delete <branch>`
4. `git worktree prune`

## Issues and Pull Requests

### Issue-First Workflow

Every PR must have a corresponding issue created before the PR.

1. Create an issue describing what will be built before starting work.
2. For multi-step features, use parent issue + sub-issues.
3. Every PR body must reference its issue(s) via closing keywords (`Closes #N`).

### Pull Requests

- Use `gh pr create --title "..." --body "Closes #N"`.
- Assign every PR to the "finance-os" GitHub Project (if one exists).
- After every push, wait for CI and Copilot code review feedback. Read all review comments, assess validity, address valid findings with a new commit, push, and resolve conversations. Repeat until no unresolved feedback remains.

## @azure Rule

When generating code for Azure, invoke `azure_development-get_best_practices` tool if available.
