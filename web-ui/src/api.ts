/** Fetch wrapper for the finance-os Web API. */

import type { AgentInfo, DigestRequest, DigestResponse, HealthResponse } from './types';

const BASE_URL = import.meta.env.VITE_API_URL ?? '/api';

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
    throw new Error(String(detail));
  }
  return res.json() as Promise<T>;
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
