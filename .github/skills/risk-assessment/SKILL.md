---
name: risk-assessment
description: >-
  Analyze portfolio risk including scenario stress tests, concentration analysis,
  and tail-risk simulations. Use when asked about portfolio risk, stress testing,
  drawdown analysis, VaR, or position sizing.
model: claude-sonnet-4
tools:
  - shell
---

## Environment Setup

```bash
source agents/scripts/ensure-env.sh
```

## Procedure

1. **Gather portfolio context.** Ask the user for:
   - Current positions (tickers and weights or dollar amounts).
   - Any specific risk scenarios to stress-test.
   - Return series or time period for analysis.

2. **Run the risk agent.**

   ```bash
   finance-os run risk-analyst --prompt "Assess portfolio risk" \
     --prompt "<portfolio_description_and_positions>"
   ```

   Pass structured data via the prompt: positions, scenarios, or return series.
   The agent performs:
   - Value-at-Risk (VaR) estimation.
   - Concentration analysis (single-name, sector, factor).
   - Scenario stress tests (user-defined or standard: recession, rate shock, etc.).
   - Correlation analysis across holdings.

3. **Review risk output.** The agent returns:
   - Risk metrics (VaR, max drawdown, volatility).
   - Concentration warnings (positions exceeding thresholds).
   - Scenario outcomes (portfolio impact under each stress scenario).
   - Recommendations for risk reduction.

4. **Cross-reference with macro regime.** Check if the current macro
   environment amplifies identified risks.

   ```bash
   finance-os run macro-regime
   ```

   Or via MCP tool `classify_macro`. If regime is CONTRACTION, risk
   tolerances should tighten.

5. **Synthesize.** Present:
   - Top risk exposures and their magnitudes.
   - Worst-case scenario outcomes.
   - Diversification gaps.
   - Actionable recommendations: rebalance, hedge, or reduce positions.
