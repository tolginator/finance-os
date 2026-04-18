import { describe, it, expect } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { KnowledgeGraphPanel } from '../src/components/KnowledgeGraphPanel';
import { server } from './mocks/server';

describe('KnowledgeGraphPanel', () => {
  it('shows validation error for empty text', () => {
    render(<KnowledgeGraphPanel />);
    fireEvent.click(screen.getByText('Extract'));
    expect(screen.getByTestId('kg-error')).toBeInTheDocument();
  });

  it('extracts entities and displays results table', async () => {
    render(<KnowledgeGraphPanel />);
    const textarea = screen.getByPlaceholderText('Paste text to extract entities and relationships...');
    fireEvent.change(textarea, { target: { value: 'Apple uses Intel chips for MacBooks' } });
    fireEvent.click(screen.getByText('Extract'));

    await waitFor(() => {
      const result = screen.getByTestId('kg-extraction');
      expect(result).toBeInTheDocument();
      expect(result).toHaveTextContent('Entities (2)');
      expect(result).toHaveTextContent('Relationships (1)');
      expect(result).toHaveTextContent('Apple Inc');
      expect(result).toHaveTextContent('Intel Corp');
      expect(result).toHaveTextContent('supplies_to');
    });
  });

  it('shows error when extraction fails', async () => {
    server.use(
      http.post('/api/kg/extract', () => HttpResponse.json({ detail: 'Extraction error' }, { status: 500 })),
    );
    render(<KnowledgeGraphPanel />);
    fireEvent.change(
      screen.getByPlaceholderText('Paste text to extract entities and relationships...'),
      { target: { value: 'some text' } },
    );
    fireEvent.click(screen.getByText('Extract'));

    await waitFor(() => {
      const el = screen.getByTestId('kg-error');
      expect(el).toBeInTheDocument();
      expect(el.textContent).not.toBe('');
    });
  });

  it('shows query tabs after extraction', async () => {
    render(<KnowledgeGraphPanel />);
    fireEvent.change(
      screen.getByPlaceholderText('Paste text to extract entities and relationships...'),
      { target: { value: 'Apple uses Intel chips' } },
    );
    fireEvent.click(screen.getByText('Extract'));

    await waitFor(() => {
      expect(screen.getByText('Related')).toBeInTheDocument();
      expect(screen.getByText('Supply Chain')).toBeInTheDocument();
      expect(screen.getByText('Shared Risks')).toBeInTheDocument();
    });
  });

  it('queries related entities from extraction results', async () => {
    render(<KnowledgeGraphPanel />);
    fireEvent.change(
      screen.getByPlaceholderText('Paste text to extract entities and relationships...'),
      { target: { value: 'Apple uses Intel chips' } },
    );
    fireEvent.click(screen.getByText('Extract'));

    await waitFor(() => {
      expect(screen.getByTestId('entity-select')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Query'));

    await waitFor(() => {
      const result = screen.getByTestId('kg-query-result');
      expect(result).toHaveTextContent('Intel Corp');
    });
  });

  it('queries supply chain with direction', async () => {
    render(<KnowledgeGraphPanel />);
    fireEvent.change(
      screen.getByPlaceholderText('Paste text to extract entities and relationships...'),
      { target: { value: 'Apple uses Intel chips' } },
    );
    fireEvent.click(screen.getByText('Extract'));

    await waitFor(() => {
      expect(screen.getByText('Supply Chain')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText('Supply Chain'));
    fireEvent.click(screen.getByText('Query'));

    await waitFor(() => {
      const result = screen.getByTestId('kg-query-result');
      expect(result).toHaveTextContent('TSMC');
    });
  });

  it('refreshes KG stats on button click', async () => {
    render(<KnowledgeGraphPanel />);
    fireEvent.click(screen.getByText('Refresh Stats'));

    await waitFor(() => {
      const stats = screen.getByTestId('kg-stats');
      expect(stats).toHaveTextContent('15 entities');
      expect(stats).toHaveTextContent('22 relationships');
    });
  });

  it('shows extracting state while loading', async () => {
    server.use(
      http.post('/api/kg/extract', async () => {
        await new Promise((r) => setTimeout(r, 200));
        return HttpResponse.json({ entities: [], relationships: [], entity_count: 0, relationship_count: 0 });
      }),
    );
    render(<KnowledgeGraphPanel />);
    fireEvent.change(
      screen.getByPlaceholderText('Paste text to extract entities and relationships...'),
      { target: { value: 'some text' } },
    );
    fireEvent.click(screen.getByText('Extract'));
    expect(screen.getByText('Extracting…')).toBeInTheDocument();
    expect(screen.getByText('Extracting…')).toBeDisabled();

    await waitFor(() => {
      expect(screen.getByText('Extract')).toBeInTheDocument();
    });
  });

  it('clears previous results on new extraction', async () => {
    render(<KnowledgeGraphPanel />);
    const textarea = screen.getByPlaceholderText('Paste text to extract entities and relationships...');
    fireEvent.change(textarea, { target: { value: 'Apple uses Intel chips' } });
    fireEvent.click(screen.getByText('Extract'));

    await waitFor(() => {
      expect(screen.getByTestId('kg-extraction')).toBeInTheDocument();
    });

    // Start a new extraction — previous results should clear
    server.use(
      http.post('/api/kg/extract', () =>
        HttpResponse.json({ entities: [], relationships: [], entity_count: 0, relationship_count: 0 }),
      ),
    );
    fireEvent.change(textarea, { target: { value: 'Different text' } });
    fireEvent.click(screen.getByText('Extract'));

    await waitFor(() => {
      expect(screen.getByTestId('kg-extraction')).toHaveTextContent('Entities (0)');
    });
  });
});
