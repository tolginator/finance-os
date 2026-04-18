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

export interface WatchlistData {
  tickers: string[];
}

export interface WatchlistsResponse {
  active: string;
  watchlists: Record<string, WatchlistData>;
  active_watchlist: WatchlistData;
}

// --- Agent request/response types ---

export interface AnalyzeEarningsRequest {
  transcript: string;
  ticker?: string;
}

export interface AnalyzeEarningsResponse {
  content: string;
  tone: string;
  net_sentiment: number;
  confidence: string;
  guidance_direction: string;
  guidance_count: number;
  key_phrase_count: number;
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

export interface SearchFilingsRequest {
  ticker?: string;
  cik?: string;
  form_type?: string;
}

export interface SearchFilingsResponse {
  content: string;
  cik: string;
  form_type: string;
  filing_count: number;
}

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
  returns?: (string | number)[];
}

export interface AssessRiskResponse {
  content: string;
}

export interface ChallengeThesisRequest {
  claims?: string[];
  prompt?: string;
}

export interface ChallengeThesisResponse {
  content: string;
  conviction_score: string;
  counter_count: number;
  blind_spot_count: number;
}

// --- Pipeline types ---

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

// --- Knowledge Graph types ---

export interface EntityModel {
  entity_id: string;
  name: string;
  entity_type: string;
  ticker: string | null;
  cik: string | null;
  metadata: Record<string, unknown>;
}

export interface RelationshipModel {
  source_id: string;
  target_id: string;
  rel_type: string;
  evidence: string;
  source_doc: string;
  confidence: string;
  metadata: Record<string, unknown>;
}

export interface ExtractEntitiesRequest {
  text: string;
  source_doc?: string;
  ticker?: string;
}

export interface ExtractEntitiesResponse {
  entities: EntityModel[];
  relationships: RelationshipModel[];
  entity_count: number;
  relationship_count: number;
}

export interface QueryRelatedRequest {
  entity_id: string;
  max_depth?: number;
}

export interface QueryRelatedResponse {
  entity_id: string;
  related: EntityModel[];
  count: number;
}

export interface QuerySupplyChainRequest {
  entity_id: string;
  direction?: 'upstream' | 'downstream';
}

export interface QuerySupplyChainResponse {
  entity_id: string;
  direction: string;
  chain: EntityModel[];
  count: number;
}

export interface QuerySharedRisksRequest {
  entity_ids: string[];
}

export interface QuerySharedRisksResponse {
  entity_ids: string[];
  shared_risks: EntityModel[];
  count: number;
}

export interface KGStatsResponse {
  entity_count: number;
  relationship_count: number;
  entities_by_type: Record<string, number>;
  relationships_by_type: Record<string, number>;
}
