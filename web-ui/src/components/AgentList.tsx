import { useEffect, useState } from 'react';
import { fetchAgents } from '../api';
import type { AgentInfo } from '../types';

export function AgentList() {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAgents()
      .then(setAgents)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p>Loading agents…</p>;
  if (error) return <p style={{ color: '#ef4444' }}>Error: {error}</p>;
  if (agents.length === 0) return <p>No agents available.</p>;

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '1rem' }}>
      {agents.map((a) => (
        <div
          key={a.name}
          data-testid={`agent-${a.name}`}
          style={{
            border: '1px solid #e5e7eb',
            borderRadius: 8,
            padding: '1rem',
          }}
        >
          <strong>{a.name}</strong>
          <p style={{ margin: '0.5rem 0 0', color: '#6b7280', fontSize: '0.875rem' }}>
            {a.description}
          </p>
        </div>
      ))}
    </div>
  );
}
