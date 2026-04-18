import { useCallback, useEffect, useState } from 'react';
import { activateWatchlist, createWatchlist, deleteWatchlist, fetchWatchlists } from '../api';
import type { WatchlistsResponse } from '../types';

interface WatchlistSelectorProps {
  onWatchlistChange: (name: string, tickers: string[]) => void;
  activeTickers: string[];
}

const DEFAULT_DATA: WatchlistsResponse = {
  active: 'default',
  watchlists: { default: { tickers: [] } },
  active_watchlist: { tickers: [] },
};

export function WatchlistSelector({ onWatchlistChange, activeTickers }: WatchlistSelectorProps) {
  const [data, setData] = useState<WatchlistsResponse | null>(null);
  const [newName, setNewName] = useState('');
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      const resp = await fetchWatchlists();
      setError('');
      setData(resp);
      onWatchlistChange(resp.active, resp.active_watchlist.tickers);
    } catch {
      setError('');
      setData(DEFAULT_DATA);
      onWatchlistChange(DEFAULT_DATA.active, DEFAULT_DATA.active_watchlist.tickers);
    }
  }, [onWatchlistChange]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const resp = await fetchWatchlists();
        if (cancelled) return;
        setError('');
        setData(resp);
        onWatchlistChange(resp.active, resp.active_watchlist.tickers);
      } catch {
        if (cancelled) return;
        setError('');
        setData(DEFAULT_DATA);
        onWatchlistChange(DEFAULT_DATA.active, DEFAULT_DATA.active_watchlist.tickers);
      }
    })();
    return () => { cancelled = true; };
  }, [onWatchlistChange]);

  const handleSwitch = async (name: string) => {
    try {
      const resp = await activateWatchlist(name);
      setError('');
      onWatchlistChange(name, resp.watchlist.tickers);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to switch');
    }
  };

  const handleCreate = async () => {
    const slug = newName.trim().toLowerCase().replace(/\s+/g, '-');
    if (!slug) return;
    setError('');
    try {
      await createWatchlist(slug, activeTickers);
      setNewName('');
      setCreating(false);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create');
    }
  };

  const handleDelete = async (name: string) => {
    setError('');
    try {
      await deleteWatchlist(name);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete');
    }
  };

  if (!data) return null;

  const names = Object.keys(data.watchlists).sort((a, b) => a.localeCompare(b));

  return (
    <div style={{ marginBottom: '0.75rem' }}>
      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
        <span style={{ fontSize: '0.875rem', fontWeight: 500 }}>Watchlist:</span>
        {names.map((name) => (
          <span key={name} style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
            <button
              type="button"
              onClick={() => handleSwitch(name)}
              style={{
                padding: '0.25rem 0.5rem',
                borderRadius: 4,
                border: name === data.active ? '2px solid #2563eb' : '1px solid #d1d5db',
                background: name === data.active ? '#eff6ff' : 'white',
                cursor: 'pointer',
                fontSize: '0.8rem',
                fontWeight: name === data.active ? 600 : 400,
              }}
            >
              {name}
            </button>
            {name !== data.active && (
              <button
                type="button"
                onClick={() => handleDelete(name)}
                style={{
                  background: 'none', border: 'none', cursor: 'pointer',
                  color: '#9ca3af', fontSize: '0.75rem', padding: 0,
                }}
                title={`Delete ${name}`}
                aria-label={`Delete watchlist ${name}`}
              >
                ✕
              </button>
            )}
          </span>
        ))}
        {creating ? (
          <span style={{ display: 'inline-flex', gap: '0.25rem', alignItems: 'center' }}>
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
              placeholder="name"
              style={{ padding: '0.25rem', border: '1px solid #d1d5db', borderRadius: 4, width: 100, fontSize: '0.8rem' }}
              autoFocus
            />
            <button type="button" onClick={handleCreate}
              style={{ padding: '0.25rem 0.5rem', fontSize: '0.8rem', borderRadius: 4, border: '1px solid #d1d5db', cursor: 'pointer' }}>
              ✓
            </button>
            <button type="button" onClick={() => { setCreating(false); setNewName(''); }}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#9ca3af', fontSize: '0.8rem' }}>
              ✕
            </button>
          </span>
        ) : (
          <button
            type="button"
            onClick={() => setCreating(true)}
            style={{
              padding: '0.25rem 0.5rem', borderRadius: 4,
              border: '1px dashed #d1d5db', background: 'white',
              cursor: 'pointer', fontSize: '0.8rem', color: '#6b7280',
            }}
          >
            + New
          </button>
        )}
      </div>
      {error && <p style={{ color: '#ef4444', fontSize: '0.8rem', margin: '0.25rem 0 0' }}>{error}</p>}
    </div>
  );
}
