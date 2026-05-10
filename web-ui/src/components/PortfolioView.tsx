import { useEffect, useState } from 'react';
import { fetchHousehold } from '../api';
import type { Account, HouseholdResponse } from '../types';

type LoadState =
  | { status: 'loading' }
  | { status: 'error'; error: string }
  | { status: 'loaded'; data: HouseholdResponse };

function toSlug(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
}

function parseDecimal(value: string): { negative: boolean; digits: bigint; scale: number } {
  const trimmed = value.trim();
  const negative = trimmed.startsWith('-');
  const unsigned = negative ? trimmed.slice(1) : trimmed;
  const [integerPart = '0', fractionalPart = ''] = unsigned.split('.');
  const normalizedInteger = integerPart.replace(/^0+(?=\d)/, '') || '0';
  const normalizedFraction = fractionalPart.replace(/0+$/, '');
  const digits = `${normalizedInteger}${normalizedFraction}`.replace(/^0+(?=\d)/, '') || '0';
  return { negative, digits: BigInt(digits), scale: normalizedFraction.length };
}

function decimalToString(negative: boolean, digits: bigint, scale: number): string {
  if (digits === 0n) return '0';
  const raw = digits.toString().padStart(scale + 1, '0');
  const splitIndex = raw.length - scale;
  const integerPart = splitIndex > 0 ? raw.slice(0, splitIndex) : '0';
  const fractionalPart = splitIndex > 0 ? raw.slice(splitIndex) : raw;
  const normalizedFraction = scale === 0 ? '' : fractionalPart.replace(/0+$/, '');
  const prefix = negative ? '-' : '';
  return normalizedFraction ? `${prefix}${integerPart}.${normalizedFraction}` : `${prefix}${integerPart}`;
}

function addDecimalStrings(left: string, right: string): string {
  const parsedLeft = parseDecimal(left);
  const parsedRight = parseDecimal(right);
  const scale = Math.max(parsedLeft.scale, parsedRight.scale);
  const leftFactor = 10n ** BigInt(scale - parsedLeft.scale);
  const rightFactor = 10n ** BigInt(scale - parsedRight.scale);
  const leftValue = (parsedLeft.negative ? -1n : 1n) * parsedLeft.digits * leftFactor;
  const rightValue = (parsedRight.negative ? -1n : 1n) * parsedRight.digits * rightFactor;
  const total = leftValue + rightValue;
  const negative = total < 0n;
  const digits = negative ? -total : total;
  return decimalToString(negative, digits, scale);
}

function multiplyDecimalStrings(left: string, right: string): string {
  const parsedLeft = parseDecimal(left);
  const parsedRight = parseDecimal(right);
  const negative = parsedLeft.negative !== parsedRight.negative;
  const digits = parsedLeft.digits * parsedRight.digits;
  const scale = parsedLeft.scale + parsedRight.scale;
  return decimalToString(negative, digits, scale);
}

function roundDecimalString(value: string, scale: number): string {
  const parsed = parseDecimal(value);
  if (parsed.scale <= scale) {
    return decimalToString(parsed.negative, parsed.digits * 10n ** BigInt(scale - parsed.scale), scale);
  }

  const divisor = 10n ** BigInt(parsed.scale - scale);
  let quotient = parsed.digits / divisor;
  const remainder = parsed.digits % divisor;
  if (remainder * 2n >= divisor) quotient += 1n;
  return decimalToString(parsed.negative, quotient, scale);
}

function formatCurrency(value: string): string {
  const rounded = roundDecimalString(value, 2);
  const negative = rounded.startsWith('-');
  const unsigned = negative ? rounded.slice(1) : rounded;
  const [integerPart, fractionalPart = '00'] = unsigned.split('.');
  const groupedInteger = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  return `${negative ? '-' : ''}$${groupedInteger}.${fractionalPart.padEnd(2, '0')}`;
}

function formatShares(value: string): string {
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: 4 }).format(Number.parseFloat(value));
}

function formatDate(value: string): string {
  return new Date(value).toLocaleDateString();
}

function getAccountCostBasis(account: Account): string {
  let total = '0';

  for (const lot of account.tax_lots) {
    total = addDecimalStrings(total, multiplyDecimalStrings(lot.shares, lot.cost_basis_per_share));
  }

  for (const cashHolding of account.cash_holdings) {
    total = addDecimalStrings(total, cashHolding.amount);
  }

  return total;
}

export function PortfolioView() {
  const [state, setState] = useState<LoadState>({ status: 'loading' });
  const [expandedAccounts, setExpandedAccounts] = useState<Record<string, boolean>>({});

  useEffect(() => {
    let cancelled = false;

    async function loadHousehold() {
      try {
        const data = await fetchHousehold();
        if (cancelled) return;
        setExpandedAccounts(Object.fromEntries(data.household.accounts.map((account) => [account.name, true])));
        setState({ status: 'loaded', data });
      } catch (error) {
        if (cancelled) return;
        setState({
          status: 'error',
          error: error instanceof Error ? error.message : 'Unable to load household portfolio.',
        });
      }
    }

    loadHousehold();

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div data-testid="portfolio-view" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {state.status === 'loading' && (
        <div
          data-testid="portfolio-loading"
          style={{ border: '1px solid #e5e7eb', borderRadius: 12, padding: '1rem', background: '#fff' }}
        >
          Loading household portfolio…
        </div>
      )}

      {state.status === 'error' && (
        <div
          data-testid="portfolio-error"
          style={{ border: '1px solid #fecaca', borderRadius: 12, padding: '1rem', background: '#fef2f2', color: '#b91c1c' }}
        >
          {state.error}
        </div>
      )}

      {state.status === 'loaded' && !state.data.exists && (
        <div
          data-testid="portfolio-empty"
          style={{ border: '1px solid #e5e7eb', borderRadius: 12, padding: '1rem', background: '#fff', color: '#4b5563' }}
        >
          No household portfolio is configured yet.
        </div>
      )}

      {state.status === 'loaded' && state.data.exists && (
        <>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              gap: '1rem',
              alignItems: 'end',
              flexWrap: 'wrap',
              padding: '1rem',
              border: '1px solid #e5e7eb',
              borderRadius: 12,
              background: '#f8fafc',
            }}
          >
            <div>
              <div style={{ fontSize: '1.1rem', fontWeight: 700 }}>{state.data.household.name}</div>
              <div style={{ fontSize: '0.9rem', color: '#4b5563' }}>Revision {state.data.household.revision}</div>
            </div>
            <div style={{ textAlign: 'right', fontSize: '0.9rem', color: '#4b5563' }}>
              <div>Liquidity reserve floor: {formatCurrency(state.data.household.liquidity_reserve_floor)}</div>
              <div>Updated {new Date(state.data.household.updated_at).toLocaleString()}</div>
            </div>
          </div>

          <div data-testid="portfolio-accounts" style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {state.data.household.accounts.map((account) => {
              const isExpanded = expandedAccounts[account.name] ?? false;
              const slug = toSlug(account.name);
              const totalCostBasis = getAccountCostBasis(account);
              const holdingsCount = account.tax_lots.length + account.cash_holdings.length;

              return (
                <div
                  key={account.name}
                  data-testid={`account-${account.name}`}
                  style={{ border: '1px solid #e5e7eb', borderRadius: 12, overflow: 'hidden', background: '#fff' }}
                >
                  <button
                    type="button"
                    aria-expanded={isExpanded}
                    aria-controls={`holdings-${slug}`}
                    onClick={() => setExpandedAccounts((current) => ({ ...current, [account.name]: !(current[account.name] ?? false) }))}
                    style={{
                      width: '100%',
                      background: 'white',
                      border: 'none',
                      padding: '1rem',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      cursor: 'pointer',
                      textAlign: 'left',
                      gap: '1rem',
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 600 }}>{account.name}</div>
                      <div style={{ fontSize: '0.85rem', color: '#6b7280' }}>
                        {account.account_type} · {holdingsCount} holdings
                      </div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontWeight: 600 }}>Cost Basis: {formatCurrency(totalCostBasis)}</div>
                      <div style={{ fontSize: '0.85rem', color: '#6b7280' }}>{isExpanded ? 'Hide holdings' : 'Show holdings'}</div>
                    </div>
                  </button>

                  {isExpanded && (
                    <div id={`holdings-${slug}`} style={{ padding: '0 1rem 1rem' }}>
                      <table
                        data-testid={`holdings-table-${account.name}`}
                        style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}
                      >
                        <thead>
                          <tr style={{ textAlign: 'left', borderBottom: '1px solid #e5e7eb' }}>
                            <th style={{ padding: '0.5rem 0.25rem' }}>Ticker</th>
                            <th style={{ padding: '0.5rem 0.25rem' }}>Shares</th>
                            <th style={{ padding: '0.5rem 0.25rem' }}>Cost Basis / Share</th>
                            <th style={{ padding: '0.5rem 0.25rem' }}>Purchase Date</th>
                            <th style={{ padding: '0.5rem 0.25rem' }}>Lot Cost Basis</th>
                          </tr>
                        </thead>
                        <tbody>
                          {account.tax_lots.length === 0 ? (
                            <tr>
                              <td colSpan={5} style={{ padding: '0.75rem 0.25rem', color: '#6b7280' }}>
                                No tax lots available.
                              </td>
                            </tr>
                          ) : (
                            account.tax_lots.map((lot) => (
                              <tr key={`${account.name}-${lot.ticker}-${lot.purchase_date}`} style={{ borderBottom: '1px solid #f3f4f6' }}>
                                <td style={{ padding: '0.5rem 0.25rem', fontWeight: 600 }}>{lot.ticker}</td>
                                <td style={{ padding: '0.5rem 0.25rem' }}>{formatShares(lot.shares)}</td>
                                <td style={{ padding: '0.5rem 0.25rem' }}>{formatCurrency(lot.cost_basis_per_share)}</td>
                                <td style={{ padding: '0.5rem 0.25rem' }}>{formatDate(lot.purchase_date)}</td>
                                <td style={{ padding: '0.5rem 0.25rem' }}>{formatCurrency(multiplyDecimalStrings(lot.shares, lot.cost_basis_per_share))}</td>
                              </tr>
                            ))
                          )}
                        </tbody>
                      </table>

                      <div style={{ marginTop: '0.75rem', display: 'flex', flexDirection: 'column', gap: '0.35rem', fontSize: '0.85rem', color: '#4b5563' }}>
                        {account.cash_holdings.length === 0 ? (
                          <div>No cash holdings reported.</div>
                        ) : (
                          account.cash_holdings.map((holding, index) => (
                            <div key={`${account.name}-cash-${index}`}>
                              Cash holding: {formatCurrency(holding.amount)} · {holding.is_money_market ? 'Money market' : 'Cash'} ·
                              Valuation date {formatDate(holding.valuation_date)}
                            </div>
                          ))
                        )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
