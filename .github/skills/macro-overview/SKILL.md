---
name: macro-overview
description: >-
  Classify the current macroeconomic regime using FRED economic indicators.
  Use when asked about macro conditions, economic outlook, interest rate
  environment, recession risk, or economic regime classification.
tools:
  - shell
---

## Procedure

1. **Run the macro regime classifier.**

   ```bash
   finance-os run macro-regime
   ```

   Or via MCP tool `classify_macro`:
   - `indicators`: Optional list of specific FRED series IDs to analyze.
     Defaults to standard indicators (unemployment, GDP growth, yield curve,
     inflation, ISM manufacturing).

2. **Review regime output.** The agent returns:
   - `regime`: One of EXPANSION, CONTRACTION, or TRANSITION.
   - `indicators_fetched`: Number of FRED series retrieved.
   - `indicators_with_data`: Number with valid recent readings.
   - `content`: Human-readable regime analysis with indicator details.

3. **Interpret the regime.** Explain what the classification means:
   - **EXPANSION**: Growth accelerating, favorable for risk assets. Equities
     and credit tend to outperform. Consider cyclical tilts.
   - **CONTRACTION**: Growth decelerating or negative. Defensive positioning
     warranted. Favor quality, low-beta, and duration.
   - **TRANSITION**: Mixed signals, regime change likely. Heightened
     uncertainty. Reduce leverage, increase cash buffers.

4. **Connect to portfolio implications.** Based on the regime:
   - Which sectors historically outperform in this regime?
   - How should position sizing and risk tolerances adjust?
   - What leading indicators to watch for regime change signals?

5. **Identify key indicators to monitor.** Highlight:
   - Indicators closest to inflection points.
   - Divergences between indicators (e.g., strong employment but inverted curve).
   - Data releases coming in the next 1–2 weeks that could shift the regime.
