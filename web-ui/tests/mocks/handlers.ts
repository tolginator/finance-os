import { http, HttpResponse } from 'msw';

export const handlers = [
  http.get('/api/health', () => HttpResponse.json({ status: 'ok' })),

  http.get('/api/filesystem/browse', () =>
    HttpResponse.json({
      current: '/home/user',
      parent: '/home',
      entries: [
        { name: 'Documents', path: '/home/user/Documents', is_dir: true },
        { name: 'portfolio.qif', path: '/home/user/portfolio.qif', is_dir: false },
      ],
    }),
  ),

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

  http.get('/api/household', () =>
    HttpResponse.json({
      exists: true,
      household: {
        name: 'Test Household',
        members: [],
        liquidity_reserve_floor: '25000',
        tax_year: null,
        accounts: [
          {
            name: 'Primary Brokerage',
            account_type: 'taxable',
            owner: null,
            beneficiary: null,
            institution: null,
            tax_lots: [
              {
                ticker: 'VTI',
                shares: '10',
                cost_basis_per_share: '250.00',
                purchase_date: '2024-01-10',
              },
            ],
            cash_holdings: [
              {
                amount: '5000',
                valuation_date: '2025-02-14',
                is_money_market: true,
                ticker: null,
                counts_toward_liquidity_reserve: true,
              },
            ],
            withdrawal_restrictions: [],
          },
        ],
      },
    }),
  ),

  http.post('/api/household/import/qif/preview', async ({ request }) => {
    const body = (await request.json()) as { qif_content: string; household_name: string };
    return HttpResponse.json({
      accounts: [
        {
          name: 'Investment Account',
          account_type: 'taxable',
          tax_lots: [
            {
              ticker: 'VTI',
              shares: '100',
              cost_basis_per_share: '200.00',
              purchase_date: '2024-01-15',
            },
          ],
          cash_holdings: [],
        },
      ],
      warnings: body.qif_content.includes('warning') ? [{ line: 7, message: 'Parser warning' }] : [],
      position_only: false,
    });
  }),

  http.post('/api/household/qif_source', () =>
    HttpResponse.json({ qif_source_path: '/path/to/test.qif' }),
  ),

  http.put('/api/household/excluded_accounts', () =>
    HttpResponse.json({ excluded_accounts: [] }),
  ),

  http.post('/api/agents/macro_regime', () =>
    HttpResponse.json({
      regime: 'Balanced slowdown',
      indicators_fetched: 6,
      indicators_with_data: 5,
      content: 'Macro regime classification completed.',
    }),
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
