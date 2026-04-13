---
name: earnings-analysis
description: >-
  Analyze earnings call transcripts for sentiment, guidance, and key themes.
  Use when asked to analyze earnings, interpret an earnings call, or assess
  management tone and forward guidance.
model: claude-sonnet-4
tools:
  - shell
---

## Environment Setup

Before running any `finance-os` CLI commands, activate the Python environment:

```bash
cd agents && source .venv/bin/activate
```

If the venv doesn't exist, create it first:

```bash
cd agents && python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
```

## Procedure

1. **Obtain the transcript.** If the user provides a transcript directly, use it.
   If they provide a ticker, fetch the latest earnings transcript from public sources.

2. **Run the earnings interpreter agent.**

   ```bash
   finance-os run earnings-interpreter --ticker <TICKER> --prompt "<transcript_text>"
   ```

   Or via MCP tool `analyze_earnings`:
   - `transcript`: The full or partial earnings call text.
   - `ticker`: The company ticker symbol (optional but recommended).

3. **Review the output.** The agent returns:
   - `net_sentiment`: Score from -1.0 (bearish) to 1.0 (bullish).
   - `tone`: Overall tone classification.
   - `guidance_direction`: Whether guidance was raised, maintained, or lowered.
   - `guidance_count`: Number of forward-looking statements detected.
   - `key_phrase_count`: Notable phrases extracted.
   - `content`: Human-readable summary.

4. **Contextualize.** Compare sentiment against:
   - Prior quarter results (is tone improving or deteriorating?).
   - Consensus expectations (did guidance surprise?).
   - Sector peers (is this company-specific or industry-wide?).

5. **Synthesize findings.** Present a concise summary covering:
   - Management tone and confidence level.
   - Key guidance changes and their implications.
   - Notable phrases or hedging language.
   - Whether the earnings support or challenge the investment thesis.
