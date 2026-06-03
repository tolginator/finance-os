import { describe, expect, it } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { MacroDashboard } from '../src/components/MacroDashboard';
import { server } from './mocks/server';

describe('MacroDashboard', () => {
  it('shows a loading state before the macro regime resolves', async () => {
    server.use(
      http.post('/api/agents/macro_regime', async () => {
        await new Promise((resolve) => setTimeout(resolve, 500));
        return HttpResponse.json({
          regime: 'Balanced slowdown',
          indicators_fetched: 8,
          indicators_with_data: 7,
          content: 'Macro regime classification completed.',
        });
      }),
    );

    render(<MacroDashboard />);

    expect(screen.getByTestId('macro-loading')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByTestId('macro-regime')).toBeInTheDocument();
    });
  });

  it('renders the regime, indicator counts, and narrative content', async () => {
    server.use(
      http.post('/api/agents/macro_regime', () =>
        HttpResponse.json({
          regime: 'Disinflationary expansion',
          indicators_fetched: 9,
          indicators_with_data: 8,
          content: 'Growth is positive while inflation pressures continue to ease.',
        }),
      ),
    );

    render(<MacroDashboard />);

    await waitFor(() => {
      expect(screen.getByTestId('macro-regime')).toHaveTextContent('Disinflationary expansion');
    });
    expect(screen.getByText('9')).toBeInTheDocument();
    expect(screen.getByText('8')).toBeInTheDocument();
    expect(screen.getByTestId('macro-content')).toHaveTextContent(
      'Growth is positive while inflation pressures continue to ease.',
    );
  });
});
