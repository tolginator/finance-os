/** API response types matching the FastAPI backend contracts. */

export interface AgentInfo {
  name: string;
  description: string;
}

export interface DigestRequest {
  tickers: string[];
  lookback_days?: number;
  alert_threshold?: string;
}

export interface DigestResponse {
  ticker_count: number;
  entry_count: number;
  alert_count: number;
  material_count: number;
  content: string;
}

export interface HealthResponse {
  status: string;
}

export interface TaxLot {
  ticker: string;
  shares: string;
  cost_basis_per_share: string;
  purchase_date: string;
}

export interface CashHolding {
  amount: string;
  valuation_date: string;
  is_money_market: boolean;
  ticker: string | null;
  counts_toward_liquidity_reserve: boolean;
}

export interface Account {
  name: string;
  account_type: string;
  tax_lots: TaxLot[];
  cash_holdings: CashHolding[];
}

export interface Household {
  name: string;
  accounts: Account[];
  liquidity_reserve_floor: string;
  revision: number;
  updated_at: string;
}

export interface HouseholdResponse {
  household: Household;
  exists: boolean;
}

export interface WatchlistData {
  tickers: string[];
}

export interface WatchlistsResponse {
  active: string;
  watchlists: Record<string, WatchlistData>;
  active_watchlist: WatchlistData;
}

export interface ClassifyMacroRequest {
  api_key?: string;
  indicators?: string[];
}

export interface ClassifyMacroResponse {
  content: string;
  regime: string;
  indicators_fetched: number;
  indicators_with_data: number;
}

export type MacroRegimeResponse = ClassifyMacroResponse;

export interface GenerateSignalsRequest {
  signals?: Record<string, unknown>[];
  sentiment?: string | number;
  regime?: string;
  direction?: string;
  source?: string;
  method?: string;
}

export interface GenerateSignalsResponse {
  content: string;
  agent: string;
  composite: Record<string, unknown>;
  signals: Record<string, unknown>[];
}

export interface EvaluateThesisRequest {
  theses: Record<string, unknown>[];
  data?: Record<string, string>;
}

export interface EvaluateThesisResponse {
  content: string;
  theses_checked: number;
  alerts_generated: number;
  critical_alerts: number;
}

export interface AssessRiskRequest {
  positions?: Record<string, unknown>[];
  scenarios?: Record<string, unknown>[];
  returns?: string[];
}

export interface AssessRiskResponse {
  content: string;
}

export interface TaskDefinition {
  agent_name: string;
  prompt?: string;
  kwargs?: Record<string, unknown>;
  priority?: number;
  depends_on?: string[];
  task_id?: string;
}

export interface RunPipelineRequest {
  tasks: TaskDefinition[];
}

export interface PipelineTaskResult {
  task_id: string;
  agent_name: string;
  success: boolean;
  duration_ms: number;
  content: string | null;
  metadata: Record<string, unknown>;
  error: string | null;
}

export interface RunPipelineResponse {
  results: PipelineTaskResult[];
  total_duration_ms: number;
  successful: number;
  failed: number;
  memo: Record<string, unknown> | null;
}
