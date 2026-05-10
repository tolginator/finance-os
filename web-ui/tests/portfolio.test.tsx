import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { PortfolioView } from '../src/components/PortfolioView';

describe('PortfolioView', () => {
  it('renders nav, account cards, and exposure summary', () => {
    render(<PortfolioView />);
    expect(screen.getByTestId('portfolio-nav')).toBeInTheDocument();
    expect(screen.getByTestId('portfolio-accounts')).toBeInTheDocument();
    expect(screen.getByTestId('account-Joint Taxable')).toBeInTheDocument();
    expect(screen.getByTestId('account-Traditional IRA')).toBeInTheDocument();
    expect(screen.getByTestId('exposure-summary')).toBeInTheDocument();
  });

  it('renders holdings tables for each account', () => {
    render(<PortfolioView />);
    expect(screen.getByTestId('holdings-table-Joint Taxable')).toBeInTheDocument();
    expect(screen.getByTestId('holdings-table-Traditional IRA')).toBeInTheDocument();
    expect(screen.getByTestId('holdings-table-Roth IRA')).toBeInTheDocument();
    expect(screen.getByTestId('holdings-table-401(k)')).toBeInTheDocument();
  });
});