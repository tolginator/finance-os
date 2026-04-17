/** Agent specification registry — single source of truth for per-agent UI forms. */

export interface FieldSpec {
  name: string;
  label: string;
  type: 'text' | 'textarea' | 'number' | 'select' | 'json';
  required?: boolean;
  defaultValue?: string;
  placeholder?: string;
  options?: string[];
}

export interface AgentSpec {
  name: string;
  label: string;
  description: string;
  endpoint: string;
  fields: FieldSpec[];
  responseFields: string[];
}

export const agentSpecs: AgentSpec[] = [
  {
    name: 'earnings_interpreter',
    label: 'Earnings Interpreter',
    description: 'Analyze earnings call transcripts for tone, sentiment, and guidance.',
    endpoint: '/agents/earnings_interpreter',
    fields: [
      { name: 'transcript', label: 'Transcript', type: 'textarea', required: true, placeholder: 'Paste earnings call transcript...' },
      { name: 'ticker', label: 'Ticker', type: 'text', placeholder: 'AAPL' },
    ],
    responseFields: ['tone', 'net_sentiment', 'confidence', 'guidance_direction', 'guidance_count', 'key_phrase_count'],
  },
  {
    name: 'macro_regime',
    label: 'Macro Regime',
    description: 'Classify current macro environment from FRED indicators.',
    endpoint: '/agents/macro_regime',
    fields: [
      { name: 'api_key', label: 'FRED API Key', type: 'text', placeholder: 'Optional — uses env default' },
      { name: 'indicators', label: 'Indicators (JSON)', type: 'json', placeholder: '["GDP", "UNRATE", "CPIAUCSL"]' },
    ],
    responseFields: ['regime', 'indicators_fetched', 'indicators_with_data'],
  },
  {
    name: 'filing_analyst',
    label: 'Filing Analyst',
    description: 'Search and list SEC filings for a company.',
    endpoint: '/agents/filing_analyst',
    fields: [
      { name: 'ticker', label: 'Ticker', type: 'text', placeholder: 'AAPL' },
      { name: 'cik', label: 'CIK', type: 'text', placeholder: 'Optional — resolved from ticker' },
      { name: 'form_type', label: 'Form Type', type: 'select', defaultValue: '10-K', options: ['10-K', '10-Q', '8-K', 'DEF 14A', 'S-1'] },
    ],
    responseFields: ['cik', 'form_type', 'filing_count'],
  },
  {
    name: 'quant_signal',
    label: 'Quant Signal',
    description: 'Generate composite quantitative signals.',
    endpoint: '/agents/quant_signal',
    fields: [
      { name: 'signals', label: 'Signals (JSON)', type: 'json', placeholder: '[{"name": "momentum", "value": 0.7, "weight": 1.0}]' },
      { name: 'regime', label: 'Macro Regime', type: 'text', placeholder: 'expansion' },
      { name: 'direction', label: 'Direction', type: 'text', placeholder: 'long' },
      { name: 'method', label: 'Method', type: 'select', defaultValue: 'equal_weight', options: ['equal_weight', 'risk_parity'] },
    ],
    responseFields: ['agent', 'composite', 'signals'],
  },
  {
    name: 'thesis_guardian',
    label: 'Thesis Guardian',
    description: 'Evaluate investment theses against observed data.',
    endpoint: '/agents/thesis_guardian',
    fields: [
      { name: 'theses', label: 'Theses (JSON)', type: 'json', required: true, placeholder: '[{"ticker": "AAPL", "hypothesis": "...", "assumptions": [...]}]' },
      { name: 'data', label: 'Observed Data (JSON)', type: 'json', placeholder: '{"revenue_growth": "0.15"}' },
    ],
    responseFields: ['theses_checked', 'alerts_generated', 'critical_alerts'],
  },
  {
    name: 'risk_analyst',
    label: 'Risk Analyst',
    description: 'Run portfolio risk analysis — VaR, CVaR, stress scenarios.',
    endpoint: '/agents/risk_analyst',
    fields: [
      { name: 'positions', label: 'Positions (JSON)', type: 'json', placeholder: '[{"ticker": "AAPL", "weight": 0.3}]' },
      { name: 'scenarios', label: 'Scenarios (JSON)', type: 'json', placeholder: '[{"name": "crash", "shocks": {...}}]' },
      { name: 'returns', label: 'Returns (JSON)', type: 'json', placeholder: '["0.01", "-0.02", "0.005"]' },
    ],
    responseFields: [],
  },
  {
    name: 'adversarial',
    label: 'Adversarial',
    description: 'Challenge investment claims or theses adversarially.',
    endpoint: '/agents/adversarial',
    fields: [
      { name: 'claims', label: 'Claims (JSON)', type: 'json', placeholder: '["Revenue will grow 20% YoY"]' },
      { name: 'prompt', label: 'Thesis Prompt', type: 'textarea', placeholder: 'Describe the investment thesis to challenge...' },
    ],
    responseFields: ['conviction_score', 'counter_count', 'blind_spot_count'],
  },
];

export function getAgentSpec(name: string): AgentSpec | undefined {
  return agentSpecs.find((s) => s.name === name);
}
