import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { App } from '../src/App';
import { HealthStatus } from '../src/components/HealthStatus';
import { AgentList } from '../src/components/AgentList';
import { DigestPanel } from '../src/components/DigestPanel';
import { server } from './mocks/server';

// --- App (smoke) ---

describe('App', () => {
  it('renders the header and all panels', async () => {
    render(<App />);
    expect(screen.getByText('finance-os')).toBeInTheDocument();
    expect(screen.getByText('Run Digest')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByTestId('health-label')).toBeInTheDocument();
    });
  });
});

// --- HealthStatus ---

describe('HealthStatus', () => {
  it('shows connected when API returns ok', async () => {
    render(<HealthStatus />);
    await waitFor(() => {
      expect(screen.getByTestId('health-label')).toHaveTextContent('API Connected');
    });
    expect(screen.getByTestId('health-dot')).toHaveStyle({ backgroundColor: '#22c55e' });
  });

  it('shows unavailable when API is unreachable', async () => {
    server.use(http.get('/api/health', () => HttpResponse.error()));
    render(<HealthStatus />);
    await waitFor(() => {
      expect(screen.getByTestId('health-label')).toHaveTextContent('API Unavailable');
    });
    expect(screen.getByTestId('health-dot')).toHaveStyle({ backgroundColor: '#ef4444' });
  });

  it('shows unavailable when API returns non-ok status', async () => {
    server.use(http.get('/api/health', () => HttpResponse.json({ status: 'degraded' })));
    render(<HealthStatus />);
    await waitFor(() => {
      expect(screen.getByTestId('health-label')).toHaveTextContent('API Unavailable');
    });
  });

  it('shows loading state initially', async () => {
    server.use(http.get('/api/health', async () => {
      await new Promise((r) => setTimeout(r, 500));
      return HttpResponse.json({ status: 'ok' });
    }));
    render(<HealthStatus />);
    expect(screen.getByTestId('health-label')).toHaveTextContent('Checking');
    expect(screen.getByTestId('health-dot')).toHaveStyle({ backgroundColor: '#a3a3a3' });
    await waitFor(() => {
      expect(screen.getByTestId('health-label')).toHaveTextContent('API Connected');
    });
  });
});

// --- AgentList ---

describe('AgentList', () => {
  it('renders agent cards from API', async () => {
    render(<AgentList />);
    await waitFor(() => {
      expect(screen.getByTestId('agent-macro_regime')).toBeInTheDocument();
      expect(screen.getByTestId('agent-filing_analyst')).toBeInTheDocument();
      expect(screen.getByTestId('agent-adversarial')).toBeInTheDocument();
    });
  });

  it('shows loading state initially', async () => {
    server.use(http.get('/api/agents', async () => {
      await new Promise((r) => setTimeout(r, 500));
      return HttpResponse.json([]);
    }));
    render(<AgentList />);
    expect(screen.getByTestId('agents-loading')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByTestId('agents-empty')).toBeInTheDocument();
    });
  });

  it('shows error when agent fetch fails', async () => {
    server.use(http.get('/api/agents', () => HttpResponse.json({ detail: 'Server error' }, { status: 500 })));
    render(<AgentList />);
    await waitFor(() => {
      expect(screen.getByTestId('agents-error')).toBeInTheDocument();
    });
  });

  it('shows empty state when no agents returned', async () => {
    server.use(http.get('/api/agents', () => HttpResponse.json([])));
    render(<AgentList />);
    await waitFor(() => {
      expect(screen.getByTestId('agents-empty')).toBeInTheDocument();
    });
  });
});

// --- DigestPanel ---

describe('DigestPanel', () => {
  it('shows validation error for empty tickers', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    render(<DigestPanel />);
    fireEvent.click(screen.getByText('Run Digest'));
    expect(screen.getByTestId('digest-error')).toBeInTheDocument();
    // Validation should prevent network request
    const digestCalls = fetchSpy.mock.calls.filter(
      ([url]) => typeof url === 'string' && url.includes('/digest'),
    );
    expect(digestCalls).toHaveLength(0);
    fetchSpy.mockRestore();
  });

  it('shows validation error for whitespace-only input', () => {
    render(<DigestPanel />);
    const input = screen.getByPlaceholderText('AAPL, MSFT, GOOGL');
    fireEvent.change(input, { target: { value: '   ,  , ' } });
    fireEvent.click(screen.getByText('Run Digest'));
    expect(screen.getByTestId('digest-error')).toBeInTheDocument();
  });

  it('runs digest and displays results', async () => {
    render(<DigestPanel />);
    const input = screen.getByPlaceholderText('AAPL, MSFT, GOOGL');
    fireEvent.change(input, { target: { value: 'AAPL, MSFT' } });
    fireEvent.click(screen.getByText('Run Digest'));

    await waitFor(() => {
      const result = screen.getByTestId('digest-result');
      expect(result).toBeInTheDocument();
      expect(result).toHaveTextContent('Tickers: 2');
      expect(result).toHaveTextContent('Digest for AAPL, MSFT');
    });
  });

  it('uppercases and normalizes ticker input', async () => {
    let capturedTickers: string[] = [];
    server.use(
      http.post('/api/digest', async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        capturedTickers = body.tickers as string[];
        return HttpResponse.json({
          ticker_count: capturedTickers.length,
          entry_count: 0,
          alert_count: 0,
          material_count: 0,
          content: `Digest for ${capturedTickers.join(', ')}`,
        });
      }),
    );
    render(<DigestPanel />);
    const input = screen.getByPlaceholderText('AAPL, MSFT, GOOGL');
    fireEvent.change(input, { target: { value: '  aapl   msft, googl  ' } });
    fireEvent.click(screen.getByText('Run Digest'));

    await waitFor(() => {
      expect(screen.getByTestId('digest-result')).toBeInTheDocument();
    });
    expect(capturedTickers).toEqual(['AAPL', 'MSFT', 'GOOGL']);
  });

  it('shows error when digest API fails', async () => {
    server.use(http.post('/api/digest', () => HttpResponse.json({ detail: 'Bad request' }, { status: 400 })));
    render(<DigestPanel />);
    const input = screen.getByPlaceholderText('AAPL, MSFT, GOOGL');
    fireEvent.change(input, { target: { value: 'BAD' } });
    fireEvent.click(screen.getByText('Run Digest'));

    await waitFor(() => {
      expect(screen.getByTestId('digest-error')).toBeInTheDocument();
    });
  });

  it('clears previous error on successful submission', async () => {
    // First: trigger validation error
    render(<DigestPanel />);
    fireEvent.click(screen.getByText('Run Digest'));
    expect(screen.getByTestId('digest-error')).toBeInTheDocument();

    // Then: submit valid input
    const input = screen.getByPlaceholderText('AAPL, MSFT, GOOGL');
    fireEvent.change(input, { target: { value: 'AAPL' } });
    fireEvent.click(screen.getByText('Run Digest'));

    await waitFor(() => {
      expect(screen.getByTestId('digest-result')).toBeInTheDocument();
    });
    expect(screen.queryByTestId('digest-error')).not.toBeInTheDocument();
  });

  it('shows loading state while fetching', async () => {
    server.use(
      http.post('/api/digest', async () => {
        await new Promise((r) => setTimeout(r, 500));
        return HttpResponse.json({
          ticker_count: 1, entry_count: 0, alert_count: 0, material_count: 0, content: 'done',
        });
      }),
    );
    render(<DigestPanel />);
    const input = screen.getByPlaceholderText('AAPL, MSFT, GOOGL');
    fireEvent.change(input, { target: { value: 'AAPL' } });
    fireEvent.click(screen.getByText('Run Digest'));

    // Button should show loading state immediately
    expect(screen.getByText('Running…')).toBeInTheDocument();
    expect(screen.getByText('Running…')).toBeDisabled();

    // Eventually resolves back to normal
    await waitFor(() => {
      expect(screen.getByText('Run Digest')).toBeInTheDocument();
    });
  });

  it('sends lookback_days from input', async () => {
    let capturedLookback = 0;
    server.use(
      http.post('/api/digest', async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        capturedLookback = body.lookback_days as number;
        return HttpResponse.json({
          ticker_count: 1, entry_count: 0, alert_count: 0, material_count: 0, content: 'ok',
        });
      }),
    );
    render(<DigestPanel />);
    const tickerInput = screen.getByPlaceholderText('AAPL, MSFT, GOOGL');
    fireEvent.change(tickerInput, { target: { value: 'AAPL' } });
    const lookbackInput = screen.getByDisplayValue('7');
    fireEvent.change(lookbackInput, { target: { value: '30' } });
    fireEvent.click(screen.getByText('Run Digest'));

    await waitFor(() => {
      expect(screen.getByTestId('digest-result')).toBeInTheDocument();
    });
    expect(capturedLookback).toBe(30);
  });
});
