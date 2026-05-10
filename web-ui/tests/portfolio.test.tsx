import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
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

  it('toggles account holdings on click and updates aria-expanded', () => {
    render(<PortfolioView />);
    const button = screen.getByTestId('account-Joint Taxable').querySelector('button')!;
    // Starts expanded
    expect(button).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByTestId('holdings-table-Joint Taxable')).toBeInTheDocument();

    // Collapse
    fireEvent.click(button);
    expect(button).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByTestId('holdings-table-Joint Taxable')).not.toBeInTheDocument();

    // Re-expand
    fireEvent.click(button);
    expect(button).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByTestId('holdings-table-Joint Taxable')).toBeInTheDocument();
  });

  it('generates valid HTML ids for aria-controls', () => {
    render(<PortfolioView />);
    const button = screen.getByTestId('account-Joint Taxable').querySelector('button')!;
    const controlsId = button.getAttribute('aria-controls')!;
    // Must not contain spaces
    expect(controlsId).not.toMatch(/\s/);
    expect(controlsId).toBe('holdings-joint-taxable');
  });
});