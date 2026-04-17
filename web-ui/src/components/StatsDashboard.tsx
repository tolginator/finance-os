import { useCallback, useEffect, useState } from 'react';
import { fetchHealth, fetchAgents, fetchKGStats } from '../api';
import type { AgentInfo, KGStatsResponse } from '../types';

export function StatsDashboard() {
  const [health, setHealth] = useState<{ status: string } | null>(null);
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [kgStats, setKgStats] = useState<KGStatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const refresh = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [h, a, kg] = await Promise.all([
        fetchHealth(),
        fetchAgents(),
        fetchKGStats(),
      ]);
      setHealth(h);
      setAgents(a);
      setKgStats(kg);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load stats');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  if (loading) return <p data-testid="stats-loading" style={{ color: '#6b7280' }}>Loading stats…</p>;
  if (error) return <p data-testid="stats-error" style={{ color: '#ef4444' }}>{error}</p>;

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1rem' }}>
      {/* Health */}
      <div style={{ padding: '0.75rem', border: '1px solid #e5e7eb', borderRadius: 6 }}>
        <h3 style={{ margin: '0 0 0.5rem', fontSize: '0.95rem' }}>System Health</h3>
        {health && (
          <p style={{ fontSize: '0.85rem', margin: 0 }}>
            Status: <strong style={{ color: health.status === 'ok' ? '#16a34a' : '#ef4444' }}>{health.status}</strong>
          </p>
        )}
      </div>

      {/* Agent Catalog */}
      <div style={{ padding: '0.75rem', border: '1px solid #e5e7eb', borderRadius: 6 }}>
        <h3 style={{ margin: '0 0 0.5rem', fontSize: '0.95rem' }}>Agents ({agents.length})</h3>
        <ul style={{ margin: 0, padding: '0 0 0 1.25rem', fontSize: '0.85rem' }}>
          {agents.map((a) => (
            <li key={a.name} style={{ marginBottom: '0.25rem' }}>
              <strong>{a.name}</strong> — {a.description}
            </li>
          ))}
        </ul>
      </div>

      {/* KG Stats */}
      <div style={{ padding: '0.75rem', border: '1px solid #e5e7eb', borderRadius: 6 }}>
        <h3 style={{ margin: '0 0 0.5rem', fontSize: '0.95rem' }}>Knowledge Graph</h3>
        {kgStats && (
          <div style={{ fontSize: '0.85rem' }}>
            <p style={{ margin: '0 0 0.25rem' }}><strong>Entities:</strong> {kgStats.entity_count}</p>
            <p style={{ margin: '0 0 0.25rem' }}><strong>Relationships:</strong> {kgStats.relationship_count}</p>
            {Object.entries(kgStats.entities_by_type).map(([type, count]) => (
              <span key={type} style={{ display: 'inline-block', marginRight: '0.5rem', padding: '0.15rem 0.4rem', background: '#f3f4f6', borderRadius: 4, fontSize: '0.8rem' }}>
                {type}: {count}
              </span>
            ))}
          </div>
        )}
      </div>

      <div style={{ gridColumn: '1 / -1', textAlign: 'right' }}>
        <button
          onClick={refresh}
          data-testid="stats-refresh"
          style={{ padding: '0.4rem 0.75rem', borderRadius: 6, border: '1px solid #d1d5db', background: 'white', cursor: 'pointer' }}
        >
          Refresh Stats
        </button>
      </div>
    </div>
  );
}
