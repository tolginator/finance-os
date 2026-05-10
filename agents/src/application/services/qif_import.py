"""QIF-to-household import preview mapping."""

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
_BUY_ACTIONS = frozenset({"buy", "buyx"})
_REINVEST_ACTIONS = frozenset({"reinvdiv", "reinvint", "reinvlg", "reinvsh"})
_POSITION_ACTIONS = frozenset({"shrsin"})
_SKIP_ACTIONS = frozenset({"sell", "sellx", "div", "intinc", "cglong", "cgshort", "shrsout"})

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


def preview_qif_import(
    qif_content: str,
    household_name: str = "My Household",
) -> ImportPreviewResponse:
    """Parse QIF content and return proposed household accounts.

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
    position_only = False
    security_symbols = _build_security_symbol_lookup(parsed)

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
                account = accounts_map[qif_account.name]
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

    for investment in parsed.investment_transactions:
        account_type = _map_raw_account_type(parsed.accounts.get(investment.account))
        if account_type is None:
            continue

        account = accounts_map.setdefault(
            investment.account,
            Account(name=investment.account, account_type=account_type),
        )
        if account.account_type == AccountType.TAXABLE and (
            parsed.accounts.get(investment.account) is None
            or parsed.accounts[investment.account].account_type == "Invst"
        ) and _infer_account_type(investment.account) is None:
            warnings.append(
                ImportWarning(
                    message=(
                        f"Imported QIF investment account '{investment.account}' as taxable; "
                        "verify whether it should be an IRA, 401(k), HSA, or trust account."
                    )
                )
            )

        normalized_action = investment.action.strip().lower().replace(" ", "")
        if normalized_action in _SKIP_ACTIONS or not normalized_action:
            continue

        ticker, ticker_warning = _resolve_ticker(investment.security, security_symbols)
        if ticker_warning is not None:
            warnings.append(ticker_warning)
        if not ticker:
            warnings.append(
                ImportWarning(
                    message=(
                        f"Skipped investment transaction in account '{investment.account}' "
                        "because no ticker could be resolved."
                    )
                )
            )
            position_only = True
            continue

        if investment.quantity <= 0:
            warnings.append(
                ImportWarning(
                    message=(
                        f"Skipped {investment.action or 'investment'} transaction for {ticker} "
                        f"in account '{investment.account}' because shares were missing."
                    )
                )
            )
            position_only = True
            continue

        if normalized_action in _BUY_ACTIONS or normalized_action in _REINVEST_ACTIONS:
            lot_date = investment.date or date.today()
            lot_basis = investment.price
            if investment.price <= 0 or investment.date is None:
                position_only = True
                warnings.append(
                    ImportWarning(
                        message=(
                            f"Lot for {ticker} in account '{investment.account}' is missing "
                            "cost basis or purchase date — imported as position-only."
                        )
                    )
                )
                if investment.price <= 0:
                    lot_basis = _ZERO
            _append_tax_lot(
                account=account,
                ticker=ticker,
                shares=investment.quantity,
                cost_basis_per_share=lot_basis,
                purchase_date=lot_date,
                warnings=warnings,
            )
            continue

        if normalized_action in _POSITION_ACTIONS:
            position_only = True
            warnings.append(
                ImportWarning(
                    message=(
                        f"Share transfer for {ticker} in account '{investment.account}' "
                        "lacks complete cost basis — imported as position-only."
                    )
                )
            )
            _append_tax_lot(
                account=account,
                ticker=ticker,
                shares=investment.quantity,
                cost_basis_per_share=investment.price if investment.price > 0 else _ZERO,
                purchase_date=investment.date or date.today(),
                warnings=warnings,
            )
            continue

        warnings.append(
            ImportWarning(
                message=(
                    f"Skipped unsupported investment action '{investment.action}' "
                    f"in account '{investment.account}'."
                )
            )
        )

    if not parsed.accounts:
        for banking in parsed.banking_transactions:
            accounts_map.setdefault(
                banking.account,
                Account(name=banking.account, account_type=AccountType.TAXABLE),
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
