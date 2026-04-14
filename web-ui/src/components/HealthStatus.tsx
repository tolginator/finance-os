import { useEffect, useState } from 'react';
import { fetchHealth } from '../api';

export function HealthStatus() {
  const [status, setStatus] = useState<'loading' | 'ok' | 'error'>('loading');

  useEffect(() => {
    fetchHealth()
      .then((r) => setStatus(r.status === 'ok' ? 'ok' : 'error'))
      .catch(() => setStatus('error'));
  }, []);

  const color = status === 'ok' ? '#22c55e' : status === 'error' ? '#ef4444' : '#a3a3a3';
  const label = status === 'ok' ? 'API Connected' : status === 'error' ? 'API Unavailable' : 'Checking…';

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
      <span
        data-testid="health-dot"
        style={{
          width: 12,
          height: 12,
          borderRadius: '50%',
          backgroundColor: color,
          display: 'inline-block',
        }}
      />
      <span data-testid="health-label">{label}</span>
    </div>
  );
}
