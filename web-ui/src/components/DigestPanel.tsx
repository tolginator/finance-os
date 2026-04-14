import { useState } from 'react';
import { runDigest } from '../api';
import type { DigestResponse } from '../types';

function parseTickers(input: string): string[] {
  return input
    .split(/[,\s]+/)
    .map((t) => t.trim().toUpperCase())
    .filter((t) => t.length > 0);
}

export function DigestPanel() {
  const [input, setInput] = useState('');
  const [lookback, setLookback] = useState(7);
  const [result, setResult] = useState<DigestResponse | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const tickers = parseTickers(input);
    if (tickers.length === 0) {
      setError('Enter at least one ticker symbol.');
      return;
    }
    setError('');
    setResult(null);
    setLoading(true);
    try {
      const resp = await runDigest({ tickers, lookback_days: lookback });
      setResult(resp);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'end' }}>
        <label style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem', flex: 1 }}>
          <span style={{ fontSize: '0.875rem', fontWeight: 500 }}>Tickers</span>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="AAPL, MSFT, GOOGL"
            style={{ padding: '0.5rem', border: '1px solid #d1d5db', borderRadius: 6 }}
          />
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem', width: 100 }}>
          <span style={{ fontSize: '0.875rem', fontWeight: 500 }}>Lookback</span>
          <input
            type="number"
            value={lookback}
            onChange={(e) => setLookback(Number(e.target.value))}
            min={1}
            max={90}
            style={{ padding: '0.5rem', border: '1px solid #d1d5db', borderRadius: 6 }}
          />
        </label>
        <button
          type="submit"
          disabled={loading}
          style={{
            padding: '0.5rem 1rem',
            backgroundColor: '#2563eb',
            color: 'white',
            border: 'none',
            borderRadius: 6,
            cursor: loading ? 'wait' : 'pointer',
          }}
        >
          {loading ? 'Running…' : 'Run Digest'}
        </button>
      </form>

      {error && (
        <p data-testid="digest-error" style={{ color: '#ef4444', marginTop: '0.75rem' }}>
          {error}
        </p>
      )}

      {result && (
        <div data-testid="digest-result" style={{ marginTop: '1rem', border: '1px solid #e5e7eb', borderRadius: 8, padding: '1rem' }}>
          <div style={{ display: 'flex', gap: '1.5rem', marginBottom: '0.75rem', fontSize: '0.875rem' }}>
            <span>Tickers: <strong>{result.ticker_count}</strong></span>
            <span>Entries: <strong>{result.entry_count}</strong></span>
            <span>Alerts: <strong>{result.alert_count}</strong></span>
            <span>Material: <strong>{result.material_count}</strong></span>
          </div>
          <pre style={{ whiteSpace: 'pre-wrap', fontSize: '0.875rem', margin: 0 }}>
            {result.content}
          </pre>
        </div>
      )}
    </div>
  );
}
