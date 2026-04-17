/** Fetch wrapper for the finance-os Web API. */

import type {
  AgentInfo, AnalyzeEarningsRequest, AnalyzeEarningsResponse,
  AssessRiskRequest, AssessRiskResponse, ChallengeThesisRequest,
  ChallengeThesisResponse, ClassifyMacroRequest, ClassifyMacroResponse,
  DigestRequest, DigestResponse, EvaluateThesisRequest, EvaluateThesisResponse,
  ExtractEntitiesRequest, ExtractEntitiesResponse, GenerateSignalsRequest,
  GenerateSignalsResponse, HealthResponse, KGStatsResponse,
  QueryRelatedRequest, QueryRelatedResponse, QuerySharedRisksRequest,
  QuerySharedRisksResponse, QuerySupplyChainRequest, QuerySupplyChainResponse,
  RunPipelineRequest, RunPipelineResponse, SearchFilingsRequest,
  SearchFilingsResponse, WatchlistData, WatchlistsResponse,
} from './types';

const BASE_URL = import.meta.env.VITE_API_URL ?? '/api';

/** Normalize FastAPI error detail (string, array, or object) to a readable string. */
export function normalizeDetail(detail: unknown): string {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((e) => {
        if (typeof e === 'object' && e !== null) {
          const loc = Array.isArray(e.loc) ? e.loc.join(' → ') : '';
          const msg = typeof e.msg === 'string' ? e.msg : JSON.stringify(e);
          return loc ? `${loc}: ${msg}` : msg;
        }
        return String(e);
      })
      .join('; ');
  }
  if (typeof detail === 'object' && detail !== null) return JSON.stringify(detail);
  return String(detail);
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const { headers: optionHeaders, ...restOptions } = options ?? {};
  const headers = new Headers(optionHeaders);

  if (restOptions.body != null && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    ...restOptions,
    headers,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = (body as Record<string, unknown>).detail ?? res.statusText;
    throw new Error(normalizeDetail(detail));
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// --- Health & Info ---

export function fetchHealth(): Promise<HealthResponse> {
  return request('/health');
}

export function fetchAgents(): Promise<AgentInfo[]> {
  return request('/agents');
}

// --- Research Digest ---

export function runDigest(req: DigestRequest): Promise<DigestResponse> {
  return request('/digest', {
    method: 'POST',
    body: JSON.stringify(req),
  });
}

// --- Watchlists ---

export function fetchWatchlists(): Promise<WatchlistsResponse> {
  return request('/watchlists');
}

export function updateWatchlist(name: string, tickers: string[]): Promise<WatchlistData> {
  return request(`/watchlists/${encodeURIComponent(name)}`, {
    method: 'PUT',
    body: JSON.stringify({ tickers }),
  });
}

export function createWatchlist(name: string, tickers: string[] = []): Promise<WatchlistData> {
  return request('/watchlists', {
    method: 'POST',
    body: JSON.stringify({ name, tickers }),
  });
}

export function deleteWatchlist(name: string): Promise<void> {
  return request(`/watchlists/${encodeURIComponent(name)}`, {
    method: 'DELETE',
  });
}

export function activateWatchlist(name: string): Promise<{ active: string; watchlist: WatchlistData }> {
  return request(`/watchlists/${encodeURIComponent(name)}/activate`, {
    method: 'PUT',
  });
}

// --- Agents ---

export function runEarningsAnalysis(req: AnalyzeEarningsRequest): Promise<AnalyzeEarningsResponse> {
  return request('/agents/earnings_interpreter', {
    method: 'POST',
    body: JSON.stringify(req),
  });
}

export function runMacroClassification(req: ClassifyMacroRequest): Promise<ClassifyMacroResponse> {
  return request('/agents/macro_regime', {
    method: 'POST',
    body: JSON.stringify(req),
  });
}

export function runFilingSearch(req: SearchFilingsRequest): Promise<SearchFilingsResponse> {
  return request('/agents/filing_analyst', {
    method: 'POST',
    body: JSON.stringify(req),
  });
}

export function runSignalGeneration(req: GenerateSignalsRequest): Promise<GenerateSignalsResponse> {
  return request('/agents/quant_signal', {
    method: 'POST',
    body: JSON.stringify(req),
  });
}

export function runThesisEvaluation(req: EvaluateThesisRequest): Promise<EvaluateThesisResponse> {
  return request('/agents/thesis_guardian', {
    method: 'POST',
    body: JSON.stringify(req),
  });
}

export function runRiskAssessment(req: AssessRiskRequest): Promise<AssessRiskResponse> {
  return request('/agents/risk_analyst', {
    method: 'POST',
    body: JSON.stringify(req),
  });
}

export function runAdversarialChallenge(req: ChallengeThesisRequest): Promise<ChallengeThesisResponse> {
  return request('/agents/adversarial', {
    method: 'POST',
    body: JSON.stringify(req),
  });
}

// --- Pipeline ---

export function runPipeline(req: RunPipelineRequest): Promise<RunPipelineResponse> {
  return request('/pipeline', {
    method: 'POST',
    body: JSON.stringify(req),
  });
}

// --- Knowledge Graph ---

export function extractEntities(req: ExtractEntitiesRequest): Promise<ExtractEntitiesResponse> {
  return request('/kg/extract', {
    method: 'POST',
    body: JSON.stringify(req),
  });
}

export function queryRelated(req: QueryRelatedRequest): Promise<QueryRelatedResponse> {
  return request('/kg/query/related', {
    method: 'POST',
    body: JSON.stringify(req),
  });
}

export function querySupplyChain(req: QuerySupplyChainRequest): Promise<QuerySupplyChainResponse> {
  return request('/kg/query/supply-chain', {
    method: 'POST',
    body: JSON.stringify(req),
  });
}

export function querySharedRisks(req: QuerySharedRisksRequest): Promise<QuerySharedRisksResponse> {
  return request('/kg/query/shared-risks', {
    method: 'POST',
    body: JSON.stringify(req),
  });
}

export function fetchKGStats(): Promise<KGStatsResponse> {
  return request('/kg/stats');
}
