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
