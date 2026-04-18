import { useCallback, useRef, useState } from 'react';
import { fetchTickerSummary, fetchTickerTranscript } from '../api';
import type { TickerSummary, TickerTranscript } from '../types';

export interface TickerContext {
  symbol: string;
  summary: TickerSummary | null;
  transcript: TickerTranscript | null;
  loading: boolean;
}

interface TickerBarProps {
  onTickerChange: (ctx: TickerContext) => void;
}

export function TickerBar({ onTickerChange }: TickerBarProps) {
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [summary, setSummary] = useState<TickerSummary | null>(null);
  const requestId = useRef(0);

  const lookup = useCallback(async () => {
    const symbol = input.trim().toUpperCase();
    if (!symbol) return;

    const thisRequest = ++requestId.current;

    setLoading(true);
    setError('');
    setSummary(null);
    onTickerChange({ symbol, summary: null, transcript: null, loading: true });

    try {
      const [sum, tx] = await Promise.all([
        fetchTickerSummary(symbol),
        fetchTickerTranscript(symbol),
      ]);
      // Ignore stale responses from superseded requests
      if (thisRequest !== requestId.current) return;
      setSummary(sum);
      onTickerChange({ symbol, summary: sum, transcript: tx, loading: false });
    } catch (err) {
      if (thisRequest !== requestId.current) return;
      const msg = err instanceof Error ? err.message : 'Lookup failed';
      setError(msg);
      onTickerChange({ symbol, summary: null, transcript: null, loading: false });
    } finally {
      if (thisRequest === requestId.current) {
        setLoading(false);
      }
    }
  }, [input, onTickerChange]);

  return (
    <div data-testid="ticker-bar" style={{ padding: '1rem', background: '#f0f4ff', borderRadius: 8, marginBottom: '1rem' }}>
      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
        <input
          data-testid="ticker-input"
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value.toUpperCase())}
          onKeyDown={(e) => { if (e.key === 'Enter') lookup(); }}
          placeholder="Enter ticker (e.g. AAPL)"
          style={{ padding: '0.5rem 0.75rem', border: '1px solid #d1d5db', borderRadius: 6, fontSize: '1rem', fontWeight: 600, width: 140 }}
        />
        <button
          data-testid="ticker-lookup"
          type="button"
          onClick={lookup}
          disabled={loading || !input.trim()}
          style={{ padding: '0.5rem 1rem', background: '#2563eb', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: '0.9rem' }}
        >
          {loading ? 'Looking up…' : 'Look Up'}
        </button>
      </div>

      {error && <p data-testid="ticker-error" style={{ color: '#ef4444', marginTop: '0.5rem', fontSize: '0.85rem' }}>{error}</p>}

      {summary && (
        <div data-testid="ticker-summary" style={{ marginTop: '0.75rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '0.5rem', fontSize: '0.85rem' }}>
          <div><strong>{summary.name}</strong> ({summary.symbol})</div>
          <div>Sector: {summary.sector || '—'}</div>
          <div>Industry: {summary.industry || '—'}</div>
          <div>Price: {summary.current_price ? `${summary.currency} ${summary.current_price}` : '—'}</div>
          <div>Market Cap: {summary.market_cap ? formatMarketCap(summary.market_cap) : '—'}</div>
          <div>52W Range: {summary.fifty_two_week_low && summary.fifty_two_week_high ? `${summary.fifty_two_week_low} – ${summary.fifty_two_week_high}` : '—'}</div>
          {summary.earnings_date && <div>Next Earnings: {summary.earnings_date}</div>}
        </div>
      )}

      {summary?.description && (
        <p style={{ marginTop: '0.5rem', fontSize: '0.8rem', color: '#4b5563', lineHeight: 1.4 }}>
          {summary.description.length > 300 ? summary.description.slice(0, 300) + '…' : summary.description}
        </p>
      )}
    </div>
  );
}

function formatMarketCap(val: string): string {
  const num = Number(val);
  if (!Number.isFinite(num)) return val;
  if (num >= 1e12) return `$${(num / 1e12).toFixed(1)}T`;
  if (num >= 1e9) return `$${(num / 1e9).toFixed(1)}B`;
  if (num >= 1e6) return `$${(num / 1e6).toFixed(0)}M`;
  return `$${num.toLocaleString()}`;
}
