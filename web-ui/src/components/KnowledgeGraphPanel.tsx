import { useCallback, useState } from 'react';
import { extractEntities, fetchKGStats, queryRelated, querySharedRisks, querySupplyChain } from '../api';
import type {
  EntityModel, ExtractEntitiesResponse, KGStatsResponse,
  QueryRelatedResponse, QuerySharedRisksResponse, QuerySupplyChainResponse,
} from '../types';

type QueryTab = 'related' | 'supply-chain' | 'shared-risks';

export function KnowledgeGraphPanel() {
  const [text, setText] = useState('');
  const [sourceDoc, setSourceDoc] = useState('');
  const [ticker, setTicker] = useState('');
  const [extraction, setExtraction] = useState<ExtractEntitiesResponse | null>(null);
  const [extracting, setExtracting] = useState(false);
  const [error, setError] = useState('');

  const [queryTab, setQueryTab] = useState<QueryTab>('related');
  const [selectedEntity, setSelectedEntity] = useState('');
  const [queryDirection, setQueryDirection] = useState<'upstream' | 'downstream'>('upstream');
  const [selectedEntities, setSelectedEntities] = useState<string[]>([]);
  const [queryResult, setQueryResult] = useState<QueryRelatedResponse | QuerySupplyChainResponse | QuerySharedRisksResponse | null>(null);
  const [querying, setQuerying] = useState(false);
  const [queryError, setQueryError] = useState('');

  const [stats, setStats] = useState<KGStatsResponse | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);

  const allEntities: EntityModel[] = extraction?.entities ?? [];

  const handleExtract = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim()) {
      setError('Enter text to extract entities from.');
      setExtraction(null);
      setQueryResult(null);
      setSelectedEntities([]);
      setSelectedEntity('');
      setQueryError('');
      return;
    }
    setError('');
    setExtraction(null);
    setQueryResult(null);
    setSelectedEntities([]);
    setSelectedEntity('');
    setQueryError('');
    setExtracting(true);
    try {
      const resp = await extractEntities({
        text: text.trim(),
        source_doc: sourceDoc.trim() || undefined,
        ticker: ticker.trim() || undefined,
      });
      setExtraction(resp);
      if (resp.entities.length > 0) {
        setSelectedEntity(resp.entities[0].entity_id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Extraction failed');
    } finally {
      setExtracting(false);
    }
  };

  const handleQuery = async () => {
    setQueryError('');
    setQueryResult(null);
    setQuerying(true);
    try {
      if (queryTab === 'related') {
        if (!selectedEntity) { setQueryError('Select an entity.'); setQuerying(false); return; }
        const resp = await queryRelated({ entity_id: selectedEntity });
        setQueryResult(resp);
      } else if (queryTab === 'supply-chain') {
        if (!selectedEntity) { setQueryError('Select an entity.'); setQuerying(false); return; }
        const resp = await querySupplyChain({ entity_id: selectedEntity, direction: queryDirection });
        setQueryResult(resp);
      } else {
        if (selectedEntities.length < 2) { setQueryError('Select at least 2 entities.'); setQuerying(false); return; }
        const resp = await querySharedRisks({ entity_ids: selectedEntities });
        setQueryResult(resp);
      }
    } catch (err) {
      setQueryError(err instanceof Error ? err.message : 'Query failed');
    } finally {
      setQuerying(false);
    }
  };

  const handleRefreshStats = useCallback(async () => {
    setStatsLoading(true);
    try {
      const resp = await fetchKGStats();
      setStats(resp);
    } catch {
      /* stats are best-effort */
    } finally {
      setStatsLoading(false);
    }
  }, []);

  const toggleEntitySelection = (entityId: string) => {
    setSelectedEntities((prev) =>
      prev.includes(entityId) ? prev.filter((id) => id !== entityId) : [...prev, entityId],
    );
  };

  return (
    <div>
      {/* Extract Section */}
      <form onSubmit={handleExtract} style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Paste text to extract entities and relationships..."
          rows={4}
          style={{ padding: '0.5rem', border: '1px solid #d1d5db', borderRadius: 6, resize: 'vertical' }}
        />
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <input
            type="text"
            value={sourceDoc}
            onChange={(e) => setSourceDoc(e.target.value)}
            placeholder="Source document (optional)"
            style={{ flex: 1, padding: '0.5rem', border: '1px solid #d1d5db', borderRadius: 6 }}
          />
          <input
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            placeholder="Ticker (optional)"
            style={{ width: 100, padding: '0.5rem', border: '1px solid #d1d5db', borderRadius: 6 }}
          />
          <button
            type="submit"
            disabled={extracting}
            style={{
              padding: '0.5rem 1rem', backgroundColor: '#2563eb', color: 'white',
              borderRadius: 6, border: 'none', cursor: extracting ? 'wait' : 'pointer',
            }}
          >
            {extracting ? 'Extracting…' : 'Extract'}
          </button>
        </div>
      </form>

      {error && <p data-testid="kg-error" style={{ color: '#ef4444', marginTop: '0.5rem' }}>{error}</p>}

      {/* Extraction Results */}
      {extraction && (
        <div data-testid="kg-extraction" style={{ marginTop: '1rem' }}>
          <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.9rem' }}>
            Entities ({extraction.entity_count}) · Relationships ({extraction.relationship_count})
          </h4>

          {extraction.entities.length > 0 && (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem', marginBottom: '0.75rem' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #e5e7eb', textAlign: 'left' }}>
                  <th style={{ padding: '0.25rem 0.5rem' }}>Name</th>
                  <th style={{ padding: '0.25rem 0.5rem' }}>Type</th>
                  <th style={{ padding: '0.25rem 0.5rem' }}>Ticker</th>
                  <th style={{ padding: '0.25rem 0.5rem' }}>ID</th>
                </tr>
              </thead>
              <tbody>
                {extraction.entities.map((e) => (
                  <tr key={e.entity_id} style={{ borderBottom: '1px solid #f3f4f6' }}>
                    <td style={{ padding: '0.25rem 0.5rem' }}>{e.name}</td>
                    <td style={{ padding: '0.25rem 0.5rem' }}>{e.entity_type}</td>
                    <td style={{ padding: '0.25rem 0.5rem' }}>{e.ticker ?? '—'}</td>
                    <td style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem', color: '#6b7280' }}>{e.entity_id}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {extraction.relationships.length > 0 && (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #e5e7eb', textAlign: 'left' }}>
                  <th style={{ padding: '0.25rem 0.5rem' }}>Source</th>
                  <th style={{ padding: '0.25rem 0.5rem' }}>Relationship</th>
                  <th style={{ padding: '0.25rem 0.5rem' }}>Target</th>
                  <th style={{ padding: '0.25rem 0.5rem' }}>Confidence</th>
                </tr>
              </thead>
              <tbody>
                {extraction.relationships.map((r) => (
                  <tr key={`${r.source_id}:${r.rel_type}:${r.target_id}`} style={{ borderBottom: '1px solid #f3f4f6' }}>
                    <td style={{ padding: '0.25rem 0.5rem' }}>{r.source_id}</td>
                    <td style={{ padding: '0.25rem 0.5rem' }}>{r.rel_type}</td>
                    <td style={{ padding: '0.25rem 0.5rem' }}>{r.target_id}</td>
                    <td style={{ padding: '0.25rem 0.5rem' }}>{r.confidence}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Query Section — only show when entities exist */}
      {allEntities.length > 0 && (
        <div style={{ marginTop: '1rem', padding: '0.75rem', border: '1px solid #e5e7eb', borderRadius: 6 }}>
          <div role="tablist" aria-label="Knowledge graph queries" style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.75rem' }}>
            {(['related', 'supply-chain', 'shared-risks'] as QueryTab[]).map((tab) => (
              <button
                key={tab}
                type="button"
                role="tab"
                aria-selected={queryTab === tab}
                onClick={() => { setQueryTab(tab); setQueryResult(null); setQueryError(''); }}
                style={{
                  padding: '0.25rem 0.75rem', borderRadius: 4, border: '1px solid #d1d5db',
                  background: queryTab === tab ? '#eff6ff' : 'white', cursor: 'pointer',
                  fontWeight: queryTab === tab ? 600 : 400, fontSize: '0.85rem',
                }}
              >
                {tab === 'related' ? 'Related' : tab === 'supply-chain' ? 'Supply Chain' : 'Shared Risks'}
              </button>
            ))}
          </div>

          {queryTab !== 'shared-risks' ? (
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <select
                value={selectedEntity}
                onChange={(e) => setSelectedEntity(e.target.value)}
                style={{ flex: 1, padding: '0.4rem', border: '1px solid #d1d5db', borderRadius: 4 }}
                data-testid="entity-select"
              >
                {allEntities.map((e) => (
                  <option key={e.entity_id} value={e.entity_id}>{e.name} ({e.entity_type})</option>
                ))}
              </select>
              {queryTab === 'supply-chain' && (
                <select
                  value={queryDirection}
                  onChange={(e) => setQueryDirection(e.target.value as 'upstream' | 'downstream')}
                  style={{ padding: '0.4rem', border: '1px solid #d1d5db', borderRadius: 4 }}
                >
                  <option value="upstream">Upstream</option>
                  <option value="downstream">Downstream</option>
                </select>
              )}
              <button
                type="button"
                onClick={handleQuery}
                disabled={querying}
                style={{
                  padding: '0.4rem 0.75rem', backgroundColor: '#2563eb', color: 'white',
                  borderRadius: 4, border: 'none', cursor: querying ? 'wait' : 'pointer', fontSize: '0.85rem',
                }}
              >
                {querying ? 'Querying…' : 'Query'}
              </button>
            </div>
          ) : (
            <div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.25rem', marginBottom: '0.5rem' }}>
                {allEntities.map((e) => (
                  <label key={e.entity_id} style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.85rem' }}>
                    <input
                      type="checkbox"
                      checked={selectedEntities.includes(e.entity_id)}
                      onChange={() => toggleEntitySelection(e.entity_id)}
                    />
                    {e.name}
                  </label>
                ))}
              </div>
              <button
                type="button"
                onClick={handleQuery}
                disabled={querying || selectedEntities.length < 2}
                style={{
                  padding: '0.4rem 0.75rem', backgroundColor: '#2563eb', color: 'white',
                  borderRadius: 4, border: 'none', cursor: querying ? 'wait' : 'pointer', fontSize: '0.85rem',
                }}
              >
                {querying ? 'Querying…' : 'Find Shared Risks'}
              </button>
            </div>
          )}

          {queryError && <p data-testid="kg-query-error" style={{ color: '#ef4444', marginTop: '0.5rem' }}>{queryError}</p>}

          {queryResult && (
            <div data-testid="kg-query-result" style={{ marginTop: '0.75rem' }}>
              <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.85rem' }}>
                {'count' in queryResult ? `Results: ${queryResult.count}` : 'Results'}
              </h4>
              {renderQueryEntities(queryResult)}
            </div>
          )}
        </div>
      )}

      {/* Stats Section */}
      <div style={{ marginTop: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <button
          type="button"
          onClick={handleRefreshStats}
          disabled={statsLoading}
          style={{
            padding: '0.4rem 0.75rem', border: '1px solid #d1d5db', borderRadius: 4,
            background: 'white', cursor: statsLoading ? 'wait' : 'pointer', fontSize: '0.85rem',
          }}
        >
          {statsLoading ? 'Loading…' : 'Refresh Stats'}
        </button>
        {stats && (
          <span data-testid="kg-stats" style={{ fontSize: '0.85rem', color: '#6b7280' }}>
            {stats.entity_count} entities · {stats.relationship_count} relationships
          </span>
        )}
      </div>
    </div>
  );
}

function renderQueryEntities(result: QueryRelatedResponse | QuerySupplyChainResponse | QuerySharedRisksResponse) {
  const entities: EntityModel[] =
    'related' in result ? result.related :
    'chain' in result ? result.chain :
    'shared_risks' in result ? result.shared_risks : [];

  if (entities.length === 0) return <p style={{ color: '#6b7280', fontSize: '0.85rem' }}>No results found.</p>;

  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
      <thead>
        <tr style={{ borderBottom: '2px solid #e5e7eb', textAlign: 'left' }}>
          <th style={{ padding: '0.25rem 0.5rem' }}>Name</th>
          <th style={{ padding: '0.25rem 0.5rem' }}>Type</th>
          <th style={{ padding: '0.25rem 0.5rem' }}>Ticker</th>
        </tr>
      </thead>
      <tbody>
        {entities.map((e) => (
          <tr key={e.entity_id} style={{ borderBottom: '1px solid #f3f4f6' }}>
            <td style={{ padding: '0.25rem 0.5rem' }}>{e.name}</td>
            <td style={{ padding: '0.25rem 0.5rem' }}>{e.entity_type}</td>
            <td style={{ padding: '0.25rem 0.5rem' }}>{e.ticker ?? '—'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
