import { describe, it, expect } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { App } from '../src/App';
import { server } from './mocks/server';

describe('App', () => {
  it('renders the header', () => {
    render(<App />);
    expect(screen.getByText('finance-os')).toBeInTheDocument();
  });
});

describe('HealthStatus', () => {
  it('shows connected when API is healthy', async () => {
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('health-label')).toHaveTextContent('API Connected');
    });
  });

  it('shows unavailable when API is down', async () => {
    server.use(http.get('/api/health', () => HttpResponse.error()));
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('health-label')).toHaveTextContent('API Unavailable');
    });
  });
});

describe('AgentList', () => {
  it('renders agent cards from API', async () => {
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('agent-macro_regime')).toBeInTheDocument();
      expect(screen.getByTestId('agent-filing_analyst')).toBeInTheDocument();
      expect(screen.getByTestId('agent-adversarial')).toBeInTheDocument();
    });
  });

  it('shows error when agent fetch fails', async () => {
    server.use(http.get('/api/agents', () => HttpResponse.json({ detail: 'Server error' }, { status: 500 })));
    render(<App />);
    await waitFor(() => {
      expect(screen.getByText(/Error:/)).toBeInTheDocument();
    });
  });
});

describe('DigestPanel', () => {
  it('shows validation error for empty tickers', async () => {
    render(<App />);
    const button = screen.getByText('Run Digest');
    fireEvent.click(button);
    expect(screen.getByTestId('digest-error')).toHaveTextContent('Enter at least one ticker');
  });

  it('runs digest and displays results', async () => {
    render(<App />);
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

  it('shows error when digest API fails', async () => {
    server.use(http.post('/api/digest', () => HttpResponse.json({ detail: 'Bad request' }, { status: 400 })));
    render(<App />);
    const input = screen.getByPlaceholderText('AAPL, MSFT, GOOGL');
    fireEvent.change(input, { target: { value: 'BAD' } });
    fireEvent.click(screen.getByText('Run Digest'));

    await waitFor(() => {
      expect(screen.getByTestId('digest-error')).toHaveTextContent('Bad request');
    });
  });
});
