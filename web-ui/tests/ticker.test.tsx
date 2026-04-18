import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { App } from '../src/App';
import { server } from './mocks/server';

describe('TickerBar', () => {
  it('renders ticker input and lookup button', () => {
    render(<App />);
    expect(screen.getByTestId('ticker-input')).toBeInTheDocument();
    expect(screen.getByTestId('ticker-lookup')).toBeInTheDocument();
  });

  it('fetches and displays ticker summary on lookup', async () => {
    render(<App />);
    fireEvent.change(screen.getByTestId('ticker-input'), { target: { value: 'AAPL' } });
    fireEvent.click(screen.getByTestId('ticker-lookup'));

    await waitFor(() => {
      expect(screen.getByTestId('ticker-summary')).toBeInTheDocument();
    });
    expect(screen.getByText(/AAPL Inc\./)).toBeInTheDocument();
    expect(screen.getByText(/Technology/)).toBeInTheDocument();
  });

  it('shows error when lookup fails', async () => {
    server.use(
      http.get('/api/ticker/:symbol/summary', () => HttpResponse.json({}, { status: 500 })),
    );
    render(<App />);
    fireEvent.change(screen.getByTestId('ticker-input'), { target: { value: 'BAD' } });
    fireEvent.click(screen.getByTestId('ticker-lookup'));

    await waitFor(() => {
      const el = screen.getByTestId('ticker-error');
      expect(el).toBeInTheDocument();
      expect(el.textContent).not.toBe('');
    });
  });

  it('auto-populates agent runner fields with ticker data', async () => {
    render(<App />);

    // Wait for agents to load
    await waitFor(() => {
      expect(screen.getByTestId('agent-select')).toBeInTheDocument();
    });

    // Look up AAPL
    fireEvent.change(screen.getByTestId('ticker-input'), { target: { value: 'AAPL' } });
    fireEvent.click(screen.getByTestId('ticker-lookup'));

    await waitFor(() => {
      expect(screen.getByTestId('ticker-summary')).toBeInTheDocument();
    });

    // The earnings_interpreter form should have ticker pre-filled
    // (earnings_interpreter is the default agent)
    const transcriptField = screen.getByPlaceholderText(/Paste earnings call transcript/);
    await waitFor(() => {
      expect((transcriptField as HTMLTextAreaElement).value).toContain('earnings call transcript for AAPL');
    });
  });

  it('submits lookup on Enter key', async () => {
    render(<App />);
    const input = screen.getByTestId('ticker-input');
    fireEvent.change(input, { target: { value: 'MSFT' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    await waitFor(() => {
      expect(screen.getByTestId('ticker-summary')).toBeInTheDocument();
    });
    expect(screen.getByText(/MSFT Inc\./)).toBeInTheDocument();
  });

  it('disables lookup button when input is empty', () => {
    render(<App />);
    expect(screen.getByTestId('ticker-lookup')).toBeDisabled();
  });
});
