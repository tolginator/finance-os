import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { QifImporter } from '../src/components/QifImporter';
import { server } from './mocks/server';

describe('QifImporter', () => {
  it('shows file input in the idle state', () => {
    render(<QifImporter onImported={() => {}} />);

    expect(screen.getByTestId('qif-importer')).toBeInTheDocument();
    expect(screen.getByTestId('qif-file-input')).toBeInTheDocument();
    expect(screen.getByTestId('qif-household-name')).toHaveValue('My Household');
    expect(screen.getByTestId('qif-preview-button')).toBeDisabled();
  });

  it('shows account preview after selecting a file and previewing', async () => {
    render(<QifImporter onImported={() => {}} />);

    const file = new File(['!Type:Invst\n^'], 'test.qif', { type: 'text/plain' });
    fireEvent.change(screen.getByTestId('qif-file-input'), { target: { files: [file] } });
    fireEvent.click(screen.getByTestId('qif-preview-button'));

    await waitFor(() => {
      expect(screen.getByTestId('qif-preview-accounts')).toBeInTheDocument();
    });
    expect(screen.getByText('Investment Account')).toBeInTheDocument();
    expect(screen.getByText('Tax lots: 1')).toBeInTheDocument();
  });

  it('shows warnings when preview returns them', async () => {
    server.use(
      http.post('/api/household/import/qif/preview', () =>
        HttpResponse.json({
          accounts: [],
          warnings: [{ line: 12, message: 'Skipped unsupported record' }],
          position_only: true,
        }),
      ),
    );

    render(<QifImporter onImported={() => {}} />);

    const file = new File(['!Type:Invst\nwarning\n^'], 'warning.qif', { type: 'text/plain' });
    fireEvent.change(screen.getByTestId('qif-file-input'), { target: { files: [file] } });
    fireEvent.click(screen.getByTestId('qif-preview-button'));

    await waitFor(() => {
      expect(screen.getByTestId('qif-preview-warnings')).toBeInTheDocument();
    });
    expect(screen.getByText('Line 12: Skipped unsupported record')).toBeInTheDocument();
    expect(screen.getByText('Position-only import: Yes')).toBeInTheDocument();
  });

  it('clicking confirm saves and shows success message', async () => {
    render(<QifImporter onImported={() => {}} />);

    const file = new File(['!Type:Invst\n^'], 'confirm.qif', { type: 'text/plain' });
    fireEvent.change(screen.getByTestId('qif-file-input'), { target: { files: [file] } });
    fireEvent.click(screen.getByTestId('qif-preview-button'));

    await waitFor(() => {
      expect(screen.getByTestId('qif-confirm-button')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('qif-confirm-button'));

    await waitFor(() => {
      expect(screen.getByTestId('qif-success')).toBeInTheDocument();
    });
    expect(screen.getByText('Imported 1 account from QIF file.')).toBeInTheDocument();
  });

  it('clicking cancel returns to idle state', async () => {
    render(<QifImporter onImported={() => {}} />);

    const file = new File(['!Type:Invst\n^'], 'cancel.qif', { type: 'text/plain' });
    fireEvent.change(screen.getByTestId('qif-file-input'), { target: { files: [file] } });
    fireEvent.click(screen.getByTestId('qif-preview-button'));

    await waitFor(() => {
      expect(screen.getByTestId('qif-confirm-button')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('qif-cancel-button'));

    expect(screen.queryByTestId('qif-confirm-button')).not.toBeInTheDocument();
    expect(screen.getByTestId('qif-preview-button')).toBeDisabled();
  });

  it('shows an error state on network failure', async () => {
    server.use(
      http.post('/api/household/import/qif/preview', () =>
        HttpResponse.json({ detail: 'Preview failed' }, { status: 500 }),
      ),
    );

    render(<QifImporter onImported={() => {}} />);

    const file = new File(['!Type:Invst\n^'], 'error.qif', { type: 'text/plain' });
    fireEvent.change(screen.getByTestId('qif-file-input'), { target: { files: [file] } });
    fireEvent.click(screen.getByTestId('qif-preview-button'));

    await waitFor(() => {
      expect(screen.getByText('Preview failed')).toBeInTheDocument();
    });
    expect(screen.queryByTestId('qif-preview-accounts')).not.toBeInTheDocument();
  });

  it('calls onImported when the user chooses to view the portfolio', async () => {
    const onImported = vi.fn();
    render(<QifImporter onImported={onImported} />);

    const file = new File(['!Type:Invst\n^'], 'done.qif', { type: 'text/plain' });
    fireEvent.change(screen.getByTestId('qif-file-input'), { target: { files: [file] } });
    fireEvent.click(screen.getByTestId('qif-preview-button'));

    await waitFor(() => {
      expect(screen.getByTestId('qif-confirm-button')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('qif-confirm-button'));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'View Portfolio' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'View Portfolio' }));
    expect(onImported).toHaveBeenCalledTimes(1);
  });
});
