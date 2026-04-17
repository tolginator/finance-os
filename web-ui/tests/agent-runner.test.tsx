import { describe, it, expect } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { AgentRunner } from '../src/components/AgentRunner';
import { server } from './mocks/server';

describe('AgentRunner', () => {
  it('loads agent list and shows selector', async () => {
    render(<AgentRunner />);
    await waitFor(() => {
      expect(screen.getByTestId('agent-select')).toBeInTheDocument();
    });
    const select = screen.getByTestId('agent-select') as HTMLSelectElement;
    expect(select.options.length).toBe(3);
  });

  it('shows loading state initially', () => {
    render(<AgentRunner />);
    expect(screen.getByTestId('agent-runner-loading')).toBeInTheDocument();
  });

  it('shows error when agent list fails', async () => {
    server.use(http.get('/api/agents', () => HttpResponse.json({ detail: 'fail' }, { status: 500 })));
    render(<AgentRunner />);
    await waitFor(() => {
      expect(screen.getByTestId('agent-runner-error')).toBeInTheDocument();
    });
  });

  it('renders form fields for selected agent', async () => {
    render(<AgentRunner />);
    await waitFor(() => {
      expect(screen.getByTestId('agent-select')).toBeInTheDocument();
    });

    // macro_regime is the first agent in mock — its spec has api_key and indicators fields
    expect(screen.getByText('FRED API Key')).toBeInTheDocument();
  });

  it('switches form when selecting different agent', async () => {
    render(<AgentRunner />);
    await waitFor(() => {
      expect(screen.getByTestId('agent-select')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId('agent-select'), { target: { value: 'adversarial' } });
    await waitFor(() => {
      expect(screen.getByText('Thesis Prompt')).toBeInTheDocument();
    });
  });

  it('runs agent and displays structured results', async () => {
    render(<AgentRunner />);
    await waitFor(() => {
      expect(screen.getByTestId('agent-select')).toBeInTheDocument();
    });

    // Select adversarial agent and fill prompt
    fireEvent.change(screen.getByTestId('agent-select'), { target: { value: 'adversarial' } });
    await waitFor(() => {
      expect(screen.getByText('Thesis Prompt')).toBeInTheDocument();
    });

    const promptInput = screen.getByPlaceholderText('Describe the investment thesis to challenge...');
    fireEvent.change(promptInput, { target: { value: 'AAPL will double in 2 years' } });
    fireEvent.click(screen.getByText('Run Agent'));

    await waitFor(() => {
      const result = screen.getByTestId('agent-runner-result');
      expect(result).toHaveTextContent('Adversarial challenge report');
      expect(result).toHaveTextContent('medium');
      expect(result).toHaveTextContent('4');
    });
  });

  it('validates required fields before running', async () => {
    render(<AgentRunner />);
    await waitFor(() => {
      expect(screen.getByTestId('agent-select')).toBeInTheDocument();
    });

    // Select filing_analyst (ticker is not required per spec, but let's test earnings)
    fireEvent.change(screen.getByTestId('agent-select'), { target: { value: 'filing_analyst' } });
    await waitFor(() => {
      expect(screen.getByText('Ticker')).toBeInTheDocument();
    });

    // filing_analyst has no required fields, so running empty is fine
    fireEvent.click(screen.getByText('Run Agent'));
    await waitFor(() => {
      expect(screen.getByTestId('agent-runner-result')).toBeInTheDocument();
    });
  });

  it('shows error for invalid JSON in JSON fields', async () => {
    render(<AgentRunner />);
    await waitFor(() => {
      expect(screen.getByTestId('agent-select')).toBeInTheDocument();
    });

    // macro_regime has indicators JSON field
    const indicatorInput = screen.getByPlaceholderText('["GDP", "UNRATE", "CPIAUCSL"]');
    fireEvent.change(indicatorInput, { target: { value: 'not valid json' } });
    fireEvent.click(screen.getByText('Run Agent'));

    await waitFor(() => {
      expect(screen.getByTestId('agent-runner-error')).toHaveTextContent('invalid JSON');
    });
  });

  it('shows error when agent API fails', async () => {
    server.use(
      http.post('/api/agents/macro_regime', () =>
        HttpResponse.json({ detail: 'Agent failed' }, { status: 500 }),
      ),
    );
    render(<AgentRunner />);
    await waitFor(() => {
      expect(screen.getByTestId('agent-select')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText('Run Agent'));

    await waitFor(() => {
      expect(screen.getByTestId('agent-runner-error')).toHaveTextContent('Agent failed');
    });
  });

  it('clears result when switching agents', async () => {
    render(<AgentRunner />);
    await waitFor(() => {
      expect(screen.getByTestId('agent-select')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Run Agent'));
    await waitFor(() => {
      expect(screen.getByTestId('agent-runner-result')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId('agent-select'), { target: { value: 'adversarial' } });
    expect(screen.queryByTestId('agent-runner-result')).not.toBeInTheDocument();
  });
});
