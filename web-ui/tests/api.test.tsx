import { describe, expect, it } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from './mocks/server';
import {
  activateWatchlist,
  createWatchlist,
  deleteWatchlist,
  fetchAgents,
  fetchHealth,
  fetchWatchlists,
  normalizeDetail,
  previewQifImport,
  runDigest,
  runPipeline,
  saveHousehold,
  updateWatchlist,
} from '../src/api';

describe('normalizeDetail', () => {
  it('returns string detail as-is', () => {
    expect(normalizeDetail('Not found')).toBe('Not found');
  });

  it('formats validation arrays', () => {
    const detail = [{ loc: ['body', 'tasks', 0, 'agent_name'], msg: 'field required' }];
    expect(normalizeDetail(detail)).toBe('body → tasks → 0 → agent_name: field required');
  });

  it('stringifies object detail', () => {
    expect(normalizeDetail({ error: 'bad' })).toBe('{"error":"bad"}');
  });
});

describe('api helpers', () => {
  it('fetches health', async () => {
    await expect(fetchHealth()).resolves.toEqual({ status: 'ok' });
  });

  it('fetches agents', async () => {
    const agents = await fetchAgents();
    expect(agents.length).toBeGreaterThan(0);
    expect(agents.some((agent) => agent.name === 'macro_regime')).toBe(true);
  });

  it('runs digest', async () => {
    const response = await runDigest({ tickers: ['AAPL', 'MSFT'] });
    expect(response.ticker_count).toBe(2);
    expect(response.content).toContain('AAPL, MSFT');
  });

  it('manages watchlists', async () => {
    await expect(fetchWatchlists()).resolves.toMatchObject({ active: 'default' });
    await expect(updateWatchlist('default', ['AAPL'])).resolves.toEqual({ tickers: ['AAPL', 'MSFT'] });
    await expect(createWatchlist('growth', ['VTI'])).resolves.toEqual({ tickers: [] });
    await expect(activateWatchlist('default')).resolves.toMatchObject({ active: 'default' });
    await expect(deleteWatchlist('growth')).resolves.toBeUndefined();
  });

  it('previews qif imports and saves households', async () => {
    await expect(previewQifImport('!Type:Invst\n^', 'My Household')).resolves.toMatchObject({
      accounts: [{ name: 'Investment Account' }],
      warnings: [],
      position_only: false,
    });

    await expect(
      saveHousehold({
        name: 'My Household',
        accounts: [],
        liquidity_reserve_floor: '0',
        expected_revision: 0,
      }),
    ).resolves.toMatchObject({ journal_entry: 'Imported 1 account from QIF file.' });
  });

  it('runs pipeline', async () => {
    const response = await runPipeline({ tasks: [{ agent_name: 'macro_regime' }] });
    expect(response.successful).toBe(1);
    expect(response.results[0]?.task_id).toBe('task-1');
  });

  it('surfaces api errors', async () => {
    server.use(http.post('/api/digest', () => HttpResponse.json({ detail: 'Bad request' }, { status: 400 })));
    await expect(runDigest({ tickers: ['BAD'] })).rejects.toThrow();
  });
});
