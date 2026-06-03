import { describe, it, expect } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { PipelineRunner } from '../src/components/PipelineRunner';
import { StatsDashboard } from '../src/components/StatsDashboard';
import { server } from './mocks/server';

describe('PipelineRunner', () => {
  it('renders initial task editor with agent selector', () => {
    render(<PipelineRunner />);
    expect(screen.getByText('Run Pipeline')).toBeInTheDocument();
    expect(screen.getByText('+ Add Task')).toBeInTheDocument();
    expect(screen.getByText('task-0')).toBeInTheDocument();
  });

  it('adds and removes tasks', () => {
    render(<PipelineRunner />);
    fireEvent.click(screen.getByText('+ Add Task'));
    expect(screen.getAllByText('task-1').length).toBeGreaterThanOrEqual(1);
    fireEvent.click(screen.getByLabelText('Remove task-1'));
    expect(screen.queryAllByText('task-1')).toHaveLength(0);
  });

  it('runs pipeline and shows results', async () => {
    render(<PipelineRunner />);
    fireEvent.click(screen.getByText('Run Pipeline'));

    await waitFor(() => {
      const result = screen.getByTestId('pipeline-result');
      expect(result).toHaveTextContent('1 succeeded');
      expect(result).toHaveTextContent('0 failed');
      expect(result).toHaveTextContent('1500ms');
    });
  });

  it('shows error when pipeline fails', async () => {
    server.use(http.post('/api/pipeline', () => HttpResponse.json({ detail: 'Pipeline error' }, { status: 500 })));
    render(<PipelineRunner />);
    fireEvent.click(screen.getByText('Run Pipeline'));

    await waitFor(() => {
      expect(screen.getByTestId('pipeline-error')).toBeInTheDocument();
    });
  });

  it('detects dependency cycles', async () => {
    render(<PipelineRunner />);
    fireEvent.click(screen.getByText('+ Add Task'));

    const allSelects = screen.getAllByRole('listbox') as HTMLSelectElement[];
    allSelects[0].options[0].selected = true;
    fireEvent.change(allSelects[0]);
    allSelects[1].options[0].selected = true;
    fireEvent.change(allSelects[1]);

    fireEvent.click(screen.getByText('Run Pipeline'));
    await waitFor(() => {
      expect(screen.getByTestId('pipeline-error')).toHaveTextContent('cycle');
    });
  });
});

describe('StatsDashboard', () => {
  it('loads and displays stats from all sources', async () => {
    render(<StatsDashboard />);
    expect(screen.getByTestId('stats-loading')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('System Health')).toBeInTheDocument();
    });
    expect(screen.getByText('Agent Coverage')).toBeInTheDocument();
    expect(screen.getByText('Watchlists')).toBeInTheDocument();
  });

  it('refreshes stats on button click', async () => {
    render(<StatsDashboard />);
    await waitFor(() => {
      expect(screen.getByText('Status:')).toBeInTheDocument();
    });

    server.use(http.get('/api/health', () => HttpResponse.json({ status: 'degraded' }), { once: true }));

    fireEvent.click(screen.getByTestId('stats-refresh'));
    await waitFor(() => {
      expect(screen.getByText('degraded')).toBeInTheDocument();
    });
  });

  it('shows error when stats fail with refresh button available', async () => {
    server.use(http.get('/api/health', () => HttpResponse.json({}, { status: 500 })));
    render(<StatsDashboard />);
    await waitFor(() => {
      expect(screen.getByTestId('stats-error')).toBeInTheDocument();
    });
    expect(screen.getByTestId('stats-refresh')).toBeInTheDocument();
  });

  it('shows agent and watchlist counts', async () => {
    render(<StatsDashboard />);
    await waitFor(() => {
      expect(screen.getByText('Agents available:')).toBeInTheDocument();
    });
    expect(screen.getByText('Saved watchlists:')).toBeInTheDocument();
  });
});
