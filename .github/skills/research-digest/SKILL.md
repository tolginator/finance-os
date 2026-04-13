---
name: research-digest
description: >-
  Run a full research pipeline for a watchlist of tickers. Fetches SEC filings,
  classifies macro regime, scores materiality, and generates alerts. Use when
  asked for a research digest, daily briefing, watchlist update, or market
  overview for specific tickers.
model: claude-sonnet-4
tools:
  - shell
---

## Procedure

1. **Identify the ticker watchlist.** Ask the user for tickers if not provided.
   Accept comma-separated symbols (e.g., MSFT,AAPL,GOOG).

2. **Run the research digest.**

   ```bash
   finance-os digest --tickers <TICKER1>,<TICKER2>,<TICKER3>
   ```

   Or via MCP tool `research_digest`:
   - `tickers`: List of ticker symbols.
   - `lookback_days`: Number of days to consider (default: 7).
   - `alert_threshold`: Materiality threshold 0.0–1.0 (default: 0.5).

3. **Review digest output.** The digest returns:
   - `entry_count`: Total data entries processed.
   - `alert_count`: Material changes detected.
   - `material_count`: Entries exceeding the materiality threshold.
   - `content`: Human-readable digest with per-entry sentiment scores.

4. **For deeper analysis on flagged tickers**, run the full pipeline.

   ```bash
   finance-os pipeline --ticker <TICKER>
   ```

   Or via MCP tool `orchestrate` with the default pipeline tasks.
   The pipeline runs: macro regime → filing analyst → earnings interpreter →
   quant signals (depends on macro + earnings) → adversarial (depends on
   filings + earnings). Returns a structured research memo.

5. **Present findings.** Organize by priority:
   - **Material alerts** first — what changed and why it matters.
   - **Sentiment shifts** — which tickers are trending positive or negative.
   - **Action items** — tickers that warrant deeper analysis or thesis review.
   - **Macro context** — current regime and its implications for the watchlist.
