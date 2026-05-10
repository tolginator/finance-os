import { useMemo, useState } from 'react';
import { type AssetClass, householdMock } from '../mockData';

const ETF_PRICE_MAP: Record<string, number> = {
  VTI: 280,
  VXUS: 67,
  VWO: 44,
  BND: 72,
  VTIP: 50,
  VNQ: 90,
  SGOV: 100,
  LQD: 107,
  HYG: 78,
  GLDM: 46,
};

const ETF_ASSET_CLASS_MAP: Record<string, AssetClass> = {
  VTI: 'us_equity',
  VXUS: 'intl_developed',
  VWO: 'emerging_markets',
  BND: 'us_treasuries',
  VTIP: 'tips',
  VNQ: 'real_assets',
  SGOV: 'cash_money_market',
  LQD: 'ig_corporate',
  HYG: 'high_yield',
  GLDM: 'real_assets',
};

const ASSET_CLASS_LABELS: Record<AssetClass, string> = {
  us_equity: 'US Equity',
  intl_developed: 'Intl Developed',
  emerging_markets: 'Emerging Markets',
  us_treasuries: 'US Treasuries',
  ig_corporate: 'IG Corporate',
  high_yield: 'High Yield',
  tips: 'TIPS',
  real_assets: 'Real Assets',
  cash_money_market: 'Cash / MMF',
};

const ALL_ASSET_CLASSES = Object.keys(ASSET_CLASS_LABELS) as AssetClass[];

function toNumber(value: string): number {
  return Number.parseFloat(value);
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(value);
}

function formatShares(value: string): string {
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 }).format(toNumber(value));
}

export function PortfolioView() {
  const [expandedAccounts, setExpandedAccounts] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(householdMock.accounts.map((account) => [account.name, true])),
  );

  const { totalNav, exposures } = useMemo(() => {
    const nextExposures = Object.fromEntries(ALL_ASSET_CLASSES.map((assetClass) => [assetClass, 0])) as Record<AssetClass, number>;
    let nav = 0;

    for (const account of householdMock.accounts) {
      for (const lot of account.tax_lots) {
        const price = ETF_PRICE_MAP[lot.ticker] ?? 0;
        const value = toNumber(lot.shares) * price;
        nav += value;
        const assetClass = ETF_ASSET_CLASS_MAP[lot.ticker] ?? 'cash_money_market';
        nextExposures[assetClass] += value;
      }

      for (const cashHolding of account.cash_holdings) {
        const amount = toNumber(cashHolding.amount);
        nav += amount;
        nextExposures.cash_money_market += amount;
      }
    }

    return { totalNav: nav, exposures: nextExposures };
  }, []);

  const exposureRows = ALL_ASSET_CLASSES
    .map((assetClass) => ({
      assetClass,
      label: ASSET_CLASS_LABELS[assetClass],
      value: exposures[assetClass],
      weight: totalNav === 0 ? 0 : exposures[assetClass] / totalNav,
    }))
    .filter((row) => row.value > 0)
    .sort((left, right) => right.value - left.value);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div
        data-testid="portfolio-nav"
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
          <div style={{ fontSize: '0.85rem', color: '#6b7280', marginBottom: '0.25rem' }}>Total household NAV</div>
          <div style={{ fontSize: '2rem', fontWeight: 700 }}>{formatCurrency(totalNav)}</div>
        </div>
        <div style={{ textAlign: 'right', fontSize: '0.9rem', color: '#4b5563' }}>
          <div>{householdMock.name}</div>
          <div>Last updated {new Date(householdMock.updated_at).toLocaleString()}</div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 2fr) minmax(280px, 1fr)', gap: '1rem', alignItems: 'start' }}>
        <div data-testid="portfolio-accounts" style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {householdMock.accounts.map((account) => {
            const isExpanded = expandedAccounts[account.name] ?? false;
            const accountValue = account.tax_lots.reduce((sum, lot) => sum + toNumber(lot.shares) * (ETF_PRICE_MAP[lot.ticker] ?? 0), 0)
              + account.cash_holdings.reduce((sum, holding) => sum + toNumber(holding.amount), 0);

            return (
              <div
                key={account.name}
                data-testid={`account-${account.name}`}
                style={{ border: '1px solid #e5e7eb', borderRadius: 12, overflow: 'hidden' }}
              >
                <button
                  type="button"
                  onClick={() => setExpandedAccounts((current) => ({ ...current, [account.name]: !isExpanded }))}
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
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 600 }}>{account.name}</div>
                    <div style={{ fontSize: '0.85rem', color: '#6b7280' }}>{account.account_type}</div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontWeight: 600 }}>{formatCurrency(accountValue)}</div>
                    <div style={{ fontSize: '0.85rem', color: '#6b7280' }}>{isExpanded ? 'Hide holdings' : 'Show holdings'}</div>
                  </div>
                </button>

                {isExpanded && (
                  <div style={{ padding: '0 1rem 1rem' }}>
                    <table
                      data-testid={`holdings-table-${account.name}`}
                      style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}
                    >
                      <thead>
                        <tr style={{ textAlign: 'left', borderBottom: '1px solid #e5e7eb' }}>
                          <th style={{ padding: '0.5rem 0.25rem' }}>Ticker</th>
                          <th style={{ padding: '0.5rem 0.25rem' }}>Shares</th>
                          <th style={{ padding: '0.5rem 0.25rem' }}>Cost basis / share</th>
                          <th style={{ padding: '0.5rem 0.25rem' }}>Current value</th>
                        </tr>
                      </thead>
                      <tbody>
                        {account.tax_lots.map((lot) => (
                          <tr key={`${account.name}-${lot.ticker}-${lot.purchase_date}`} style={{ borderBottom: '1px solid #f3f4f6' }}>
                            <td style={{ padding: '0.5rem 0.25rem', fontWeight: 600 }}>{lot.ticker}</td>
                            <td style={{ padding: '0.5rem 0.25rem' }}>{formatShares(lot.shares)}</td>
                            <td style={{ padding: '0.5rem 0.25rem' }}>{formatCurrency(toNumber(lot.cost_basis_per_share))}</td>
                            <td style={{ padding: '0.5rem 0.25rem' }}>{formatCurrency(toNumber(lot.shares) * (ETF_PRICE_MAP[lot.ticker] ?? 0))}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>

                    <div style={{ marginTop: '0.75rem', fontSize: '0.85rem', color: '#4b5563' }}>
                      {account.cash_holdings.map((holding, index) => (
                        <div key={`${account.name}-cash-${index}`}>
                          Cash reserve: {formatCurrency(toNumber(holding.amount))} · valued {holding.valuation_date}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <div
          data-testid="exposure-summary"
          style={{ border: '1px solid #e5e7eb', borderRadius: 12, padding: '1rem', background: 'white' }}
        >
          <h3 style={{ margin: '0 0 0.75rem', fontSize: '1rem' }}>Asset class exposure</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {exposureRows.map((row) => (
              <div key={row.assetClass}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', marginBottom: '0.25rem' }}>
                  <span>{row.label}</span>
                  <span>{formatCurrency(row.value)} · {(row.weight * 100).toFixed(1)}%</span>
                </div>
                <div style={{ height: 10, borderRadius: 999, background: '#e5e7eb', overflow: 'hidden' }}>
                  <div
                    style={{
                      width: `${Math.max(row.weight * 100, 2)}%`,
                      height: '100%',
                      background: '#2563eb',
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}