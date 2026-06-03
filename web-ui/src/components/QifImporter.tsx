import { useCallback, useEffect, useState } from 'react';
import { setQifSource, setExcludedAccounts } from '../api';
import type { ImportPreviewResponse } from '../types';

interface QifImporterProps {
  onImported: () => void;
}

type ImportStatus = 'idle' | 'previewing' | 'preview' | 'saving' | 'done';

interface BrowseEntry {
  name: string;
  path: string;
  is_dir: boolean;
}

const panelStyle = {
  border: '1px solid #e5e7eb',
  borderRadius: 12,
  background: '#fff',
  padding: '1rem',
};

const secondaryTextStyle = { color: '#6b7280', fontSize: '0.9rem' };

const buttonStyle = {
  border: '1px solid #d1d5db',
  borderRadius: 10,
  padding: '0.65rem 1rem',
  background: '#111827',
  color: '#fff',
  fontWeight: 600,
  cursor: 'pointer',
};

const secondaryButtonStyle = {
  ...buttonStyle,
  background: '#fff',
  color: '#111827',
};

// ---------------------------------------------------------------------------
// File browser modal
// ---------------------------------------------------------------------------

function FileBrowser({ onSelect, onCancel }: { onSelect: (path: string) => void; onCancel: () => void }) {
  const [currentDir, setCurrentDir] = useState('~');
  const [entries, setEntries] = useState<BrowseEntry[]>([]);
  const [parentDir, setParentDir] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [browseError, setBrowseError] = useState('');

  const loadDir = useCallback(async (dir: string) => {
    setLoading(true);
    setBrowseError('');
    try {
      const params = new URLSearchParams({ path: dir, filter: '.qif' });
      const response = await fetch(`/api/filesystem/browse?${params}`);
      if (!response.ok) {
        const data = await response.json().catch(() => ({ detail: 'Failed to browse directory' }));
        throw new Error(data.detail ?? 'Failed to browse directory');
      }
      const data = await response.json();
      setCurrentDir(data.current);
      setParentDir(data.parent);
      setEntries(data.entries);
    } catch (err) {
      setBrowseError(err instanceof Error ? err.message : 'Browse failed');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadDir(currentDir);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div
      data-testid="qif-file-browser"
      style={{
        border: '1px solid #d1d5db',
        borderRadius: 12,
        background: '#f9fafb',
        padding: '1rem',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.75rem',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ fontWeight: 700, fontSize: '0.95rem' }}>Select QIF File</div>
        <button type="button" onClick={onCancel} style={{ ...secondaryButtonStyle, padding: '0.35rem 0.65rem', fontSize: '0.85rem' }}>
          Cancel
        </button>
      </div>

      <div style={{ fontSize: '0.85rem', color: '#374151', fontFamily: 'monospace', padding: '0.4rem 0.6rem', background: '#e5e7eb', borderRadius: 8 }}>
        {currentDir}
      </div>

      {browseError ? (
        <div style={{ color: '#b91c1c', fontSize: '0.85rem' }}>{browseError}</div>
      ) : null}

      <div style={{ maxHeight: 300, overflowY: 'auto', border: '1px solid #e5e7eb', borderRadius: 8, background: '#fff' }}>
        {parentDir ? (
          <button
            type="button"
            onClick={() => void loadDir(parentDir)}
            style={{ width: '100%', textAlign: 'left', padding: '0.55rem 0.75rem', border: 'none', background: 'transparent', cursor: 'pointer', fontWeight: 600, color: '#2563eb', borderBottom: '1px solid #f3f4f6' }}
          >
            ↑ ..
          </button>
        ) : null}
        {loading ? (
          <div style={{ padding: '1rem', textAlign: 'center', color: '#6b7280' }}>Loading…</div>
        ) : entries.length === 0 ? (
          <div style={{ padding: '1rem', textAlign: 'center', color: '#6b7280' }}>No files or folders</div>
        ) : (
          entries.map((entry) => (
            <button
              type="button"
              key={entry.path}
              onClick={() => (entry.is_dir ? void loadDir(entry.path) : onSelect(entry.path))}
              style={{
                width: '100%',
                textAlign: 'left',
                padding: '0.55rem 0.75rem',
                border: 'none',
                background: 'transparent',
                cursor: 'pointer',
                display: 'flex',
                gap: '0.5rem',
                alignItems: 'center',
                borderBottom: '1px solid #f3f4f6',
              }}
            >
              <span style={{ fontSize: '1rem' }}>{entry.is_dir ? '📁' : '📄'}</span>
              <span style={{ fontWeight: entry.is_dir ? 600 : 400, color: entry.is_dir ? '#374151' : '#111827' }}>
                {entry.name}
              </span>
            </button>
          ))
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main QIF Importer
// ---------------------------------------------------------------------------

export function QifImporter({ onImported }: QifImporterProps) {
  const [status, setStatus] = useState<ImportStatus>('idle');
  const [qifPath, setQifPath] = useState('');
  const [browsing, setBrowsing] = useState(false);
  const [preview, setPreview] = useState<ImportPreviewResponse | null>(null);
  const [selectedAccounts, setSelectedAccounts] = useState<Set<string>>(new Set());
  const [error, setError] = useState('');

  const canPreview = qifPath.trim().length > 0 && status !== 'previewing' && status !== 'saving';

  async function handlePreview() {
    const trimmed = qifPath.trim();
    if (!trimmed) return;

    setError('');
    setStatus('previewing');

    try {
      await setQifSource(trimmed);

      const response = await fetch('/api/household');
      if (!response.ok) throw new Error('Failed to load household from QIF.');
      const data = await response.json();
      if (!data.exists) throw new Error('QIF file could not be parsed.');

      const accounts = data.household.accounts ?? [];
      setPreview({
        accounts,
        warnings: [],
        position_only: false,
      });
      setSelectedAccounts(new Set(accounts.map((a: { name: string }) => a.name)));
      setStatus('preview');
    } catch (previewError) {
      setPreview(null);
      setStatus('idle');
      setError(previewError instanceof Error ? previewError.message : 'Unable to preview QIF import.');
    }
  }

  async function handleConfirm() {
    if (preview === null) return;

    setError('');
    setStatus('saving');

    try {
      const allNames = preview.accounts.map((a) => a.name);
      const excluded = allNames.filter((name) => !selectedAccounts.has(name));
      await setExcludedAccounts(excluded);
      setStatus('done');
    } catch (saveError) {
      setStatus('preview');
      setError(saveError instanceof Error ? saveError.message : 'Unable to save account selection.');
    }
  }

  function handleCancel() {
    setStatus('idle');
    setPreview(null);
    setSelectedAccounts(new Set());
    setError('');
  }

  function handleFileSelected(path: string) {
    setQifPath(path);
    setBrowsing(false);
  }

  return (
    <div data-testid="qif-importer" style={{ ...panelStyle, display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
        <div style={{ fontSize: '1rem', fontWeight: 700 }}>Import a QIF file</div>
        <div style={secondaryTextStyle}>Browse to select your QIF file. It will be parsed fresh on every portfolio load.</div>
      </div>

      {error ? (
        <div style={{ border: '1px solid #fecaca', borderRadius: 10, background: '#fef2f2', color: '#b91c1c', padding: '0.75rem' }}>
          {error}
        </div>
      ) : null}

      {(status === 'idle' || status === 'previewing') && !browsing && (
        <>
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'stretch' }}>
            <input
              data-testid="qif-path-input"
              type="text"
              value={qifPath}
              onChange={(event) => setQifPath(event.target.value)}
              placeholder="No file selected"
              readOnly
              style={{ flex: 1, border: '1px solid #d1d5db', borderRadius: 10, padding: '0.7rem 0.85rem', font: 'inherit', background: '#f9fafb', color: '#374151' }}
            />
            <button
              type="button"
              data-testid="qif-browse-button"
              onClick={() => setBrowsing(true)}
              disabled={status === 'previewing'}
              style={secondaryButtonStyle}
            >
              Browse…
            </button>
          </div>

          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
            <button
              type="button"
              data-testid="qif-preview-button"
              onClick={() => {
                void handlePreview();
              }}
              disabled={!canPreview}
              style={{
                ...buttonStyle,
                opacity: canPreview ? 1 : 0.6,
                cursor: canPreview ? 'pointer' : 'not-allowed',
              }}
            >
              {status === 'previewing' ? 'Loading…' : 'Load QIF'}
            </button>
          </div>
        </>
      )}

      {browsing && (
        <FileBrowser onSelect={handleFileSelected} onCancel={() => setBrowsing(false)} />
      )}

      {status === 'preview' && preview ? (
        <>
          <div style={{ display: 'grid', gap: '0.5rem' }}>
            <div style={{ fontWeight: 600 }}>
              Accounts found: {preview.accounts.length} · Selected: {selectedAccounts.size}
            </div>
            <div style={secondaryTextStyle}>Position-only import: {preview.position_only ? 'Yes' : 'No'}</div>
            <div style={{ display: 'flex', gap: '0.75rem', fontSize: '0.85rem' }}>
              <button
                type="button"
                data-testid="qif-select-all"
                onClick={() => setSelectedAccounts(new Set(preview.accounts.map((a) => a.name)))}
                style={{ ...secondaryButtonStyle, padding: '0.35rem 0.65rem', fontSize: '0.85rem' }}
              >
                Select all
              </button>
              <button
                type="button"
                data-testid="qif-select-none"
                onClick={() => setSelectedAccounts(new Set())}
                style={{ ...secondaryButtonStyle, padding: '0.35rem 0.65rem', fontSize: '0.85rem' }}
              >
                Select none
              </button>
            </div>
          </div>

          <div data-testid="qif-preview-accounts" style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {preview.accounts.map((account) => {
              const checked = selectedAccounts.has(account.name);
              return (
                <label
                  key={`${account.name}-${account.account_type}`}
                  style={{
                    border: `1px solid ${checked ? '#93c5fd' : '#e5e7eb'}`,
                    borderRadius: 10,
                    padding: '0.85rem',
                    background: checked ? '#eff6ff' : '#f9fafb',
                    display: 'flex',
                    gap: '0.75rem',
                    cursor: 'pointer',
                    alignItems: 'flex-start',
                  }}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => {
                      setSelectedAccounts((prev) => {
                        const next = new Set(prev);
                        if (next.has(account.name)) {
                          next.delete(account.name);
                        } else {
                          next.add(account.name);
                        }
                        return next;
                      });
                    }}
                    style={{ marginTop: '0.2rem' }}
                  />
                  <div>
                    <div style={{ fontWeight: 600 }}>{account.name}</div>
                    <div style={secondaryTextStyle}>Type: {account.account_type}</div>
                    <div style={secondaryTextStyle}>Tax lots: {account.tax_lots.length}</div>
                    <div style={secondaryTextStyle}>Cash holdings: {account.cash_holdings.length}</div>
                  </div>
                </label>
              );
            })}
          </div>

          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
            <button
              type="button"
              data-testid="qif-confirm-button"
              disabled={selectedAccounts.size === 0}
              onClick={() => {
                void handleConfirm();
              }}
              style={{
                ...buttonStyle,
                opacity: selectedAccounts.size === 0 ? 0.6 : 1,
                cursor: selectedAccounts.size === 0 ? 'not-allowed' : 'pointer',
              }}
            >
              Confirm ({selectedAccounts.size} accounts)
            </button>
            <button type="button" data-testid="qif-cancel-button" onClick={handleCancel} style={secondaryButtonStyle}>
              Cancel
            </button>
          </div>
        </>
      ) : null}

      {status === 'saving' ? <div style={{ fontWeight: 600 }}>Saving…</div> : null}

      {status === 'done' ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          <div data-testid="qif-success" style={{ border: '1px solid #bbf7d0', borderRadius: 10, background: '#f0fdf4', color: '#166534', padding: '0.85rem' }}>
            QIF source configured. Portfolio will be parsed fresh from the QIF file on each load.
          </div>
          <div>
            <button type="button" onClick={onImported} style={buttonStyle}>
              View Portfolio
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
