/** Fetch wrapper for the finance-os Web API. */

import type {
  AgentInfo,
  ClassifyMacroRequest,
  ClassifyMacroResponse,
  DigestRequest,
  DigestResponse,
  HealthResponse,
  RunPipelineRequest,
  RunPipelineResponse,
  WatchlistData,
  WatchlistsResponse,
} from './types';

const BASE_URL = import.meta.env.VITE_API_URL ?? '/api';

interface ValidationErrorItem {
  loc?: unknown[];
  msg?: string;
}

export function normalizeDetail(detail: unknown): string {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((error) => {
        if (typeof error === 'object' && error !== null) {
          const item = error as ValidationErrorItem;
          const loc = Array.isArray(item.loc) ? item.loc.join(' → ') : '';
          const msg = typeof item.msg === 'string' ? item.msg : JSON.stringify(error);
          return loc ? `${loc}: ${msg}` : msg;
        }
        return String(error);
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

  const response = await fetch(`${BASE_URL}${path}`, {
    ...restOptions,
    headers,
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = (body as Record<string, unknown>).detail ?? response.statusText;
    throw new Error(normalizeDetail(detail));
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export function fetchHealth(): Promise<HealthResponse> {
  return request('/health');
}

export function fetchAgents(): Promise<AgentInfo[]> {
  return request('/agents');
}

export function runDigest(req: DigestRequest): Promise<DigestResponse> {
  return request('/digest', {
    method: 'POST',
    body: JSON.stringify(req),
  });
}

export function classifyMacro(req: ClassifyMacroRequest): Promise<ClassifyMacroResponse> {
  return request('/agents/macro_regime', {
    method: 'POST',
    body: JSON.stringify(req),
  });
}

export function runPipeline(req: RunPipelineRequest): Promise<RunPipelineResponse> {
  return request('/pipeline', {
    method: 'POST',
    body: JSON.stringify(req),
  });
}

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
