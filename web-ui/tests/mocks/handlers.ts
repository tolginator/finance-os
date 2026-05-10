import { http, HttpResponse } from 'msw';

export const handlers = [
  http.get('/api/health', () => HttpResponse.json({ status: 'ok' })),

  http.get('/api/agents', () =>
    HttpResponse.json([
      { name: 'earnings_interpreter', description: 'Analyzes earnings call transcripts for sentiment and guidance' },
      { name: 'macro_regime', description: 'Classifies macro regime from FRED indicators' },
      { name: 'macro_outlook', description: 'Computes asset-class tilts from macro regime' },
      { name: 'filing_analyst', description: 'Searches and analyzes SEC filings' },
      { name: 'quant_signal', description: 'Generates composite quant signals from multiple inputs' },
      { name: 'thesis_guardian', description: 'Evaluates investment theses against observed data' },
      { name: 'risk_analyst', description: 'Assesses portfolio risk with VaR, CVaR, and scenario analysis' },
      { name: 'adversarial', description: 'Challenges investment theses adversarially' },
    ]),
  ),

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

  http.get('/api/watchlists', () =>
    HttpResponse.json({
      active: 'default',
      watchlists: { default: { tickers: [] } },
      active_watchlist: { tickers: [] },
    }),
  ),

  http.put('/api/watchlists/:name', () => HttpResponse.json({ tickers: ['AAPL', 'MSFT'] })),
  http.post('/api/watchlists', () => HttpResponse.json({ tickers: [] }, { status: 201 })),
  http.delete('/api/watchlists/:name', () => new HttpResponse(null, { status: 204 })),

  http.put('/api/watchlists/:name/activate', ({ params }) => {
    const name = String(params.name);
    return HttpResponse.json({
      active: name,
      watchlist: { tickers: ['AAPL', 'MSFT'] },
    });
  }),

  http.post('/api/pipeline', () =>
    HttpResponse.json({
      results: [
        {
          task_id: 'task-1',
          agent_name: 'macro_regime',
          success: true,
          duration_ms: 1200,
          content: 'Macro regime dashboard',
          metadata: {},
          error: null,
        },
      ],
      total_duration_ms: 1500,
      successful: 1,
      failed: 0,
      memo: null,
    }),
  ),
];
