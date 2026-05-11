import { useState } from 'react';
import { setQifSource, setExcludedAccounts } from '../api';
import type { ImportPreviewResponse } from '../types';

interface QifImporterProps {
  onImported: () => void;
}

type ImportStatus = 'idle' | 'previewing' | 'preview' | 'saving' | 'done';

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

export function QifImporter({ onImported }: QifImporterProps) {
  const [status, setStatus] = useState<ImportStatus>('idle');
  const [qifPath, setQifPath] = useState('');
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
      // Set the QIF source path in config, which validates the file exists.
      await setQifSource(trimmed);

      // Now read the file server-side via the preview endpoint using the
      // configured path. We use a GET to /household which parses from config.
      // But first we need to preview — use the import preview endpoint.
      // Read the file content server-side by fetching household (which now
      // parses QIF from the configured path).
      const response = await fetch('/api/household');
      if (!response.ok) throw new Error('Failed to load household from QIF.');
      const data = await response.json();
      if (!data.exists) throw new Error('QIF file could not be parsed.');

      // Build preview-like response from the household data.
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
      // Store excluded accounts (those NOT selected) in config.
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

  return (
    <div data-testid="qif-importer" style={{ ...panelStyle, display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
        <div style={{ fontSize: '1rem', fontWeight: 700 }}>Import a QIF file</div>
        <div style={secondaryTextStyle}>Enter the path to your QIF file on the server. It will be parsed fresh on every load.</div>
      </div>

      {error ? (
        <div style={{ border: '1px solid #fecaca', borderRadius: 10, background: '#fef2f2', color: '#b91c1c', padding: '0.75rem' }}>
          {error}
        </div>
      ) : null}

      {(status === 'idle' || status === 'previewing') && (
        <>
          <label style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
            <span style={{ fontWeight: 600 }}>QIF file path</span>
            <input
              data-testid="qif-path-input"
              type="text"
              value={qifPath}
              onChange={(event) => setQifPath(event.target.value)}
              placeholder="/path/to/portfolio.qif"
              style={{ border: '1px solid #d1d5db', borderRadius: 10, padding: '0.7rem 0.85rem', font: 'inherit' }}
            />
          </label>

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
