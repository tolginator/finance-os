import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { PortfolioView } from '../src/components/PortfolioView';
import { server } from './mocks/server';

const householdFixture = {
  exists: true,
  household: {
    name: 'Family Office',
    liquidity_reserve_floor: '100000',
    revision: 4,
    updated_at: '2025-03-01T12:00:00Z',
    accounts: [
      {
        name: 'Joint Taxable',
        account_type: 'taxable',
        tax_lots: [
          { ticker: 'VTI', shares: '10', cost_basis_per_share: '250.00', purchase_date: '2024-01-15' },
          { ticker: 'VXUS', shares: '5', cost_basis_per_share: '60.50', purchase_date: '2024-02-20' },
        ],
        cash_holdings: [
          {
            amount: '1000',
            valuation_date: '2025-03-01',
            is_money_market: true,
            ticker: null,
            counts_toward_liquidity_reserve: true,
          },
        ],
      },
      {
        name: 'Traditional IRA',
        account_type: 'traditional_ira',
        tax_lots: [
          { ticker: 'BND', shares: '20', cost_basis_per_share: '72.10', purchase_date: '2023-11-10' },
        ],
        cash_holdings: [],
      },
    ],
  },
};

describe('PortfolioView', () => {
  it('shows a loading state before household data resolves', async () => {
    server.use(
      http.get('/api/household', async () => {
        await new Promise((resolve) => setTimeout(resolve, 500));
        return HttpResponse.json(householdFixture);
      }),
    );

    render(<PortfolioView />);

    expect(screen.getByTestId('portfolio-loading')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByTestId('portfolio-accounts')).toBeInTheDocument();
    });
  });

  it('shows an empty state when no household is configured', async () => {
    server.use(
      http.get('/api/household', () =>
        HttpResponse.json({
          exists: false,
          household: {
            name: '',
            accounts: [],
            liquidity_reserve_floor: '0',
            revision: 0,
            updated_at: '2025-03-01T00:00:00Z',
          },
        }),
      ),
    );

    render(<PortfolioView />);

    await waitFor(() => {
      expect(screen.getByTestId('portfolio-empty')).toBeInTheDocument();
    });
  });

  it('renders household accounts from the API response', async () => {
    server.use(http.get('/api/household', () => HttpResponse.json(householdFixture)));

    render(<PortfolioView />);

    await waitFor(() => {
      expect(screen.getByTestId('portfolio-accounts')).toBeInTheDocument();
    });
    expect(screen.getByTestId('account-Joint Taxable')).toBeInTheDocument();
    expect(screen.getByTestId('account-Traditional IRA')).toBeInTheDocument();
    expect(screen.getByTestId('holdings-table-Joint Taxable')).toBeInTheDocument();
    expect(screen.getByText('Family Office')).toBeInTheDocument();
    expect(screen.getByText('Cost Basis: $3,802.50')).toBeInTheDocument();
  });

  it('toggles account holdings with aria attributes intact', async () => {
    server.use(http.get('/api/household', () => HttpResponse.json(householdFixture)));

    render(<PortfolioView />);

    await waitFor(() => {
      expect(screen.getByTestId('account-Joint Taxable')).toBeInTheDocument();
    });

    const button = screen.getByTestId('account-Joint Taxable').querySelector('button');
    expect(button).not.toBeNull();
    expect(button).toHaveAttribute('aria-expanded', 'true');
    expect(button).toHaveAttribute('aria-controls', 'holdings-joint-taxable');
    expect(screen.getByTestId('holdings-table-Joint Taxable')).toBeInTheDocument();

    fireEvent.click(button!);
    expect(button).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByTestId('holdings-table-Joint Taxable')).not.toBeInTheDocument();

    fireEvent.click(button!);
    expect(button).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByTestId('holdings-table-Joint Taxable')).toBeInTheDocument();
  });
});
