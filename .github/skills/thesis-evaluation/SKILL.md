---
name: thesis-evaluation
description: >-
  Evaluate an investment thesis by running adversarial challenges, identifying
  blind spots, and computing conviction scores. Use when asked to evaluate,
  challenge, stress-test, or critique an investment thesis.
model: claude-opus-4
tools:
  - shell
---

## Environment Setup

```bash
source agents/scripts/ensure-env.sh
```

## Procedure

1. **Gather the thesis.** Ask the user for:
   - The ticker symbol.
   - The investment thesis (bull case, key assumptions, catalysts).
   - Any position sizing or time horizon context.

2. **Run the adversarial agent** to challenge the thesis.

   ```bash
   finance-os run adversarial --ticker <TICKER> --prompt "Challenge the investment thesis for <TICKER>: <thesis_text>"
   ```

   Or via MCP tool `orchestrate` with a single adversarial task:
   ```json
   {
     "tasks": [{"agent_name": "adversarial", "prompt": "Challenge: <thesis>", "task_id": "challenge"}],
     "ticker": "<TICKER>"
   }
   ```

3. **Review adversarial output.** The agent returns:
   - `conviction_score`: 0.0–1.0 post-challenge conviction.
   - `counter_count`: Number of counter-arguments found.
   - `blind_spot_count`: Unaddressed risk categories.
   - Counter-arguments ranked by strength (STRONG, MODERATE, WEAK).
   - Blind spots ranked by severity (HIGH, MEDIUM, LOW).

4. **Run the thesis guardian** if the user has an active thesis to monitor.

   ```bash
   finance-os run thesis-guardian --ticker <TICKER> --prompt "Monitor thesis assumptions"
   ```

   Pass structured theses via kwargs for richer analysis.

5. **Cross-reference with filings.** Run the filing analyst to check if recent
   SEC filings support or contradict thesis assumptions.

   ```bash
   finance-os run filing-analyst --ticker <TICKER>
   ```

6. **Synthesize.** Present:
   - Post-challenge conviction score and what it means.
   - The strongest counter-arguments and how they could invalidate the thesis.
   - Critical blind spots the thesis doesn't address.
   - Recommendations: strengthen thesis, reduce position, or abandon.
