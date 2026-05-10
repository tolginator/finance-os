import { useEffect, useState } from 'react';
import { classifyMacroRegime } from '../api';
import type { MacroRegimeResponse } from '../types';

type LoadState =
  | { status: 'loading' }
  | { status: 'error'; error: string }
  | { status: 'loaded'; data: MacroRegimeResponse };

export function MacroDashboard() {
  const [state, setState] = useState<LoadState>({ status: 'loading' });

  useEffect(() => {
    let cancelled = false;

    async function loadRegime() {
      try {
        const data = await classifyMacroRegime();
        if (cancelled) return;
        setState({ status: 'loaded', data });
      } catch (error) {
        if (cancelled) return;
        setState({
          status: 'error',
          error: error instanceof Error ? error.message : 'Unable to load macro regime.',
        });
      }
    }

    loadRegime();

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div data-testid="macro-dashboard" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {state.status === 'loading' && (
        <div
          data-testid="macro-loading"
          style={{ border: '1px solid #e5e7eb', borderRadius: 12, padding: '1rem', background: '#fff' }}
        >
          Loading macro regime…
        </div>
      )}

      {state.status === 'error' && (
        <div
          data-testid="macro-error"
          style={{ border: '1px solid #fecaca', borderRadius: 12, padding: '1rem', background: '#fef2f2', color: '#b91c1c' }}
        >
          {state.error}
        </div>
      )}

      {state.status === 'loaded' && (
        <>
          <div style={{ border: '1px solid #e5e7eb', borderRadius: 12, padding: '1rem', background: '#fff' }}>
            <div style={{ fontSize: '0.85rem', color: '#6b7280', marginBottom: '0.25rem' }}>Current regime</div>
            <div data-testid="macro-regime" style={{ fontSize: '1.4rem', fontWeight: 700 }}>
              {state.data.regime}
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.75rem' }}>
            <div style={{ border: '1px solid #e5e7eb', borderRadius: 12, padding: '1rem', background: '#fff' }}>
              <div style={{ fontSize: '0.85rem', color: '#6b7280', marginBottom: '0.25rem' }}>Indicators fetched</div>
              <div style={{ fontSize: '1.1rem', fontWeight: 600 }}>{state.data.indicators_fetched}</div>
            </div>
            <div style={{ border: '1px solid #e5e7eb', borderRadius: 12, padding: '1rem', background: '#fff' }}>
              <div style={{ fontSize: '0.85rem', color: '#6b7280', marginBottom: '0.25rem' }}>Indicators with data</div>
              <div style={{ fontSize: '1.1rem', fontWeight: 600 }}>{state.data.indicators_with_data}</div>
            </div>
          </div>

          <div
            data-testid="macro-content"
            style={{ border: '1px solid #e5e7eb', borderRadius: 12, padding: '1rem', background: '#fff', whiteSpace: 'pre-wrap' }}
          >
            {state.data.content}
          </div>
        </>
      )}
    </div>
  );
}
