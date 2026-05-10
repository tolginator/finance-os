export interface AgentSpec {
  name: string;
  label: string;
  description: string;
}

export const agentSpecs: AgentSpec[] = [
  {
    name: 'macro_regime',
    label: 'Macro Regime',
    description: 'Classify current macro environment from FRED indicators.',
  },
  {
    name: 'quant_signal',
    label: 'Quant Signal',
    description: 'Generate composite quantitative signals.',
  },
  {
    name: 'thesis_guardian',
    label: 'Thesis Guardian',
    description: 'Evaluate investment theses against observed data.',
  },
  {
    name: 'risk_analyst',
    label: 'Risk Analyst',
    description: 'Run portfolio risk analysis — VaR, CVaR, stress scenarios.',
  },
  {
    name: 'adversarial',
    label: 'Adversarial',
    description: 'Challenge investment claims or theses adversarially.',
  },
];

export function getAgentSpec(name: string): AgentSpec | undefined {
  return agentSpecs.find((spec) => spec.name === name);
}
