import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { QifImporter } from '../src/components/QifImporter';
import { server } from './mocks/server';

describe('QifImporter', () => {
  it('shows browse button in the idle state', () => {
    render(<QifImporter onImported={() => {}} />);

    expect(screen.getByTestId('qif-importer')).toBeInTheDocument();
    expect(screen.getByTestId('qif-browse-button')).toBeInTheDocument();
    expect(screen.getByTestId('qif-preview-button')).toBeDisabled();
  });

  it('opens file browser when Browse is clicked', async () => {
    render(<QifImporter onImported={() => {}} />);

    fireEvent.click(screen.getByTestId('qif-browse-button'));

    await waitFor(() => {
      expect(screen.getByTestId('qif-file-browser')).toBeInTheDocument();
    });
    expect(screen.getByText('portfolio.qif')).toBeInTheDocument();
    expect(screen.getByText('Documents')).toBeInTheDocument();
  });

  it('selects a file from the browser and enables Load QIF', async () => {
    render(<QifImporter onImported={() => {}} />);

    fireEvent.click(screen.getByTestId('qif-browse-button'));

    await waitFor(() => {
      expect(screen.getByText('portfolio.qif')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('portfolio.qif'));

    await waitFor(() => {
      expect(screen.getByTestId('qif-path-input')).toHaveValue('/home/user/portfolio.qif');
    });
    expect(screen.getByTestId('qif-preview-button')).not.toBeDisabled();
  });

  it('shows account preview after selecting file and loading', async () => {
    render(<QifImporter onImported={() => {}} />);

    fireEvent.click(screen.getByTestId('qif-browse-button'));
    await waitFor(() => { expect(screen.getByText('portfolio.qif')).toBeInTheDocument(); });
    fireEvent.click(screen.getByText('portfolio.qif'));
    await waitFor(() => { expect(screen.getByTestId('qif-preview-button')).not.toBeDisabled(); });

    fireEvent.click(screen.getByTestId('qif-preview-button'));

    await waitFor(() => {
      expect(screen.getByTestId('qif-preview-accounts')).toBeInTheDocument();
    });
    expect(screen.getByText('Primary Brokerage')).toBeInTheDocument();
  });

  it('clicking confirm saves excluded accounts and shows success', async () => {
    render(<QifImporter onImported={() => {}} />);

    fireEvent.click(screen.getByTestId('qif-browse-button'));
    await waitFor(() => { expect(screen.getByText('portfolio.qif')).toBeInTheDocument(); });
    fireEvent.click(screen.getByText('portfolio.qif'));
    await waitFor(() => { expect(screen.getByTestId('qif-preview-button')).not.toBeDisabled(); });
    fireEvent.click(screen.getByTestId('qif-preview-button'));
    await waitFor(() => { expect(screen.getByTestId('qif-confirm-button')).toBeInTheDocument(); });

    fireEvent.click(screen.getByTestId('qif-confirm-button'));

    await waitFor(() => {
      expect(screen.getByTestId('qif-success')).toBeInTheDocument();
    });
  });

  it('clicking cancel returns to idle state', async () => {
    render(<QifImporter onImported={() => {}} />);

    fireEvent.click(screen.getByTestId('qif-browse-button'));
    await waitFor(() => { expect(screen.getByText('portfolio.qif')).toBeInTheDocument(); });
    fireEvent.click(screen.getByText('portfolio.qif'));
    await waitFor(() => { expect(screen.getByTestId('qif-preview-button')).not.toBeDisabled(); });
    fireEvent.click(screen.getByTestId('qif-preview-button'));
    await waitFor(() => { expect(screen.getByTestId('qif-confirm-button')).toBeInTheDocument(); });

    fireEvent.click(screen.getByTestId('qif-cancel-button'));

    expect(screen.queryByTestId('qif-confirm-button')).not.toBeInTheDocument();
    expect(screen.getByTestId('qif-browse-button')).toBeInTheDocument();
  });

  it('shows an error state on network failure', async () => {
    server.use(
      http.post('/api/household/qif_source', () =>
        HttpResponse.json({ detail: 'File not found' }, { status: 400 }),
      ),
    );

    render(<QifImporter onImported={() => {}} />);

    fireEvent.click(screen.getByTestId('qif-browse-button'));
    await waitFor(() => { expect(screen.getByText('portfolio.qif')).toBeInTheDocument(); });
    fireEvent.click(screen.getByText('portfolio.qif'));
    await waitFor(() => { expect(screen.getByTestId('qif-preview-button')).not.toBeDisabled(); });
    fireEvent.click(screen.getByTestId('qif-preview-button'));

    await waitFor(() => {
      expect(screen.getByText(/File not found|Unable to preview/)).toBeInTheDocument();
    });
    expect(screen.queryByTestId('qif-preview-accounts')).not.toBeInTheDocument();
  });

  it('calls onImported when the user chooses to view the portfolio', async () => {
    const onImported = vi.fn();
    render(<QifImporter onImported={onImported} />);

    fireEvent.click(screen.getByTestId('qif-browse-button'));
    await waitFor(() => { expect(screen.getByText('portfolio.qif')).toBeInTheDocument(); });
    fireEvent.click(screen.getByText('portfolio.qif'));
    await waitFor(() => { expect(screen.getByTestId('qif-preview-button')).not.toBeDisabled(); });
    fireEvent.click(screen.getByTestId('qif-preview-button'));
    await waitFor(() => { expect(screen.getByTestId('qif-confirm-button')).toBeInTheDocument(); });
    fireEvent.click(screen.getByTestId('qif-confirm-button'));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'View Portfolio' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'View Portfolio' }));
    expect(onImported).toHaveBeenCalledTimes(1);
  });
});
