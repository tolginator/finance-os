import { useState } from 'react';
import { previewQifImport, saveHousehold } from '../api';
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

function readFileAsText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === 'string') {
        resolve(reader.result);
        return;
      }
      reject(new Error('Unable to read selected file.'));
    };
    reader.onerror = () => {
      reject(reader.error ?? new Error('Unable to read selected file.'));
    };
    reader.readAsText(file);
  });
}

export function QifImporter({ onImported }: QifImporterProps) {
  const [status, setStatus] = useState<ImportStatus>('idle');
  const [householdName, setHouseholdName] = useState('My Household');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreviewResponse | null>(null);
  const [journalEntry, setJournalEntry] = useState('');
  const [error, setError] = useState('');
  const [fileInputKey, setFileInputKey] = useState(0);

  const canPreview = selectedFile !== null && status !== 'previewing' && status !== 'saving';
  const normalizedHouseholdName = householdName.trim() || 'My Household';

  async function handlePreview() {
    if (selectedFile === null) return;

    setError('');
    setStatus('previewing');

    try {
      const qifContent = await readFileAsText(selectedFile);
      const response = await previewQifImport(qifContent, normalizedHouseholdName);
      setPreview(response);
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
      const response = await saveHousehold({
        name: normalizedHouseholdName,
        accounts: preview.accounts,
        liquidity_reserve_floor: '0',
        expected_revision: 0,
      });
      setJournalEntry(response.journal_entry);
      setStatus('done');
    } catch (saveError) {
      setStatus('preview');
      setError(saveError instanceof Error ? saveError.message : 'Unable to save imported household.');
    }
  }

  function handleCancel() {
    setStatus('idle');
    setPreview(null);
    setSelectedFile(null);
    setJournalEntry('');
    setError('');
    setFileInputKey((current) => current + 1);
  }

  return (
    <div data-testid="qif-importer" style={{ ...panelStyle, display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
        <div style={{ fontSize: '1rem', fontWeight: 700 }}>Import a QIF file</div>
        <div style={secondaryTextStyle}>Preview parsed accounts before saving them to your household portfolio.</div>
      </div>

      {error ? (
        <div style={{ border: '1px solid #fecaca', borderRadius: 10, background: '#fef2f2', color: '#b91c1c', padding: '0.75rem' }}>
          {error}
        </div>
      ) : null}

      {(status === 'idle' || status === 'previewing') && (
        <>
          <label style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
            <span style={{ fontWeight: 600 }}>Household name</span>
            <input
              data-testid="qif-household-name"
              type="text"
              value={householdName}
              onChange={(event) => setHouseholdName(event.target.value)}
              style={{ border: '1px solid #d1d5db', borderRadius: 10, padding: '0.7rem 0.85rem', font: 'inherit' }}
            />
          </label>

          <label style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
            <span style={{ fontWeight: 600 }}>QIF file</span>
            <input
              key={fileInputKey}
              data-testid="qif-file-input"
              type="file"
              accept=".qif"
              onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
              style={{ font: 'inherit' }}
            />
          </label>

          {selectedFile ? <div style={secondaryTextStyle}>Selected file: {selectedFile.name}</div> : null}

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
              {status === 'previewing' ? 'Previewing…' : 'Preview Import'}
            </button>
          </div>
        </>
      )}

      {status === 'preview' && preview ? (
        <>
          <div style={{ display: 'grid', gap: '0.5rem' }}>
            <div style={{ fontWeight: 600 }}>Accounts found: {preview.accounts.length}</div>
            <div style={secondaryTextStyle}>Position-only import: {preview.position_only ? 'Yes' : 'No'}</div>
          </div>

          <div data-testid="qif-preview-accounts" style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {preview.accounts.map((account) => (
              <div
                key={`${account.name}-${account.account_type}`}
                style={{ border: '1px solid #e5e7eb', borderRadius: 10, padding: '0.85rem', background: '#f9fafb' }}
              >
                <div style={{ fontWeight: 600 }}>{account.name}</div>
                <div style={secondaryTextStyle}>Type: {account.account_type}</div>
                <div style={secondaryTextStyle}>Tax lots: {account.tax_lots.length}</div>
                <div style={secondaryTextStyle}>Cash holdings: {account.cash_holdings.length}</div>
              </div>
            ))}
          </div>

          {preview.warnings.length > 0 ? (
            <div data-testid="qif-preview-warnings" style={{ border: '1px solid #fde68a', borderRadius: 10, background: '#fffbeb', padding: '0.85rem' }}>
              <div style={{ fontWeight: 600, marginBottom: '0.5rem' }}>Warnings</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', ...secondaryTextStyle }}>
                {preview.warnings.map((warning, index) => (
                  <div key={`${warning.line ?? 'general'}-${index}`}>
                    {warning.line === null ? warning.message : `Line ${warning.line}: ${warning.message}`}
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
            <button
              type="button"
              data-testid="qif-confirm-button"
              onClick={() => {
                void handleConfirm();
              }}
              style={buttonStyle}
            >
              Confirm Import
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
            {journalEntry}
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
