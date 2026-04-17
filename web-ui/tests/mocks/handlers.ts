import { http, HttpResponse } from 'msw';

export const handlers = [
  http.get('/api/health', () => {
    return HttpResponse.json({ status: 'ok' });
  }),

  http.get('/api/agents', () => {
    return HttpResponse.json([
      { name: 'earnings_interpreter', description: 'Analyzes earnings call transcripts for sentiment and guidance' },
      { name: 'macro_regime', description: 'Classifies macro regime from FRED indicators' },
      { name: 'filing_analyst', description: 'Searches and analyzes SEC filings' },
      { name: 'quant_signal', description: 'Generates composite quant signals from multiple inputs' },
      { name: 'thesis_guardian', description: 'Evaluates investment theses against observed data' },
      { name: 'risk_analyst', description: 'Assesses portfolio risk with VaR, CVaR, and scenario analysis' },
      { name: 'adversarial', description: 'Challenges investment theses adversarially' },
    ]);
  }),

  http.post('/api/digest', async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    const tickers = body.tickers as string[];
    return HttpResponse.json({
      ticker_count: tickers.length,
      entry_count: 3,
      alert_count: 1,
      material_count: 1,
      content: `Digest for ${tickers.join(', ')}`,
    });
  }),

  // --- Watchlists ---

  http.get('/api/watchlists', () => {
    return HttpResponse.json({
      active: 'default',
      watchlists: { default: { tickers: [] } },
      active_watchlist: { tickers: [] },
    });
  }),

  http.put('/api/watchlists/:name', () => {
    return HttpResponse.json({ tickers: ['AAPL', 'MSFT'] });
  }),

  http.post('/api/watchlists', () => {
    return HttpResponse.json({ tickers: [] }, { status: 201 });
  }),

  http.delete('/api/watchlists/:name', () => {
    return new HttpResponse(null, { status: 204 });
  }),

  http.put('/api/watchlists/:name/activate', ({ params }) => {
    const name = params.name as string;
    return HttpResponse.json({
      active: name,
      watchlist: { tickers: ['AAPL', 'MSFT'] },
    });
  }),

  // --- Agent endpoints ---

  http.post('/api/agents/earnings_interpreter', () => {
    return HttpResponse.json({
      content: 'Earnings analysis report',
      tone: 'cautiously optimistic',
      net_sentiment: 0.65,
      confidence: 'high',
      guidance_direction: 'raised',
      guidance_count: 3,
      key_phrase_count: 12,
    });
  }),

  http.post('/api/agents/macro_regime', () => {
    return HttpResponse.json({
      content: 'Macro regime dashboard',
      regime: 'expansion',
      indicators_fetched: 5,
      indicators_with_data: 4,
    });
  }),

  http.post('/api/agents/filing_analyst', () => {
    return HttpResponse.json({
      content: 'Filing search results',
      cik: '0000320193',
      form_type: '10-K',
      filing_count: 5,
    });
  }),

  http.post('/api/agents/quant_signal', () => {
    return HttpResponse.json({
      content: 'Signal report',
      agent: 'quant_signal',
      composite: { score: 0.72, direction: 'long' },
      signals: [{ name: 'momentum', value: 0.8 }],
    });
  }),

  http.post('/api/agents/thesis_guardian', () => {
    return HttpResponse.json({
      content: 'Thesis evaluation report',
      theses_checked: 2,
      alerts_generated: 1,
      critical_alerts: 0,
    });
  }),

  http.post('/api/agents/risk_analyst', () => {
    return HttpResponse.json({
      content: 'Risk analysis report',
    });
  }),

  http.post('/api/agents/adversarial', () => {
    return HttpResponse.json({
      content: 'Adversarial challenge report',
      conviction_score: 'medium',
      counter_count: 4,
      blind_spot_count: 2,
    });
  }),

  // --- Pipeline ---

  http.post('/api/pipeline', () => {
    return HttpResponse.json({
      results: [{ task_id: 'task-1', agent_name: 'macro_regime', success: true, duration_ms: 1200, content: 'Macro regime dashboard', metadata: {}, error: null }],
      total_duration_ms: 1500,
      successful: 1,
      failed: 0,
      memo: null,
    });
  }),

  // --- Knowledge Graph ---

  http.post('/api/kg/extract', () => {
    return HttpResponse.json({
      entities: [
        { entity_id: 'company:apple inc', name: 'Apple Inc', entity_type: 'company', ticker: 'AAPL', cik: null, metadata: {} },
        { entity_id: 'company:intel corp', name: 'Intel Corp', entity_type: 'company', ticker: 'INTC', cik: null, metadata: {} },
      ],
      relationships: [
        { source_id: 'company:apple inc', target_id: 'company:intel corp', rel_type: 'supplies_to', evidence: 'Intel supplies chips', source_doc: '', confidence: '0.8', metadata: {} },
      ],
      entity_count: 2,
      relationship_count: 1,
    });
  }),

  http.post('/api/kg/query/related', () => {
    return HttpResponse.json({
      entity_id: 'company:apple inc',
      related: [
        { entity_id: 'company:intel corp', name: 'Intel Corp', entity_type: 'company', ticker: 'INTC', cik: null, metadata: {} },
      ],
      count: 1,
    });
  }),

  http.post('/api/kg/query/supply-chain', () => {
    return HttpResponse.json({
      entity_id: 'company:apple inc',
      direction: 'upstream',
      chain: [
        { entity_id: 'company:tsmc', name: 'TSMC', entity_type: 'company', ticker: 'TSM', cik: null, metadata: {} },
      ],
      count: 1,
    });
  }),

  http.post('/api/kg/query/shared-risks', () => {
    return HttpResponse.json({
      entity_ids: ['company:apple inc', 'company:intel corp'],
      shared_risks: [
        { entity_id: 'risk:chip-shortage', name: 'Global chip shortage', entity_type: 'risk', ticker: null, cik: null, metadata: {} },
      ],
      count: 1,
    });
  }),

  http.get('/api/kg/stats', () => {
    return HttpResponse.json({
      entity_count: 15,
      relationship_count: 22,
      entities_by_type: { company: 10, risk: 3, sector: 2 },
      relationships_by_type: { supplies_to: 12, competes_with: 6, exposed_to: 4 },
    });
  }),
];
