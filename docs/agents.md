# Agents

## Agent Types

| Agent | Purpose | Status |
|---|---|---|
| Filing Analyst | Extracts deltas, risk language shifts, capex changes from SEC filings | Planned |
| Earnings Interpreter | Tone analysis, sentiment drift, management confidence scoring | Planned |
| Macro Regime | Classifies macro environment using text + data | Planned |
| Quant Signal | Transforms textual insights into structured quant features | Planned |
| Thesis Guardian | Monitors investment theses, flags broken assumptions | Planned |
| Risk Agent | Scenario analysis, correlation stress tests, tail-risk simulations | Planned |
| Adversarial | Systematic thesis challenger — disproves your thesis | Planned |

## Agent Base Class

All agents extend `BaseAgent` in `agents/src/core/agent.py`. See that file for the interface contract.
