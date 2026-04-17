import { http, HttpResponse } from 'msw';

export const handlers = [
  http.get('/api/health', () => {
    return HttpResponse.json({ status: 'ok' });
  }),

  http.get('/api/agents', () => {
    return HttpResponse.json([
      { name: 'macro_regime', description: 'Classifies macro regime from FRED indicators' },
      { name: 'filing_analyst', description: 'Searches and analyzes SEC filings' },
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
];
