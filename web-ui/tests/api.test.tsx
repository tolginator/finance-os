import { describe, it, expect } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from './mocks/server';
import {
  extractEntities,
  fetchKGStats,
  normalizeDetail,
  queryRelated,
  runAdversarialChallenge,
  runEarningsAnalysis,
  runFilingSearch,
  runMacroClassification,
  runPipeline,
  runRiskAssessment,
  runSignalGeneration,
  runThesisEvaluation,
} from '../src/api';

// --- normalizeDetail (pure function) ---

describe('normalizeDetail', () => {
  it('returns string detail as-is', () => {
    expect(normalizeDetail('Not found')).toBe('Not found');
  });

  it('formats 422 validation error array', () => {
    const detail = [{ loc: ['body', 'transcript'], msg: 'field required', type: 'missing' }];
    expect(normalizeDetail(detail)).toBe('body → transcript: field required');
  });

  it('joins multiple errors with semicolons', () => {
    const detail = [
      { loc: ['body', 'tasks', 0, 'agent_name'], msg: 'field required' },
      { loc: ['body', 'tasks', 0, 'task_id'], msg: 'too short' },
    ];
    const result = normalizeDetail(detail);
    expect(result).toContain('agent_name');
    expect(result).toContain('too short');
    expect(result).toContain(';');
  });

  it('stringifies object detail', () => {
    expect(normalizeDetail({ error: 'bad' })).toBe('{"error":"bad"}');
  });

  it('falls back to String() for other types', () => {
    expect(normalizeDetail(42)).toBe('42');
  });
});

// --- API error handling (behavior) ---

describe('API error handling', () => {
  it('rejects on 422 validation errors', async () => {
    server.use(
      http.post('/api/agents/earnings_interpreter', () =>
        HttpResponse.json(
          { detail: [{ loc: ['body', 'transcript'], msg: 'field required', type: 'missing' }] },
          { status: 422 },
        ),
      ),
    );
    await expect(runEarningsAnalysis({ transcript: '' })).rejects.toThrow();
  });

  it('rejects on 404 with detail', async () => {
    server.use(
      http.post('/api/agents/macro_regime', () =>
        HttpResponse.json({ detail: 'Not found' }, { status: 404 }),
      ),
    );
    await expect(runMacroClassification({})).rejects.toThrow();
  });

  it('rejects on 500 with no detail', async () => {
    server.use(
      http.post('/api/agents/filing_analyst', () =>
        new HttpResponse(JSON.stringify({}), { status: 500, statusText: 'Internal Server Error', headers: { 'Content-Type': 'application/json' } }),
      ),
    );
    await expect(runFilingSearch({ ticker: 'X' })).rejects.toThrow();
  });

  it('rejects on 422 with multiple errors', async () => {
    server.use(
      http.post('/api/pipeline', () =>
        HttpResponse.json(
          { detail: [
            { loc: ['body', 'tasks', 0, 'agent_name'], msg: 'field required' },
            { loc: ['body', 'tasks', 0, 'task_id'], msg: 'too short' },
          ] },
          { status: 422 },
        ),
      ),
    );
    await expect(runPipeline({ tasks: [] })).rejects.toThrow();
  });
});

// --- Agent API functions ---

describe('Agent API functions', () => {
  it('runEarningsAnalysis returns structured response', async () => {
    const resp = await runEarningsAnalysis({ transcript: 'Q1 results were strong' });
    expect(resp.tone).toBe('cautiously optimistic');
    expect(resp.net_sentiment).toBe(0.65);
    expect(resp.guidance_count).toBe(3);
  });

  it('runMacroClassification returns regime', async () => {
    const resp = await runMacroClassification({});
    expect(resp.regime).toBe('expansion');
    expect(resp.indicators_fetched).toBe(5);
  });

  it('runFilingSearch returns filing count', async () => {
    const resp = await runFilingSearch({ ticker: 'AAPL' });
    expect(resp.filing_count).toBe(5);
    expect(resp.cik).toBe('0000320193');
  });

  it('runSignalGeneration returns composite', async () => {
    const resp = await runSignalGeneration({ regime: 'expansion' });
    expect(resp.agent).toBe('quant_signal');
    expect(resp.composite).toHaveProperty('score');
  });

  it('runThesisEvaluation returns alert counts', async () => {
    const resp = await runThesisEvaluation({ theses: [{ ticker: 'X', hypothesis: 'test' }] });
    expect(resp.theses_checked).toBe(2);
    expect(resp.critical_alerts).toBe(0);
  });

  it('runRiskAssessment returns content', async () => {
    const resp = await runRiskAssessment({});
    expect(resp.content).toBe('Risk analysis report');
  });

  it('runAdversarialChallenge returns conviction', async () => {
    const resp = await runAdversarialChallenge({ prompt: 'AAPL will grow' });
    expect(resp.conviction_score).toBe('medium');
    expect(resp.counter_count).toBe(4);
  });
});

// --- Pipeline ---

describe('Pipeline API', () => {
  it('runPipeline returns results with timing', async () => {
    const resp = await runPipeline({ tasks: [{ agent_name: 'macro_regime' }] });
    expect(resp.successful).toBe(1);
    expect(resp.failed).toBe(0);
    expect(resp.total_duration_ms).toBeGreaterThan(0);
  });
});

// --- Knowledge Graph ---

describe('Knowledge Graph API', () => {
  it('extractEntities returns entities and relationships', async () => {
    const resp = await extractEntities({ text: 'Apple uses Intel chips' });
    expect(resp.entity_count).toBe(2);
    expect(resp.relationship_count).toBe(1);
    expect(resp.entities[0].name).toBe('Apple Inc');
  });

  it('queryRelated returns related entities', async () => {
    const resp = await queryRelated({ entity_id: 'company:apple inc' });
    expect(resp.count).toBe(1);
    expect(resp.related[0].name).toBe('Intel Corp');
  });

  it('fetchKGStats returns counts by type', async () => {
    const resp = await fetchKGStats();
    expect(resp.entity_count).toBe(15);
    expect(resp.entities_by_type).toHaveProperty('company');
    expect(resp.relationships_by_type).toHaveProperty('supplies_to');
  });
});
