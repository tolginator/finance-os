import { goalsMock, investmentPolicyMock, type AssetClass, type Goal } from '../mockData';

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

function formatCurrency(value: string | null): string {
  if (!value) return 'Open-ended';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(Number.parseFloat(value));
}

function formatPercent(value: string): string {
  return `${(Number.parseFloat(value) * 100).toFixed(0)}%`;
}

function typeBadge(goal: Goal): { label: string; color: string; background: string } {
  switch (goal.goal_type) {
    case 'retirement':
      return { label: 'Retirement', color: '#1d4ed8', background: '#dbeafe' };
    case 'wealth_building':
      return { label: 'Wealth Building', color: '#065f46', background: '#d1fae5' };
    default:
      return { label: 'Custom', color: '#92400e', background: '#fef3c7' };
  }
}

export function GoalEditor() {
  return (
    <div data-testid="goal-editor" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div data-testid="goal-list" style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {goalsMock.map((goal) => {
          const badge = typeBadge(goal);
          return (
            <div
              key={goal.id}
              data-testid={`goal-${goal.id}`}
              style={{ border: '1px solid #e5e7eb', borderRadius: 12, padding: '1rem', background: '#fff' }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '0.5rem' }}>
                <div>
                  <div style={{ fontWeight: 600 }}>{goal.name}</div>
                  <div style={{ fontSize: '0.85rem', color: '#6b7280' }}>Priority {goal.priority}</div>
                </div>
                <span
                  style={{
                    alignSelf: 'start',
                    padding: '0.2rem 0.5rem',
                    borderRadius: 999,
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    color: badge.color,
                    background: badge.background,
                  }}
                >
                  {badge.label}
                </span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '0.5rem', fontSize: '0.85rem' }}>
                <div>Target: <strong>{formatCurrency(goal.target_amount)}</strong></div>
                <div>Timeline: <strong>{goal.target_date ?? 'Flexible'}</strong></div>
                <div>Horizon: <strong>{goal.time_horizon_years ? `${goal.time_horizon_years} years` : 'N/A'}</strong></div>
                <div>Withdrawal rate: <strong>{goal.withdrawal_rate ? formatPercent(goal.withdrawal_rate) : 'N/A'}</strong></div>
              </div>
            </div>
          );
        })}
      </div>

      <table data-testid="policy-table" style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
        <thead>
          <tr style={{ textAlign: 'left', borderBottom: '1px solid #e5e7eb' }}>
            <th style={{ padding: '0.5rem 0.25rem' }}>Asset class</th>
            <th style={{ padding: '0.5rem 0.25rem' }}>Target</th>
            <th style={{ padding: '0.5rem 0.25rem' }}>Min</th>
            <th style={{ padding: '0.5rem 0.25rem' }}>Max</th>
          </tr>
        </thead>
        <tbody>
          {(Object.keys(investmentPolicyMock.allocations) as AssetClass[]).map((assetClass) => {
            const allocation = investmentPolicyMock.allocations[assetClass];
            return (
              <tr key={assetClass} style={{ borderBottom: '1px solid #f3f4f6' }}>
                <td style={{ padding: '0.5rem 0.25rem', fontWeight: 500 }}>{ASSET_CLASS_LABELS[assetClass]}</td>
                <td style={{ padding: '0.5rem 0.25rem' }}>{formatPercent(allocation.target_weight)}</td>
                <td style={{ padding: '0.5rem 0.25rem' }}>{formatPercent(allocation.min_weight)}</td>
                <td style={{ padding: '0.5rem 0.25rem' }}>{formatPercent(allocation.max_weight)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}