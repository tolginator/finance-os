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
    expect(screen.getByText('task-1')).toBeInTheDocument();
  });

  it('adds and removes tasks', () => {
    render(<PipelineRunner />);
    fireEvent.click(screen.getByText('+ Add Task'));
    // task-2 appears as its own label and as a depends_on option for task-1
    expect(screen.getAllByText('task-2').length).toBeGreaterThanOrEqual(1);

    // Remove second task
    fireEvent.click(screen.getByLabelText('Remove task-2'));
    // Only the label should be gone; task-1's depends_on no longer lists it
    expect(screen.queryAllByText('task-2')).toHaveLength(0);
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
    server.use(
      http.post('/api/pipeline', () => HttpResponse.json({ detail: 'Pipeline error' }, { status: 500 })),
    );
    render(<PipelineRunner />);
    fireEvent.click(screen.getByText('Run Pipeline'));

    await waitFor(() => {
      const el = screen.getByTestId('pipeline-error');
      expect(el).toBeInTheDocument();
      expect(el.textContent).not.toBe('');
    });
  });

  it('detects dependency cycles', async () => {
    render(<PipelineRunner />);
    fireEvent.click(screen.getByText('+ Add Task'));

    // Get the multi-select elements (depends_on for each task)
    const allSelects = screen.getAllByRole('listbox') as HTMLSelectElement[];
    // allSelects[0] = task-1's depends_on (has option for task-2)
    // allSelects[1] = task-2's depends_on (has option for task-1)

    // Select task-2 as dependency of task-1
    const opt1 = allSelects[0].options[0]; // task-2
    opt1.selected = true;
    fireEvent.change(allSelects[0]);

    // Select task-1 as dependency of task-2
    const opt2 = allSelects[1].options[0]; // task-1
    opt2.selected = true;
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
    expect(screen.getByText('ok')).toBeInTheDocument();
    expect(screen.getByText('Knowledge Graph')).toBeInTheDocument();
  });

  it('refreshes stats on button click', async () => {
    render(<StatsDashboard />);
    await waitFor(() => {
      expect(screen.getByTestId('stats-refresh')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('stats-refresh'));
    await waitFor(() => {
      expect(screen.getByText('System Health')).toBeInTheDocument();
    });
  });

  it('shows error when stats fail with refresh button available', async () => {
    server.use(
      http.get('/api/health', () => HttpResponse.json({}, { status: 500 })),
    );
    render(<StatsDashboard />);
    await waitFor(() => {
      expect(screen.getByTestId('stats-error')).toBeInTheDocument();
    });
    expect(screen.getByTestId('stats-refresh')).toBeInTheDocument();
  });

  it('shows agent count', async () => {
    render(<StatsDashboard />);
    await waitFor(() => {
      expect(screen.getByText(/^Agents \(\d+\)$/)).toBeInTheDocument();
    });
  });
});
