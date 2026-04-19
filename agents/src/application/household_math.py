"""Pure domain helpers for household portfolio math.

Stateless functions — no I/O, no side effects.  Easy to test
independently of persistence or API layers.

All arithmetic uses ``decimal.Decimal``.
"""

from collections import defaultdict
from decimal import Decimal

from src.application.contracts.household import Account, Household, TaxLot


def total_cash(account: Account) -> Decimal:
    """Sum of all cash holdings in an account."""
    return sum((h.amount for h in account.cash_holdings), Decimal("0"))


def total_cash_household(household: Household) -> Decimal:
    """Sum of all cash holdings across every account."""
    return sum((total_cash(a) for a in household.accounts), Decimal("0"))


def liquidity_reserve_cash(household: Household) -> Decimal:
    """Sum of cash holdings that count toward the liquidity reserve."""
    total = Decimal("0")
    for account in household.accounts:
        for ch in account.cash_holdings:
            if ch.counts_toward_liquidity_reserve:
                total += ch.amount
    return total


def aggregate_lots(lots: list[TaxLot]) -> dict[str, Decimal]:
    """Aggregate tax lots into total shares per ticker.

    Returns:
        ``{ticker: total_shares}``
    """
    agg: dict[str, Decimal] = defaultdict(Decimal)
    for lot in lots:
        agg[lot.ticker] += lot.shares
    return dict(agg)


def total_cost_basis(lots: list[TaxLot]) -> Decimal:
    """Total cost basis across all lots (shares × cost_basis_per_share)."""
    return sum(
        (lot.shares * lot.cost_basis_per_share for lot in lots),
        Decimal("0"),
    )


def cost_basis_by_ticker(lots: list[TaxLot]) -> dict[str, Decimal]:
    """Total cost basis per ticker."""
    basis: dict[str, Decimal] = defaultdict(Decimal)
    for lot in lots:
        basis[lot.ticker] += lot.shares * lot.cost_basis_per_share
    return dict(basis)


def account_summary(account: Account) -> dict[str, Decimal]:
    """Quick summary for an account: shares per ticker + total cash."""
    result = aggregate_lots(account.tax_lots)
    result["_cash"] = total_cash(account)
    return result


def household_summary(household: Household) -> dict[str, dict[str, Decimal]]:
    """Per-account summary of positions and cash.

    Returns:
        ``{account_name: {ticker: shares, "_cash": cash_amount}}``
    """
    return {a.name: account_summary(a) for a in household.accounts}


def lot_count(household: Household) -> int:
    """Total number of tax lots across all accounts."""
    return sum(len(a.tax_lots) for a in household.accounts)


def cash_holding_count(household: Household) -> int:
    """Total number of cash holding records across all accounts."""
    return sum(len(a.cash_holdings) for a in household.accounts)


def unique_tickers(household: Household) -> set[str]:
    """Set of all unique tickers held across the household."""
    tickers: set[str] = set()
    for account in household.accounts:
        for lot in account.tax_lots:
            tickers.add(lot.ticker)
    return tickers


def has_complete_lots(household: Household) -> bool:
    """True if all lots have non-zero cost basis and a meaningful date.

    Used to gate tax-lot-dependent features (tax drag, TLH).
    """
    for account in household.accounts:
        for lot in account.tax_lots:
            if lot.cost_basis_per_share == Decimal("0"):
                return False
    return True
