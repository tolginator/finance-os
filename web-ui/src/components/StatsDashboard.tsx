import { useEffect, useState } from 'react';
import { fetchAgents, fetchHealth, fetchWatchlists } from '../api';
import type { AgentInfo, HealthResponse, WatchlistsResponse } from '../types';

async function fetchStats() {
  const [healthData, agentData, watchlistData] = await Promise.all([
    fetchHealth(),
    fetchAgents(),
    fetchWatchlists(),
  ]);
  return { healthData, agentData, watchlistData };
}

export function StatsDashboard() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [watchlists, setWatchlists] = useState<WatchlistsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { healthData, agentData, watchlistData } = await fetchStats();
        if (cancelled) return;
        setHealth(healthData);
        setAgents(agentData);
        setWatchlists(watchlistData);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'Failed to load stats');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const handleRefresh = async () => {
    setLoading(true);
    setError('');
    try {
      const { healthData, agentData, watchlistData } = await fetchStats();
      setHealth(healthData);
      setAgents(agentData);
      setWatchlists(watchlistData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load stats');
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <p data-testid="stats-loading" style={{ color: '#6b7280' }}>Loading stats…</p>;

  const watchlistCount = watchlists ? Object.keys(watchlists.watchlists).length : 0;
  const activeTickerCount = watchlists?.active_watchlist.tickers.length ?? 0;

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem' }}>
      {error && (
        <div data-testid="stats-error" style={{ gridColumn: '1 / -1', color: '#ef4444', padding: '0.75rem', border: '1px solid #fecaca', borderRadius: 6, background: '#fef2f2' }}>
          {error}
        </div>
      )}

      <div style={{ padding: '0.75rem', border: '1px solid #e5e7eb', borderRadius: 6 }}>
        <h3 style={{ margin: '0 0 0.5rem', fontSize: '0.95rem' }}>System Health</h3>
        <p style={{ fontSize: '0.85rem', margin: 0 }}>
          Status: <strong>{health?.status ?? 'unknown'}</strong>
        </p>
      </div>

      <div style={{ padding: '0.75rem', border: '1px solid #e5e7eb', borderRadius: 6 }}>
        <h3 style={{ margin: '0 0 0.5rem', fontSize: '0.95rem' }}>Agent Coverage</h3>
        <p style={{ fontSize: '0.85rem', margin: '0 0 0.25rem' }}>Agents available: <strong>{agents.length}</strong></p>
        <p style={{ fontSize: '0.85rem', margin: 0, color: '#6b7280' }}>Catalog stays live while portfolio workflows shift to shell views.</p>
      </div>

      <div style={{ padding: '0.75rem', border: '1px solid #e5e7eb', borderRadius: 6 }}>
        <h3 style={{ margin: '0 0 0.5rem', fontSize: '0.95rem' }}>Watchlists</h3>
        <p style={{ fontSize: '0.85rem', margin: '0 0 0.25rem' }}>Saved watchlists: <strong>{watchlistCount}</strong></p>
        <p style={{ fontSize: '0.85rem', margin: 0 }}>Active list: <strong>{watchlists?.active ?? 'none'}</strong> · {activeTickerCount} tickers</p>
      </div>

      <div style={{ gridColumn: '1 / -1', textAlign: 'right' }}>
        <button
          type="button"
          onClick={() => void handleRefresh()}
          data-testid="stats-refresh"
          style={{ padding: '0.4rem 0.75rem', borderRadius: 6, border: '1px solid #d1d5db', background: 'white', cursor: 'pointer' }}
        >
          Refresh Stats
        </button>
      </div>
    </div>
  );
}
