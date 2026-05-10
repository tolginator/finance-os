"""QIF-to-household import preview mapping."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from pydantic import ValidationError

from src.application.contracts.household import (
    Account,
    AccountType,
    CashHolding,
    ImportPreviewResponse,
    ImportWarning,
    TaxLot,
)
from src.application.services.qif_parser import QifAccount, QifData, decode_qif_text, parse_qif

_ZERO = Decimal("0")
_TINY = Decimal("0.0001")

# Action classification — mirrors slicken/src/data/investmentActions.js
_BUY_ACTIONS = frozenset({
    "buy", "buyx",
    "reinvdiv", "reinvint", "reinvlg", "reinvmd", "reinvsh",
    "shrsin", "vest",
    "cover", "coverx", "cvrshrt",
})
_SELL_ACTIONS = frozenset({
    "sell", "sellx",
    "shrsout",
    "shtsell", "shtsellx",
    "exercise", "exercisx",
})
_INCOME_ACTIONS = frozenset({
    "div", "divx", "intinc", "intincx",
    "cgshort", "cgshortx", "cgmid", "cgmidx", "cglong", "cglongx",
    "miscinc", "miscincx", "rtrncap", "rtrncapx",
})
_SPLIT_ACTION = "stksplit"

# Patterns for inferring account type from name (checked in order).
_ACCOUNT_TYPE_PATTERNS: list[tuple[list[str], AccountType]] = [
    (["roth ira", "roth_ira", "rollover roth"], AccountType.ROTH_IRA),
    (["traditional ira", "trad ira", "rollover ira", "sep ira"], AccountType.TRADITIONAL_IRA),
    (
        ["401(k)", "401k", "403(b)", "403b", "401(a)", "401a", "457(b)", "457b", "dcp"],
        AccountType.FOUR01K,
    ),
    (["hsa"], AccountType.HSA),
    (["trust", "utma", "ugma", "529"], AccountType.TRUST),
]


def _infer_account_type(name: str) -> AccountType | None:
    """Infer account type from common patterns in account name."""
    lower = name.lower()
    for patterns, account_type in _ACCOUNT_TYPE_PATTERNS:
        for pat in patterns:
            if pat in lower:
                return account_type
    return None


def _split_ratio(quantity: Decimal) -> Decimal:
    """Decode QIF stock-split ratio (Quicken encodes as Q × 10)."""
    return quantity / Decimal("10")


@dataclass
class _Lot:
    """A single FIFO lot for position tracking."""

    purchase_date: date
    shares: Decimal
    price_per_share: Decimal
    cost_basis: Decimal


@dataclass
class _Holding:
    """Accumulated holding for one security in one account."""

    lots: list[_Lot] = field(default_factory=list)
    shares: Decimal = _ZERO
    total_cost_basis: Decimal = _ZERO
    last_price: Decimal = _ZERO
    last_price_date: date | None = None


def _compute_holdings(
    investments: list,
    security_symbols: dict[str, str],
    warnings: list[ImportWarning],
) -> dict[str, dict[str, _Holding]]:
    """Walk investment transactions chronologically, tracking FIFO lots.

    Mirrors slicken's ``computeHoldings()`` logic:
    - Buys add lots with cost basis
    - Sells consume lots FIFO, reducing shares and cost basis
    - Stock splits multiply shares and divide price across all lots
    - All arithmetic uses Decimal

    Returns:
        { account_name: { ticker: _Holding } }
    """
    # Sort chronologically
    sorted_txns = sorted(
        investments,
        key=lambda t: t.date or date.min,
    )

    holdings: dict[str, dict[str, _Holding]] = {}
    position_only = False

    for txn in sorted_txns:
        action = txn.action.strip().lower().replace(" ", "")
        security = txn.security.strip()

        if not action or action in _INCOME_ACTIONS:
            continue

        ticker, ticker_warning = _resolve_ticker(security, security_symbols)
        if ticker_warning is not None:
            warnings.append(ticker_warning)
        if not ticker:
            if action in _BUY_ACTIONS or action in _SELL_ACTIONS:
                warnings.append(ImportWarning(
                    message=(
                        f"Skipped investment transaction in account "
                        f"'{txn.account}' because no ticker could be resolved."
                    ),
                ))
                position_only = True
            continue

        acct_holdings = holdings.setdefault(txn.account, {})
        if ticker not in acct_holdings:
            acct_holdings[ticker] = _Holding()
        h = acct_holdings[ticker]

        qty = abs(txn.quantity)
        price = txn.price
        amount = abs(txn.amount)
        txn_date = txn.date or date.today()

        # Track last known price
        if price > _ZERO and txn.date is not None:
            if h.last_price_date is None or txn.date >= h.last_price_date:
                h.last_price = price
                h.last_price_date = txn.date

        # Stock split
        if action == _SPLIT_ACTION:
            ratio = _split_ratio(txn.quantity)
            if ratio > _ZERO and ratio != Decimal("1"):
                h.shares *= ratio
                for lot in h.lots:
                    lot.shares *= ratio
                    lot.price_per_share /= ratio
            continue

        # Buy / add shares
        if action in _BUY_ACTIONS:
            if qty <= _ZERO:
                warnings.append(ImportWarning(
                    message=(
                        f"Skipped {txn.action} transaction for {ticker} "
                        f"in account '{txn.account}' because shares "
                        f"were missing."
                    ),
                ))
                position_only = True
                continue

            cost = amount if amount > _ZERO else qty * price
            lot = _Lot(
                purchase_date=txn_date,
                shares=qty,
                price_per_share=cost / qty if qty > _ZERO else price,
                cost_basis=cost,
            )
            if price <= _ZERO and amount <= _ZERO:
                position_only = True
                warnings.append(ImportWarning(
                    message=(
                        f"Lot for {ticker} in account '{txn.account}' "
                        f"is missing cost basis — imported as "
                        f"position-only."
                    ),
                ))
            h.lots.append(lot)
            h.shares += qty
            h.total_cost_basis += cost
            continue

        # Sell / remove shares (FIFO)
        if action in _SELL_ACTIONS:
            if qty <= _ZERO:
                warnings.append(ImportWarning(
                    message=(
                        f"Skipped {txn.action} transaction for {ticker} "
                        f"in account '{txn.account}' because shares "
                        f"were missing."
                    ),
                ))
                continue

            remaining = qty
            cost_for_sold = _ZERO

            while remaining > _ZERO and h.lots:
                lot = h.lots[0]
                taken = min(remaining, lot.shares)
                lot_cost = taken * lot.price_per_share
                cost_for_sold += lot_cost
                lot.shares -= taken
                remaining -= taken

                if lot.shares <= _TINY:
                    h.lots.pop(0)

            h.shares -= qty
            h.total_cost_basis -= cost_for_sold
            # Clamp to zero if floating-point-like residual
            if h.shares < _ZERO:
                h.shares = _ZERO
            if h.total_cost_basis < _ZERO:
                h.total_cost_basis = _ZERO
            continue

        # Unsupported action
        warnings.append(ImportWarning(
            message=(
                f"Skipped unsupported investment action "
                f"'{txn.action}' in account '{txn.account}'."
            ),
        ))

    return holdings, position_only


def preview_qif_import(
    qif_content: str,
    household_name: str = "My Household",
) -> ImportPreviewResponse:
    """Parse QIF content and return proposed household accounts.

    Investment holdings are computed using FIFO lot tracking that mirrors
    slicken's ``computeHoldings()`` logic — buys add lots, sells consume
    them FIFO, stock splits adjust shares/price across all lots.  All
    arithmetic uses ``Decimal`` for accounting accuracy.

    Args:
        qif_content: Raw QIF file content.
        household_name: Household name supplied by the caller.

    Returns:
        Preview response containing proposed accounts, warnings, and a
        position-only flag when cost-basis fidelity is incomplete.
    """
    _ = household_name
    parsed = parse_qif(decode_qif_text(qif_content))
    warnings: list[ImportWarning] = []
    accounts_map: dict[str, Account] = {}
    security_symbols = _build_security_symbol_lookup(parsed)

    # --- 1. Create accounts from QIF account definitions ----------------
    for qif_account in parsed.accounts.values():
        account_type = _map_qif_account_type(qif_account, warnings)
        if account_type is None:
            continue

        account = accounts_map.setdefault(
            qif_account.name,
            Account(name=qif_account.name, account_type=account_type),
        )
        if qif_account.account_type == "Invst":
            inferred = _infer_account_type(qif_account.name)
            if inferred is not None:
                account.account_type = inferred
            else:
                warnings.append(
                    ImportWarning(
                        message=(
                            f"Imported QIF investment account '{qif_account.name}' as taxable; "
                            "verify whether it should be an IRA, 401(k), HSA, or trust account."
                        )
                    )
                )
        _append_cash_holding_from_balance(account, qif_account, warnings)

    # --- 2. Compute investment holdings via FIFO lot engine ---------------
    holdings, position_only = _compute_holdings(
        parsed.investment_transactions,
        security_symbols,
        warnings,
    )

    # --- 3. Convert computed holdings into TaxLot entries ----------------
    for acct_name, ticker_holdings in holdings.items():
        # Ensure the account exists in our map.
        if acct_name not in accounts_map:
            qif_acct = parsed.accounts.get(acct_name)
            acct_type = _map_raw_account_type(qif_acct)
            if acct_type is None:
                continue
            accounts_map[acct_name] = Account(
                name=acct_name, account_type=acct_type,
            )
            # Infer type for investment accounts not previously seen.
            if qif_acct and qif_acct.account_type == "Invst":
                inferred = _infer_account_type(acct_name)
                if inferred is not None:
                    accounts_map[acct_name].account_type = inferred
                elif _infer_account_type(acct_name) is None:
                    warnings.append(
                        ImportWarning(
                            message=(
                                f"Imported QIF investment account '{acct_name}' as taxable; "
                                "verify whether it should be an IRA, 401(k), HSA, or trust account."
                            )
                        )
                    )

        account = accounts_map[acct_name]

        for ticker, h in ticker_holdings.items():
            # Skip securities with no remaining shares.
            if h.shares <= _TINY:
                continue
            for lot in h.lots:
                if lot.shares <= _TINY:
                    continue
                _append_tax_lot(
                    account=account,
                    ticker=ticker,
                    shares=lot.shares,
                    cost_basis_per_share=lot.price_per_share,
                    purchase_date=lot.purchase_date,
                    warnings=warnings,
                )

    # --- 4. Compute cash balances for banking accounts ------------------
    banking_balances: dict[str, Decimal] = {}
    latest_dates: dict[str, date] = {}
    for txn in parsed.banking_transactions:
        banking_balances[txn.account] = banking_balances.get(txn.account, _ZERO) + txn.amount
        if txn.date is not None:
            prev = latest_dates.get(txn.account)
            if prev is None or txn.date > prev:
                latest_dates[txn.account] = txn.date

    for acct_name, balance in banking_balances.items():
        if balance <= _ZERO:
            continue
        qif_acct = parsed.accounts.get(acct_name)
        acct_type = _map_qif_account_type(qif_acct, warnings) if qif_acct else AccountType.TAXABLE
        if acct_type is None:
            continue
        # Skip if we already created a cash holding from statement balance
        account = accounts_map.get(acct_name)
        if account is not None and account.cash_holdings:
            continue
        account = accounts_map.setdefault(
            acct_name, Account(name=acct_name, account_type=acct_type),
        )
        try:
            account.cash_holdings.append(
                CashHolding(
                    amount=balance,
                    valuation_date=latest_dates.get(acct_name) or date.today(),
                    is_money_market=False,
                    ticker=None,
                    counts_toward_liquidity_reserve=True,
                )
            )
        except ValidationError:
            warnings.append(
                ImportWarning(
                    message=f"Skipped computed balance for '{acct_name}' — invalid cash holding.",
                )
            )

    non_empty = [
        a for a in accounts_map.values()
        if a.tax_lots or a.cash_holdings
    ]

    return ImportPreviewResponse(
        accounts=non_empty,
        warnings=_dedupe_warnings(warnings),
        position_only=position_only,
    )


def _append_cash_holding_from_balance(
    account: Account,
    qif_account: QifAccount,
    warnings: list[ImportWarning],
) -> None:
    if qif_account.account_type not in {"Bank", "Cash", "Oth A", "Invst"}:
        return
    if qif_account.statement_balance_amount <= 0:
        return

    try:
        account.cash_holdings.append(
            CashHolding(
                amount=qif_account.statement_balance_amount,
                valuation_date=qif_account.statement_balance_date or date.today(),
                is_money_market=False,
                ticker=None,
                counts_toward_liquidity_reserve=qif_account.account_type != "Invst",
            )
        )
    except ValidationError:
        warnings.append(
            ImportWarning(
                message=(
                    f"Skipped balance for account '{qif_account.name}' because the cash holding "
                    "was invalid."
                )
            )
        )


def _append_tax_lot(
    *,
    account: Account,
    ticker: str,
    shares: Decimal,
    cost_basis_per_share: Decimal,
    purchase_date: date,
    warnings: list[ImportWarning],
) -> None:
    try:
        account.tax_lots.append(
            TaxLot(
                ticker=ticker,
                shares=shares,
                cost_basis_per_share=cost_basis_per_share,
                purchase_date=purchase_date,
            )
        )
    except ValidationError:
        warnings.append(
            ImportWarning(
                message=(
                    f"Skipped lot for {ticker} in account '{account.name}' because it failed "
                    "validation."
                )
            )
        )


def _build_security_symbol_lookup(parsed: QifData) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for security in parsed.securities:
        if security.name.strip() and security.symbol.strip():
            lookup[security.name.strip().casefold()] = security.symbol.strip().upper()
        if security.symbol.strip():
            lookup[security.symbol.strip().casefold()] = security.symbol.strip().upper()
    return lookup


def _resolve_ticker(
    security_name: str,
    security_symbols: dict[str, str],
) -> tuple[str, ImportWarning | None]:
    cleaned = security_name.strip()
    if not cleaned:
        return "", None

    resolved = security_symbols.get(cleaned.casefold())
    if resolved:
        return resolved, None

    fallback = cleaned.upper().replace(" ", "")
    return fallback, ImportWarning(
        message=f"No security definition found for '{cleaned}'; using '{fallback}' as ticker.",
    )


def _map_qif_account_type(
    qif_account: QifAccount,
    warnings: list[ImportWarning],
) -> AccountType | None:
    raw_type = qif_account.account_type or ""
    if raw_type in {"CCard", "Oth L"}:
        warnings.append(
            ImportWarning(
                message=(
                    f"Skipped unsupported QIF account type '{raw_type}' "
                    f"for '{qif_account.name}'."
                )
            )
        )
        return None
    if raw_type and raw_type not in {"Bank", "Cash", "Oth A", "Invst"}:
        warnings.append(
            ImportWarning(
                message=f"Skipped unknown QIF account type '{raw_type}' for '{qif_account.name}'."
            )
        )
        return None
    inferred = _infer_account_type(qif_account.name)
    return inferred if inferred is not None else AccountType.TAXABLE


def _map_raw_account_type(qif_account: QifAccount | None) -> AccountType | None:
    if qif_account is None:
        return AccountType.TAXABLE
    if qif_account.account_type in {"CCard", "Oth L"}:
        return None
    inferred = _infer_account_type(qif_account.name)
    return inferred if inferred is not None else AccountType.TAXABLE


def _dedupe_warnings(warnings: list[ImportWarning]) -> list[ImportWarning]:
    seen: set[tuple[int | None, str]] = set()
    deduped: list[ImportWarning] = []
    for warning in warnings:
        key = (warning.line, warning.message)
        if key not in seen:
            seen.add(key)
            deduped.append(warning)
    return deduped
