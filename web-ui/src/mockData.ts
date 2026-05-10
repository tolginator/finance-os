export interface TaxLot {
  ticker: string;
  shares: string;
  cost_basis_per_share: string;
  purchase_date: string;
}

export interface CashHolding {
  amount: string;
  valuation_date: string;
  is_money_market: boolean;
  ticker: string | null;
  counts_toward_liquidity_reserve: boolean;
}

export interface Account {
  name: string;
  account_type: string;
  tax_lots: TaxLot[];
  cash_holdings: CashHolding[];
}

export interface Household {
  name: string;
  accounts: Account[];
  liquidity_reserve_floor: string;
  revision: number;
  updated_at: string;
}

export type AssetClass =
  | 'us_equity'
  | 'intl_developed'
  | 'emerging_markets'
  | 'us_treasuries'
  | 'ig_corporate'
  | 'high_yield'
  | 'tips'
  | 'real_assets'
  | 'cash_money_market';

export interface Goal {
  id: string;
  name: string;
  goal_type: 'retirement' | 'wealth_building' | 'custom';
  priority: number;
  target_amount: string | null;
  target_date: string | null;
  time_horizon_years: number | null;
  withdrawal_rate: string | null;
}

export interface AllocationTarget {
  target_weight: string;
  min_weight: string;
  max_weight: string;
}

export interface InvestmentPolicy {
  allocations: Record<AssetClass, AllocationTarget>;
}

export interface RegimeDimension {
  regime: string;
  trend: string;
  confidence: string;
}

export interface MacroRegime {
  growth: RegimeDimension;
  rates: RegimeDimension;
  inflation: RegimeDimension;
  overall_confidence: string;
  as_of: string;
}

export const householdMock: Household = {
  name: 'Harrington Family Household',
  liquidity_reserve_floor: '250000',
  revision: 7,
  updated_at: '2025-02-14T15:30:00Z',
  accounts: [
    {
      name: 'Joint Taxable',
      account_type: 'taxable',
      tax_lots: [
        { ticker: 'VTI', shares: '1700', cost_basis_per_share: '228.10', purchase_date: '2021-03-18' },
        { ticker: 'VXUS', shares: '700', cost_basis_per_share: '58.42', purchase_date: '2022-01-11' },
        { ticker: 'VWO', shares: '600', cost_basis_per_share: '40.15', purchase_date: '2022-10-04' },
        { ticker: 'BND', shares: '1800', cost_basis_per_share: '74.10', purchase_date: '2023-06-21' },
        { ticker: 'VTIP', shares: '1000', cost_basis_per_share: '48.75', purchase_date: '2024-02-09' },
        { ticker: 'VNQ', shares: '700', cost_basis_per_share: '83.90', purchase_date: '2021-09-30' },
        { ticker: 'SGOV', shares: '2200', cost_basis_per_share: '100.08', purchase_date: '2024-11-05' },
      ],
      cash_holdings: [
        {
          amount: '170000',
          valuation_date: '2025-02-14',
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
        { ticker: 'VTI', shares: '1200', cost_basis_per_share: '214.35', purchase_date: '2020-07-15' },
        { ticker: 'VXUS', shares: '900', cost_basis_per_share: '55.48', purchase_date: '2021-11-19' },
        { ticker: 'BND', shares: '2500', cost_basis_per_share: '73.40', purchase_date: '2023-08-07' },
        { ticker: 'LQD', shares: '1200', cost_basis_per_share: '104.90', purchase_date: '2024-01-12' },
        { ticker: 'HYG', shares: '800', cost_basis_per_share: '75.88', purchase_date: '2024-04-26' },
        { ticker: 'VTIP', shares: '900', cost_basis_per_share: '49.12', purchase_date: '2024-05-17' },
        { ticker: 'GLDM', shares: '1800', cost_basis_per_share: '42.30', purchase_date: '2023-10-03' },
      ],
      cash_holdings: [
        {
          amount: '35000',
          valuation_date: '2025-02-14',
          is_money_market: false,
          ticker: null,
          counts_toward_liquidity_reserve: false,
        },
      ],
    },
    {
      name: 'Roth IRA',
      account_type: 'roth_ira',
      tax_lots: [
        { ticker: 'VTI', shares: '650', cost_basis_per_share: '198.40', purchase_date: '2019-04-22' },
        { ticker: 'VWO', shares: '500', cost_basis_per_share: '39.24', purchase_date: '2021-05-13' },
        { ticker: 'VNQ', shares: '400', cost_basis_per_share: '81.55', purchase_date: '2020-12-10' },
        { ticker: 'GLDM', shares: '500', cost_basis_per_share: '39.70', purchase_date: '2022-06-29' },
        { ticker: 'VTIP', shares: '300', cost_basis_per_share: '47.95', purchase_date: '2024-03-28' },
      ],
      cash_holdings: [
        {
          amount: '12000',
          valuation_date: '2025-02-14',
          is_money_market: false,
          ticker: null,
          counts_toward_liquidity_reserve: false,
        },
      ],
    },
    {
      name: '401(k)',
      account_type: '401k',
      tax_lots: [
        { ticker: 'VTI', shares: '1500', cost_basis_per_share: '209.70', purchase_date: '2020-02-14' },
        { ticker: 'VXUS', shares: '1100', cost_basis_per_share: '57.02', purchase_date: '2021-10-08' },
        { ticker: 'BND', shares: '3200', cost_basis_per_share: '72.90', purchase_date: '2023-07-11' },
        { ticker: 'VTIP', shares: '1000', cost_basis_per_share: '48.88', purchase_date: '2024-01-26' },
        { ticker: 'VNQ', shares: '700', cost_basis_per_share: '84.05', purchase_date: '2022-02-18' },
        { ticker: 'SGOV', shares: '1200', cost_basis_per_share: '100.01', purchase_date: '2024-10-22' },
        { ticker: 'LQD', shares: '800', cost_basis_per_share: '105.10', purchase_date: '2024-06-14' },
      ],
      cash_holdings: [
        {
          amount: '30000',
          valuation_date: '2025-02-14',
          is_money_market: false,
          ticker: null,
          counts_toward_liquidity_reserve: false,
        },
      ],
    },
  ],
};

export const goalsMock: Goal[] = [
  {
    id: 'retirement-primary',
    name: 'Retirement Income Reserve',
    goal_type: 'retirement',
    priority: 1,
    target_amount: '6500000',
    target_date: '2035-12-31',
    time_horizon_years: 10,
    withdrawal_rate: '0.035',
  },
  {
    id: 'wealth-building-secondary',
    name: 'Multi-Generational Wealth Building',
    goal_type: 'wealth_building',
    priority: 2,
    target_amount: '10000000',
    target_date: '2045-12-31',
    time_horizon_years: 20,
    withdrawal_rate: null,
  },
];

export const investmentPolicyMock: InvestmentPolicy = {
  allocations: {
    us_equity: { target_weight: '0.38', min_weight: '0.32', max_weight: '0.44' },
    intl_developed: { target_weight: '0.12', min_weight: '0.08', max_weight: '0.16' },
    emerging_markets: { target_weight: '0.06', min_weight: '0.03', max_weight: '0.09' },
    us_treasuries: { target_weight: '0.18', min_weight: '0.14', max_weight: '0.24' },
    ig_corporate: { target_weight: '0.10', min_weight: '0.06', max_weight: '0.14' },
    high_yield: { target_weight: '0.03', min_weight: '0.00', max_weight: '0.05' },
    tips: { target_weight: '0.05', min_weight: '0.03', max_weight: '0.08' },
    real_assets: { target_weight: '0.05', min_weight: '0.02', max_weight: '0.08' },
    cash_money_market: { target_weight: '0.03', min_weight: '0.02', max_weight: '0.08' },
  },
};

export const macroRegimeMock: MacroRegime = {
  growth: {
    regime: 'expansion',
    trend: 'stable',
    confidence: 'high',
  },
  rates: {
    regime: 'rising',
    trend: 'rising',
    confidence: 'high',
  },
  inflation: {
    regime: 'moderate',
    trend: 'stable',
    confidence: 'moderate',
  },
  overall_confidence: 'moderate',
  as_of: '2025-02-14T08:00:00Z',
};